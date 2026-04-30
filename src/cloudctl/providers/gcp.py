import json
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional

from .base import CloudProvider


class GcpProvider(CloudProvider):
    """
    Google Cloud Platform provider via the gcloud CLI.

    Concepts mapped to cloudctl's cloud-agnostic model:
        account  → GCP Project (id = projectId, name = display name)
        role     → IAM role (e.g. roles/viewer, roles/editor)
                   GCP has no runtime role-switching via SSO; roles are IAM bindings.
                   The "selected role" is stored in context for audit purposes.
        region   → GCP region (e.g. us-central1, europe-west1)

    Requires: gcloud CLI installed and on PATH.

    Authentication uses Application Default Credentials (ADC).
    Run 'cloudctl login <org>' once to call both:
        gcloud auth login                        (user identity)
        gcloud auth application-default login    (ADC for SDKs/Terraform)

    Org config keys:
        provider:        "gcp"
        allowed_regions: list of permitted GCP region names
        default_region:  default region
        roles:           list of IAM role names shown in the picker
                         (default: ["roles/viewer", "roles/editor", "roles/owner"])
        sensitive_roles: roles requiring break-glass logging
        preferred_roles: roles shown first in the picker
    """

    _ENV_VARS = [
        "GOOGLE_CLOUD_PROJECT",
        "CLOUDSDK_CORE_PROJECT",
        "GCLOUD_PROJECT",
        "GOOGLE_OAUTH_ACCESS_TOKEN",
    ]

    # ------------------------------------------------------------------ helpers

    def _gcloud(self, args: List[str]) -> Dict[str, Any]:
        gcloud_bin = shutil.which("gcloud")
        if not gcloud_bin:
            from ..utils import console

            console.print(
                "[red]gcloud CLI not found in PATH. "
                "Install from https://cloud.google.com/sdk/docs/install[/]"
            )
            sys.exit(1)
        result = subprocess.run(
            [gcloud_bin] + args,
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
        """Authenticate with GCP via gcloud.

        Checks if already authenticated before attempting login.
        Forces token refresh for organization-level operations.
        For non-interactive environments, provides browser URL for MFA.
        """
        from ..utils import console

        # First check if already authenticated
        check_result = self._gcloud(["auth", "list", "--format=json"])
        if check_result["returncode"] == 0:
            try:
                accounts = json.loads(check_result["stdout"])
                if accounts and len(accounts) > 0:
                    account = accounts[0].get('account', 'user')
                    console.print(f"[green]✅ GCP authenticated as {account}[/green]")
                    # Force token refresh for org-level operations
                    console.print("[yellow]🔄 Refreshing authentication for organization-level operations...[/yellow]")
                    refresh_result = self._gcloud(["auth", "login", "--no-launch-browser"])
                    if refresh_result["returncode"] != 0:
                        # Check if it's a non-interactive prompt error
                        if "cannot prompt during non-interactive execution" in refresh_result["stderr"] or \
                           "Enter the following verification code in the browser:" not in refresh_result["stderr"]:
                            # In non-interactive mode, just accept existing auth and continue
                            console.print("[yellow]⚠️  Using cached authentication (organization operations may require re-auth)[/yellow]")
                            return 0
                    return 0
            except (json.JSONDecodeError, TypeError, IndexError):
                pass

        console.print("[yellow]Starting GCP authentication...[/yellow]")

        # Try user identity login with --no-launch-browser for non-interactive
        r1 = self._gcloud(["auth", "login", "--no-launch-browser"])
        if r1["returncode"] != 0:
            # If login failed, provide helpful instructions
            if "cannot prompt during non-interactive execution" in r1["stderr"]:
                console.print("[red]Error: Cannot run gcloud auth login in non-interactive mode[/red]")
                console.print("[yellow]Solution: Run this in your terminal:[/yellow]")
                console.print("[cyan]  gcloud auth login[/cyan]")
                console.print("[yellow]Then retry: cloudctl login <org>[/yellow]")
                return r1["returncode"]
            elif "verification code" in r1["stdout"]:
                # Non-interactive mode gave us a URL - print it for the user
                console.print(r1["stdout"])
                return 0

        # Application Default Credentials — needed by Terraform, SDKs, etc.
        r2 = self._gcloud(["auth", "application-default", "login", "--no-launch-browser"])
        if r2["returncode"] != 0:
            # ADC failure is less critical for org operations
            if "cannot prompt during non-interactive execution" in r2["stderr"]:
                console.print("[yellow]⚠️  Could not set up Application Default Credentials (continuing)[/yellow]")
                return 0
        else:
            console.print("[green]✅ Application Default Credentials configured[/green]")

        console.print("[green]✅ GCP authentication complete[/green]")
        return 0

    def load_token(self, org: Dict[str, Any]) -> Optional[str]:
        """
        Returns the active access token string, or None if unauthenticated.
        gcloud handles token refresh transparently.
        """
        result = self._gcloud(["auth", "print-access-token"])
        if result["returncode"] != 0:
            return None
        token = result["stdout"].strip()
        return token if token else None

    def get_token_expiry(self, org: Dict[str, Any]) -> "Optional[Any]":
        """
        GCP access tokens issued by gcloud expire in ~1 hour; gcloud refreshes
        them automatically.  We estimate expiry as now+1h when a valid token
        exists, so cloudctl watch can proactively re-auth near the threshold.
        """
        from datetime import datetime, timezone, timedelta

        token = self.load_token(org)
        if not token:
            return None
        # GCP ADC tokens last exactly 3600 s; we can't read the exact issue time
        # without parsing gcloud's credential cache, so we estimate conservatively.
        return datetime.now(timezone.utc) + timedelta(hours=1)

    def list_accounts(self, org: Dict[str, Any], token: Any) -> List[Dict[str, str]]:
        result = self._gcloud(["projects", "list", "--format=json"])
        if result["returncode"] != 0:
            return []
        try:
            projects = json.loads(result["stdout"])
            return [
                {"id": p["projectId"], "name": p.get("name", p["projectId"])}
                for p in projects
            ]
        except (json.JSONDecodeError, KeyError, ValueError):
            return []

    def list_roles(self, org: Dict[str, Any], token: Any, account_id: str) -> List[str]:
        # GCP roles are IAM bindings, not runtime-switchable.
        # We use the configured list for display/audit; the actual permissions
        # are determined by IAM policies on the project.
        return list(org.get("roles", ["roles/viewer", "roles/editor", "roles/owner"]))

    def get_credentials(
        self, org: Dict[str, Any], account: str, role: str, region: str
    ) -> Dict[str, str]:
        # Set the active project (side-effect on gcloud config).
        set_result = self._gcloud(["config", "set", "project", account])
        if set_result["returncode"] != 0:
            from ..utils import console

            console.print(f"[red]Failed to set GCP project {account}[/]")
            sys.exit(1)

        # Fetch a fresh access token.
        token_result = self._gcloud(["auth", "print-access-token"])
        if token_result["returncode"] != 0:
            from ..utils import console

            console.print(
                "[red]Failed to get GCP access token. "
                "Re-run 'cloudctl login <org>'.[/]"
            )
            sys.exit(1)

        access_token = token_result["stdout"].strip()

        return {
            "GOOGLE_CLOUD_PROJECT": account,
            # gcloud SDK reads CLOUDSDK_CORE_PROJECT; many third-party tools use GCLOUD_PROJECT
            "CLOUDSDK_CORE_PROJECT": account,
            "GCLOUD_PROJECT": account,
            # Terraform google provider / SDKs use this to skip re-fetching a token
            "GOOGLE_OAUTH_ACCESS_TOKEN": access_token,
        }

    def get_unsets(self) -> str:
        return "\n".join(f"unset {v}" for v in self._ENV_VARS)

    def logout(self, org: Dict[str, Any]) -> int:
        r1 = self._gcloud(["auth", "revoke", "--all"])
        r2 = self._gcloud(["auth", "application-default", "revoke"])
        return r1["returncode"] or r2["returncode"]
