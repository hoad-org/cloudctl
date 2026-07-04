import json
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional

from .. import exit_codes
from .base import CloudProvider, ProviderCredentialError


class AzureProvider(CloudProvider):
    """
    Microsoft Azure provider via the Azure CLI (az).

    Concepts mapped to cloudctl's cloud-agnostic model:
        account  → Azure Subscription (id = subscription UUID, name = display name)
        role     → Azure RBAC role assignment on the subscription
                   (falls back to org["roles"] when RBAC query is impractical)
        region   → Azure region (e.g. eastus, westeurope)

    Requires: Azure CLI (az) installed and on PATH.

    Credential injection contract (exec) — IMPORTANT SCOPE NOTE:
        The `az` CLI cannot consume a raw *bearer token* from an environment
        variable; it always uses its own `az login` session. A raw ARM_ACCESS_
        TOKEN therefore targets Terraform / OpenTofu (the azurerm provider) and
        Azure SDK consumers, NOT the bare `az` CLI. We emit the full ARM_* set
        (ARM_SUBSCRIPTION_ID, ARM_TENANT_ID, ARM_ACCESS_TOKEN) and set
        ARM_USE_CLI=false whenever a token is present so azurerm uses the
        injected token instead of the ambient CLI login.

        HOWEVER: `az` (and azure-identity's EnvironmentCredential) DO honor
        AZURE_CLIENT_ID / AZURE_CLIENT_SECRET / AZURE_TENANT_ID (service-
        principal login). So when the org config supplies SP creds
        (client_id + client_secret + tenant_id), get_credentials ALSO emits
        those three vars — and only then does a bare `az` command actually run
        under the injected identity rather than the ambient login.
        ``az_uses_injected_identity(org)`` reports exactly this: True iff SP
        creds are configured. cloudctl does NOT invent credentials — with no SP
        config, only the ARM_* set is emitted and the method returns False.

        get_credentials() is side-effect free: it never runs `az account set`
        (which would mutate the user's global default subscription and race
        across concurrent invocations). Subscription selection is passed
        per-invocation via env (AZURE_SUBSCRIPTION_ID / ARM_SUBSCRIPTION_ID),
        and any child `az` command cloudctl runs itself passes `--subscription`
        explicitly rather than relying on global state.

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
        "AZURE_CLIENT_ID",
        "AZURE_CLIENT_SECRET",
        "ARM_SUBSCRIPTION_ID",
        "ARM_TENANT_ID",
        "ARM_ACCESS_TOKEN",
        "ARM_USE_CLI",
    ]

    # ------------------------------------------------------------------ helpers

    def _az(self, args: List[str], capture: bool = True) -> Dict[str, Any]:
        az_bin = shutil.which("az")
        if not az_bin:
            from ..utils import console

            console.print(
                "[red]Azure CLI (az) not found in PATH. Install from https://aka.ms/azure-cli[/]"
            )
            sys.exit(1)
        # capture=False inherits stdio for interactive auth (browser opens + the
        # user completes consent); capture=True is for parsed, non-interactive queries.
        result = subprocess.run(
            [az_bin] + args,
            capture_output=capture,
            text=True,
        )
        return {
            "returncode": result.returncode,
            "stdout": result.stdout if capture else "",
            "stderr": result.stderr if capture else "",
        }

    # ----------------------------------------------------------------- interface

    def login(self, org: Dict[str, Any]) -> int:
        # Interactive (capture=False): az opens the browser for consent.
        args = ["login"]
        tenant = org.get("tenant_id")
        if tenant:
            args += ["--tenant", tenant]
        result = self._az(args, capture=False)
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

    @staticmethod
    def _sp_creds(org: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """Return {client_id, client_secret, tenant_id} iff the org config
        supplies a COMPLETE service-principal credential set, else None.
        Never invents values."""
        if not isinstance(org, dict):
            return None
        client_id = org.get("client_id")
        client_secret = org.get("client_secret")
        tenant_id = org.get("tenant_id")
        if client_id and client_secret and tenant_id:
            return {
                "client_id": str(client_id),
                "client_secret": str(client_secret),
                "tenant_id": str(tenant_id),
            }
        return None

    def az_uses_injected_identity(self, org: Dict[str, Any]) -> bool:
        """True only when SP creds are configured — the sole case where a bare
        `az` command runs under the injected identity (via AZURE_CLIENT_*)
        rather than the ambient login."""
        return self._sp_creds(org) is not None

    def get_identity(self, org: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """LIVE identity via `az account show`. Returns
        {"user","subscription_id","tenant_id"} or None if it cannot be
        verified. Never fabricates from stored context."""
        result = self._az(["account", "show", "--output", "json"])
        if result["returncode"] != 0:
            return None
        try:
            data = json.loads(result["stdout"] or "{}")
        except (json.JSONDecodeError, ValueError):
            return None
        sub_id = data.get("id")
        tenant_id = data.get("tenantId", "")
        user = ""
        user_obj = data.get("user")
        if isinstance(user_obj, dict):
            user = user_obj.get("name", "") or ""
        if not sub_id:
            return None
        return {
            "user": user,
            "subscription_id": sub_id,
            "tenant_id": tenant_id or "",
        }

    def get_token_expiry(self, org: Dict[str, Any]) -> "Optional[Any]":
        """
        Return token expiry by calling 'az account get-access-token'.
        The expiresOn field is a UTC datetime string: "2024-03-15 10:30:00.000000"
        """
        from datetime import datetime, timezone

        result = self._az(["account", "get-access-token", "--output", "json"])
        if result["returncode"] != 0:
            return None
        try:
            data = json.loads(result["stdout"])
            expires_on = data.get("expiresOn", "")
            if not expires_on:
                return None
            # Format: "2024-03-15 10:30:00.000000" (UTC)
            dt = datetime.strptime(expires_on, "%Y-%m-%d %H:%M:%S.%f")
            return dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None

    def list_accounts(self, org: Dict[str, Any], token: Any) -> List[Dict[str, str]]:
        result = self._az(["account", "list", "--output", "json"])
        if result["returncode"] != 0:
            # Do not swallow a command failure as an empty success. A nonzero rc
            # (not logged in, expired) is AUTH, not "zero subscriptions".
            stderr = result.get("stderr", "") or ""
            low = stderr.lower()
            _auth_markers = (
                "az login",
                "not logged in",
                "please run",
                "no subscription found",  # az emits this when the session is gone
                "expired",
            )
            if any(m in low for m in _auth_markers):
                raise ProviderCredentialError(
                    exit_codes.AUTH,
                    "Authentication required: run 'cloudctl login <org>'.",
                )
            raise ProviderCredentialError(
                exit_codes.ERROR,
                stderr.strip() or "az account list failed.",
            )
        try:
            subs = json.loads(result["stdout"] or "[]")
            # A real, successful empty list → genuinely zero subscriptions.
            return [{"id": s["id"], "name": s["name"]} for s in subs]
        except (json.JSONDecodeError, KeyError, ValueError):
            raise ProviderCredentialError(
                exit_codes.ERROR,
                "Unexpected response from az account list.",
            )

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
            from ..utils import console

            console.print(
                "[yellow]Warning: could not query Azure RBAC assignments "
                f"for subscription {account_id}. Defaulting to Contributor.[/]"
            )
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
        # Side-effect free: we do NOT run `az account set` (which would mutate
        # the user's global default subscription and race across concurrent
        # invocations). Subscription selection is passed per-invocation: the
        # `--subscription` flag on this read-only token fetch, and the
        # (ARM|AZURE)_SUBSCRIPTION_ID env vars returned below.

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
            # Do NOT print prose — the exec/CLI layer renders from the code.
            raise ProviderCredentialError(
                exit_codes.AUTH,
                "Authentication required: run 'cloudctl login <org>'.",
            )

        try:
            token_data = json.loads(token_result["stdout"])
            access_token = token_data["accessToken"]
        except (json.JSONDecodeError, KeyError):
            raise ProviderCredentialError(
                exit_codes.ERROR,
                "Unexpected token response from Azure CLI.",
            )

        tenant_id = org.get("tenant_id", token_data.get("tenant", ""))

        creds = {
            "AZURE_SUBSCRIPTION_ID": account,
            "AZURE_TENANT_ID": tenant_id,
            # Terraform / OpenTofu use the ARM_* prefix. These target the
            # azurerm provider and Azure SDKs, NOT the bare `az` CLI (see the
            # class docstring's scope note).
            "ARM_SUBSCRIPTION_ID": account,
            "ARM_TENANT_ID": tenant_id,
            "ARM_ACCESS_TOKEN": access_token,
        }

        # Honest injection: only when the org config supplies a COMPLETE
        # service-principal credential set do we emit the AZURE_CLIENT_* vars
        # that `az` and azure-identity's EnvironmentCredential actually honor —
        # this is what makes a bare `az` command run under the injected identity
        # instead of the ambient login. We NEVER invent SP creds.
        sp = self._sp_creds(org)
        if sp:
            creds["AZURE_CLIENT_ID"] = sp["client_id"]
            creds["AZURE_CLIENT_SECRET"] = sp["client_secret"]
            creds["AZURE_TENANT_ID"] = sp["tenant_id"]
            creds["ARM_TENANT_ID"] = sp["tenant_id"]

        # When a token is present, tell azurerm to use it directly rather than
        # shelling out to the ambient `az` CLI login (which would be the wrong
        # identity for exec-style injection).
        if access_token:
            creds["ARM_USE_CLI"] = "false"

        return creds

    def get_unsets(self) -> str:
        return "\n".join(f"unset {v}" for v in self._ENV_VARS)

    def logout(self, org: Dict[str, Any]) -> int:
        result = self._az(["logout"])
        return result["returncode"]
