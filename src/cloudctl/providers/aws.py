import json
import sys
from typing import Any, Dict, List, Optional

from .base import CloudProvider
from ..aws import (
    run_aws,
    ensure_sso_base_profile,
)
from ..sso_cache import OrgRef, load_active_sso_token


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

    def login(self, org: Dict[str, Any]) -> int:
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
            ensure_sso_base_profile(org)
            from .. import utils as _utils

            # Interactive: inherit stdio (capture=False) so `aws sso login` opens
            # the browser AND prints the verification URL/code as a fallback, and
            # blocks until the human completes the browser approval. Capturing
            # output here would hide the code and break the device-auth flow.
            _utils.run(
                ["aws", "sso", "login", "--sso-session", org["name"]],
                capture=False,
            )
            return 0
        except Exception as e:
            from ..utils import console

            console.print(f"[red]Login failed:[/] {e}")
            return 1

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
        sso_region = (
            org.get("sso_region") if isinstance(org, dict) else org.sso_region
        )

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
