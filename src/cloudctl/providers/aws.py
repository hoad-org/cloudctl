import json
import logging
import subprocess
import sys
from typing import Any, Dict, List, Optional

from .base import CloudProvider
from ..aws import (
    run_aws,
    ensure_sso_base_profile,
)
from ..sso_cache import OrgRef, load_active_sso_token

logger = logging.getLogger(__name__)


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

            _utils.run(["aws", "sso", "login", "--sso-session", org["name"]])
            return 0
        except Exception as e:
            from ..utils import console

            console.print(f"[red]Login failed:[/] {e}")
            return 1

    def load_token(self, org: Dict[str, Any]) -> Optional[Any]:
        """
        Load the active AWS SSO token for the organization.

        Returns the SsoToken object if authenticated, or a placeholder token
        in non-interactive environments where authentication isn't possible.
        """
        name = org.get("name", "") if isinstance(org, dict) else org.name
        url = (
            org.get("sso_start_url", "") if isinstance(org, dict) else org.sso_start_url
        )
        region = org.get("sso_region", "") if isinstance(org, dict) else org.sso_region

        try:
            token = load_active_sso_token(OrgRef(name, url, region))
            return token
        except KeyboardInterrupt:
            raise
        except SystemExit:
            raise
        except Exception as e:
            logger.debug(f"AWS SSO token load failed: {type(e).__name__}: {e}")
            # Return None to indicate unauthenticated state (caller will trigger login)
            return None

    def list_accounts(self, org: Dict[str, Any], token: Any) -> List[Dict[str, str]]:
        """
        List AWS accounts available to the authenticated user.

        Returns a list of {id, name} dicts for each accessible account.
        On error, logs the failure and returns an empty list.
        """
        try:
            from .. import aws as _aws

            raw = _aws.sso_list_accounts(token)
            if not raw:
                logger.warning("AWS SSO returned empty account list")
                return []
            return [{"id": a["accountId"], "name": a["accountName"]} for a in raw]
        except KeyboardInterrupt:
            raise
        except SystemExit:
            raise
        except Exception as e:
            logger.error(f"Failed to list AWS accounts: {type(e).__name__}: {e}")
            return []

    def list_roles(self, org: Dict[str, Any], token: Any, account_id: str) -> List[str]:
        """
        List AWS IAM roles available to the user in the specified account.

        Returns a list of role names. On error, logs the failure and returns
        an empty list (which will prompt interactive role selection).
        """
        try:
            from .. import aws as _aws

            raw = _aws.sso_list_account_roles(token, account_id)
            if not raw:
                logger.warning(f"AWS SSO returned no roles for account {account_id}")
                return []
            return [r["roleName"] for r in raw]
        except KeyboardInterrupt:
            raise
        except SystemExit:
            raise
        except Exception as e:
            logger.error(
                f"Failed to list AWS roles for account {account_id}: {type(e).__name__}: {e}"
            )
            return []

    def get_credentials(
        self, org: Dict[str, Any], account: str, role: str, region: str
    ) -> Dict[str, str]:
        """
        Fetch temporary credentials for the specified account and role.

        Calls AWS SSO to get-role-credentials and returns environment variables
        for AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN.
        """
        from ..utils import console

        args = [
            "sso",
            "get-role-credentials",
            "--account-id",
            account,
            "--role-name",
            role,
            "--region",
            region,
        ]
        try:
            res = run_aws(args, timeout=30)
        except subprocess.TimeoutExpired:
            console.print(
                "[red]AWS CLI command timed out after 30 seconds. "
                "Check network connectivity and try again.[/]"
            )
            logger.error(f"AWS STS get-role-credentials timed out for {account}/{role}")
            sys.exit(1)

        if res.get("returncode") != 0:
            # Check whether the SSO token is still valid
            token = self.load_token(org)
            if not token:
                console.print(
                    "[red]No valid SSO session. Run 'cloudctl login <org>'.[/]"
                )
                logger.error(f"No valid SSO token for {org.get('name', 'unknown')}")
            else:
                stderr = res.get("stderr", "")
                logger.error(
                    f"AWS STS credentials fetch failed for {account}/{role}: {stderr}"
                )
            sys.exit(1)

        try:
            data = json.loads(res.get("stdout", "{}"))
            creds = data.get("roleCredentials", {})
            if not creds:
                console.print("[red]No credentials returned from AWS STS.[/]")
                logger.error(f"AWS STS returned empty credentials for {account}/{role}")
                sys.exit(1)
        except json.JSONDecodeError as e:
            console.print("[red]Invalid JSON response from AWS STS.[/]")
            logger.error(f"Failed to parse AWS STS response: {e}")
            sys.exit(1)

        name = org.get("name", "cloudctl") if isinstance(org, dict) else org.name
        return {
            "AWS_ACCESS_KEY_ID": creds["accessKeyId"],
            "AWS_SECRET_ACCESS_KEY": creds["secretAccessKey"],
            "AWS_SESSION_TOKEN": creds["sessionToken"],
            "AWS_PROFILE": f"{name}-{account}-{role}",
        }

    def get_token_expiry(self, org: Dict[str, Any]) -> "Optional[Any]":
        """
        Return the expiry datetime for the active AWS SSO session.

        AWS SSO tokens accessed via load_token() return an SsoToken object
        with an expiresAt attribute. This method extracts that value for
        consumption by watch/context expiry monitoring.
        """
        try:
            token = self.load_token(org)
            if token and hasattr(token, "expiresAt"):
                return token.expiresAt
            return None
        except Exception as e:
            logger.debug(f"Failed to get AWS token expiry: {e}")
            return None

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
