import json
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional

from .base import CloudProvider


class AzureProvider(CloudProvider):
    """
    Microsoft Azure provider via the Azure CLI (az).

    Concepts mapped to awsctl's cloud-agnostic model:
        account  → Azure Subscription (id = subscription UUID, name = display name)
        role     → Azure RBAC role assignment on the subscription
                   (falls back to org["roles"] when RBAC query is impractical)
        region   → Azure region (e.g. eastus, westeurope)

    Requires: Azure CLI (az) installed and on PATH.

    Org config keys:
        provider:        "azure"
        tenant_id:       Azure AD tenant UUID (optional — az login prompts if absent)
        allowed_regions: list of permitted Azure region names
        default_region:  default region
        roles:           optional static list of role names (skips live RBAC query)
        sensitive_roles: roles requiring break-glass logging
        preferred_roles: roles shown first in the picker
    """

    _ENV_VARS = [
        "AZURE_SUBSCRIPTION_ID",
        "AZURE_TENANT_ID",
        "ARM_SUBSCRIPTION_ID",
        "ARM_TENANT_ID",
        "ARM_ACCESS_TOKEN",
    ]

    # ------------------------------------------------------------------ helpers

    def _az(self, args: List[str]) -> Dict[str, Any]:
        az_bin = shutil.which("az")
        if not az_bin:
            from ..utils import console

            console.print(
                "[red]Azure CLI (az) not found in PATH. Install from https://aka.ms/azure-cli[/]"
            )
            sys.exit(1)
        result = subprocess.run(
            [az_bin] + args,
            capture_output=True,
            text=True,
        )
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    # ----------------------------------------------------------------- interface

    def login(self, org: Dict[str, Any]) -> int:
        args = ["login"]
        tenant = org.get("tenant_id")
        if tenant:
            args += ["--tenant", tenant]
        result = self._az(args)
        return result["returncode"]

    def load_token(self, org: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Returns the active az account dict, or None if not authenticated.
        We use this as the opaque "token" — it carries subscription + tenant info.
        """
        result = self._az(["account", "show", "--output", "json"])
        if result["returncode"] != 0:
            return None
        try:
            return json.loads(result["stdout"])
        except (json.JSONDecodeError, ValueError):
            return None

    def list_accounts(self, org: Dict[str, Any], token: Any) -> List[Dict[str, str]]:
        result = self._az(["account", "list", "--output", "json"])
        if result["returncode"] != 0:
            return []
        try:
            subs = json.loads(result["stdout"])
            return [{"id": s["id"], "name": s["name"]} for s in subs]
        except (json.JSONDecodeError, KeyError, ValueError):
            return []

    def list_roles(self, org: Dict[str, Any], token: Any, account_id: str) -> List[str]:
        # Prefer a static configured list — RBAC queries can be very slow and noisy.
        if org.get("roles"):
            return list(org["roles"])

        # Fall back to live RBAC: unique role definition names for this subscription.
        result = self._az(
            [
                "role",
                "assignment",
                "list",
                "--subscription",
                account_id,
                "--output",
                "json",
            ]
        )
        if result["returncode"] != 0:
            return ["Contributor"]  # sensible default so the picker isn't empty
        try:
            assignments = json.loads(result["stdout"])
            seen: Dict[str, None] = {}
            for a in assignments:
                role_name = a.get("roleDefinitionName")
                if role_name:
                    seen[role_name] = None
            return list(seen.keys()) or ["Contributor"]
        except (json.JSONDecodeError, KeyError, ValueError):
            return ["Contributor"]

    def get_credentials(
        self, org: Dict[str, Any], account: str, role: str, region: str
    ) -> Dict[str, str]:
        # Set the active subscription context (side-effect on az CLI state).
        set_result = self._az(["account", "set", "--subscription", account])
        if set_result["returncode"] != 0:
            from ..utils import console

            console.print(f"[red]Failed to set Azure subscription {account}[/]")
            sys.exit(1)

        # Fetch a short-lived access token for the subscription.
        token_result = self._az(
            [
                "account",
                "get-access-token",
                "--subscription",
                account,
                "--output",
                "json",
            ]
        )
        if token_result["returncode"] != 0:
            from ..utils import console

            console.print(
                "[red]Failed to get Azure access token. Re-run 'awsctl login <org>'.[/]"
            )
            sys.exit(1)

        try:
            token_data = json.loads(token_result["stdout"])
            access_token = token_data["accessToken"]
        except (json.JSONDecodeError, KeyError):
            from ..utils import console

            console.print("[red]Unexpected token response from Azure CLI.[/]")
            sys.exit(1)

        tenant_id = org.get("tenant_id", token_data.get("tenant", ""))

        return {
            "AZURE_SUBSCRIPTION_ID": account,
            "AZURE_TENANT_ID": tenant_id,
            # Terraform / OpenTofu use ARM_* prefix
            "ARM_SUBSCRIPTION_ID": account,
            "ARM_TENANT_ID": tenant_id,
            "ARM_ACCESS_TOKEN": access_token,
        }

    def get_unsets(self) -> str:
        return "\n".join(f"unset {v}" for v in self._ENV_VARS)

    def logout(self, org: Dict[str, Any]) -> int:
        result = self._az(["logout"])
        return result["returncode"]
