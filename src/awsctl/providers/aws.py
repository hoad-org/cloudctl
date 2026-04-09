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
        name = org.get("name", "") if isinstance(org, dict) else org.name
        url = (
            org.get("sso_start_url", "") if isinstance(org, dict) else org.sso_start_url
        )
        region = org.get("sso_region", "") if isinstance(org, dict) else org.sso_region
        return load_active_sso_token(OrgRef(name, url, region))

    def list_accounts(self, org: Dict[str, Any], token: Any) -> List[Dict[str, str]]:
        try:
            from .. import aws as _aws

            raw = _aws.sso_list_accounts(token)
            return [{"id": a["accountId"], "name": a["accountName"]} for a in raw]
        except Exception:
            return []

    def list_roles(self, org: Dict[str, Any], token: Any, account_id: str) -> List[str]:
        try:
            from .. import aws as _aws

            raw = _aws.sso_list_account_roles(token, account_id)
            return [r["roleName"] for r in raw]
        except Exception:
            return []

    def get_credentials(
        self, org: Dict[str, Any], account: str, role: str, region: str
    ) -> Dict[str, str]:
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
        res = run_aws(args)
        if res.get("returncode") != 0:
            # Check whether the SSO token is still valid
            token = self.load_token(org)
            if not token:
                from ..utils import console

                console.print("[red]No valid SSO session. Run 'awsctl login <org>'.[/]")
            sys.exit(1)

        data = json.loads(res.get("stdout", "{}"))
        creds = data.get("roleCredentials", {})
        if not creds:
            from ..utils import console

            console.print("[red]No credentials returned from AWS STS.[/]")
            sys.exit(1)

        name = org.get("name", "awsctl") if isinstance(org, dict) else org.name
        return {
            "AWS_ACCESS_KEY_ID": creds["accessKeyId"],
            "AWS_SECRET_ACCESS_KEY": creds["secretAccessKey"],
            "AWS_SESSION_TOKEN": creds["sessionToken"],
            "AWS_PROFILE": f"{name}-{account}-{role}",
        }

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
