import json
import sys
from typing import Any, Dict, List, Optional

from .base import CloudProvider
from ..aws import (
    run_aws,
)
from ..sso_cache import OrgRef, load_active_sso_token, write_sso_token


class AwsProvider(CloudProvider):
    """
    AWS IAM Identity Center (SSO) provider.

    Delegates to the existing aws.py / sso_cache.py layer so all
    existing behaviour, tests, and config-file management are unchanged.
    """

    # Env vars owned by this provider — cleared on logout/unset.
    _ENV_VARS = [
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_PROFILE",
    ]

    # Device-authorization polling bounds. The AWS SSO OIDC service returns an
    # `interval` (seconds between polls) and `expiresIn` (seconds until the
    # device code dies); we honour both. These are only fallbacks used when the
    # service omits them.
    _DEFAULT_POLL_INTERVAL = 5
    _MAX_POLL_INTERVAL = 60

    def login(self, org: Dict[str, Any]) -> int:
        """Authenticate to IAM Identity Center via the SSO OIDC device flow.

        Zero-trust: this writes NO profile or `[sso-session]` block to
        ~/.aws/config. The only disk artifact is the short-lived SSO access
        token in the standard AWS SSO cache dir (~/.aws/sso/cache) — the same
        file the AWS CLI itself uses and that `get_credentials` reads back.
        The vended STS credentials are never written to disk.
        """
        # AWS China (aws-cn) does not support IAM Identity Center.
        # Users must configure long-term IAM access keys directly.
        partition = org.get("partition", "aws")
        if partition == "aws-cn":
            from ..utils import console

            console.print(
                "[red]AWS China (aws-cn) does not support IAM Identity Center.[/]\n"
                "Configure long-term IAM access keys in your environment:\n"
                "  export AWS_ACCESS_KEY_ID=<key>\n"
                "  export AWS_SECRET_ACCESS_KEY=<secret>\n"
                "  export AWS_DEFAULT_REGION=cn-north-1"
            )
            return 1

        try:
            return self._device_authorization_login(org)
        except Exception as e:
            from ..utils import console

            console.print(f"[red]Login failed:[/] {e}")
            return 1

    def _device_authorization_login(self, org: Dict[str, Any]) -> int:
        import time
        from datetime import datetime, timedelta, timezone

        import boto3
        from botocore.exceptions import ClientError

        from .. import utils as _utils

        sso_region = org.get("sso_region", "")
        start_url = org.get("sso_start_url", "")
        name = org.get("name", "")

        if not sso_region or not start_url:
            raise RuntimeError(
                "Org is missing sso_region/sso_start_url; cannot start SSO login."
            )

        # boto3 resolves the correct sso-oidc endpoint from region_name, so
        # govcloud/other partitions work without any endpoint override.
        ssooidc = boto3.client("sso-oidc", region_name=sso_region)

        reg = ssooidc.register_client(clientName="cloudctl", clientType="public")
        client_id = reg["clientId"]
        client_secret = reg["clientSecret"]

        dev = ssooidc.start_device_authorization(
            clientId=client_id,
            clientSecret=client_secret,
            startUrl=start_url,
        )
        device_code = dev["deviceCode"]
        user_code = dev.get("userCode", "")
        verification_uri_complete = dev.get("verificationUriComplete", "")
        verification_uri = dev.get("verificationUri", "")
        _interval = dev.get("interval")
        interval = (
            int(_interval)
            if _interval is not None
            else self._DEFAULT_POLL_INTERVAL
        )
        expires_in = int(dev.get("expiresIn", 600))

        # Open the browser AND print the URL + code to STDERR so a headless /
        # agent flow can complete the approval out-of-band. `console` writes to
        # stderr; keeping the machine-readable stdout stream clean.
        _utils.console.print(
            "[yellow]To authenticate, open the following URL and confirm the "
            f"code:[/]\n  URL:  {verification_uri or verification_uri_complete}\n"
            f"  Code: {user_code}"
        )
        if verification_uri_complete:
            _utils.open_browser(verification_uri_complete)

        # Poll create_token, honouring interval/SlowDown and the hard expiry
        # deadline so we NEVER hang indefinitely.
        deadline = time.monotonic() + expires_in
        while True:
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    "Device authorization expired before it was approved. "
                    "Run 'cloudctl login' again."
                )
            time.sleep(interval)
            try:
                tok = ssooidc.create_token(
                    clientId=client_id,
                    clientSecret=client_secret,
                    grantType="urn:ietf:params:oauth:grant-type:device_code",
                    deviceCode=device_code,
                )
                break
            except ClientError as e:
                code = e.response.get("Error", {}).get("Code", "")
                if code == "AuthorizationPendingException":
                    continue
                if code == "SlowDownException":
                    interval = min(interval + 5, self._MAX_POLL_INTERVAL)
                    continue
                raise

        access_token = tok["accessToken"]
        expires_in_token = int(tok.get("expiresIn", 8 * 3600))
        expires_at = (
            datetime.now(timezone.utc) + timedelta(seconds=expires_in_token)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

        write_sso_token(
            OrgRef(name, start_url, sso_region),
            access_token=access_token,
            expires_at=expires_at,
            client_id=client_id,
            client_secret=client_secret,
            registration_expires_at=self._iso_from_epoch(
                reg.get("clientSecretExpiresAt")
            ),
            refresh_token=tok.get("refreshToken"),
        )
        _utils.console.print("[green]SSO login complete.[/]")
        return 0

    @staticmethod
    def _iso_from_epoch(epoch: Any) -> str:
        """Format an epoch-seconds value (as returned by register_client's
        clientSecretExpiresAt) as an ISO-8601 UTC string; '' if unavailable."""
        from datetime import datetime, timezone

        if not epoch:
            return ""
        try:
            return datetime.fromtimestamp(int(epoch), tz=timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
        except (ValueError, TypeError, OSError):
            return ""

    def load_token(self, org: Dict[str, Any]) -> Optional[Any]:
        name = org.get("name", "") if isinstance(org, dict) else org.name
        url = (
            org.get("sso_start_url", "") if isinstance(org, dict) else org.sso_start_url
        )
        region = org.get("sso_region", "") if isinstance(org, dict) else org.sso_region
        return load_active_sso_token(OrgRef(name, url, region))

    def list_accounts(self, org: Dict[str, Any], token: Any) -> List[Dict[str, str]]:
        try:
            from .. import aws as _aws

            region = org.get("sso_region")
            raw = _aws.sso_list_accounts(token, region=region)
            return [{"id": a["accountId"], "name": a["accountName"]} for a in raw]
        except Exception:
            return []

    def list_roles(self, org: Dict[str, Any], token: Any, account_id: str) -> List[str]:
        try:
            from .. import aws as _aws

            region = org.get("sso_region")
            raw = _aws.sso_list_account_roles(token, account_id, region=region)
            return [r["roleName"] for r in raw]
        except Exception:
            return []

    def get_credentials(
        self, org: Dict[str, Any], account: str, role: str, region: str
    ) -> Dict[str, str]:
        # Load the cached SSO access token — required for get-role-credentials
        token = self.load_token(org)
        if not token or not hasattr(token, "accessToken"):
            from ..utils import console

            console.print("[red]No valid SSO session. Run 'cloudctl login <org>'.[/]")
            sys.exit(1)

        # The get-role-credentials call is an IAM Identity Center (SSO) portal
        # API. It MUST be made in the SSO instance region (org.sso_region), NOT
        # the region the user wants the *executed command* to run in. Conflating
        # the two is the classic failure: an SSO instance in eu-west-2 vending
        # creds for a command that targets us-east-1 would otherwise send the
        # portal call to the wrong endpoint and fail with "session token not
        # found or invalid". (list_accounts/list_roles already do this right.)
        sso_region = org.get("sso_region") if isinstance(org, dict) else org.sso_region

        args = [
            "sso",
            "get-role-credentials",
            "--account-id",
            account,
            "--role-name",
            role,
            "--access-token",
            token.accessToken,
            "--region",
            sso_region,
        ]
        res = run_aws(args)
        if res.get("returncode") != 0:
            from ..utils import console

            error_msg = res.get("stderr", "AWS CLI failed")
            console.print(f"[red]Failed to retrieve credentials:[/] {error_msg}")
            sys.exit(1)

        data = json.loads(res.get("stdout", "{}"))
        creds = data.get("roleCredentials", {})
        if not creds:
            from ..utils import console

            console.print("[red]No credentials returned from AWS STS.[/]")
            sys.exit(1)

        # Return ONLY the short-lived STS keys, plus the region the executed
        # command should target. Do NOT set AWS_PROFILE: these keys are
        # self-contained, and a profile name that doesn't exist in
        # ~/.aws/config takes precedence over the keys and makes the child
        # command fail with "config profile could not be found". Profile
        # management is exactly what this tool exists to avoid.
        out = {
            "AWS_ACCESS_KEY_ID": creds["accessKeyId"],
            "AWS_SECRET_ACCESS_KEY": creds["secretAccessKey"],
            "AWS_SESSION_TOKEN": creds["sessionToken"],
        }
        if region:
            out["AWS_REGION"] = region
            out["AWS_DEFAULT_REGION"] = region
        return out

    def get_unsets(self) -> str:
        return "\n".join(f"unset {v}" for v in self._ENV_VARS)

    def logout(self, org: Dict[str, Any]) -> int:
        import subprocess
        from ..aws import _resolve_aws_cli

        try:
            aws_bin = _resolve_aws_cli()
        except RuntimeError:
            aws_bin = "aws"
        result = subprocess.run([aws_bin, "sso", "logout"], check=False)
        return result.returncode
