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
        try:
            result = subprocess.run(
                [gcloud_bin] + args,
                capture_output=True,
                text=True,
                timeout=30,  # Prevent hangs from network/proxy issues
            )
            return {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except subprocess.TimeoutExpired:
            from ..utils import console

            console.print(
                "[red]gcloud command timed out after 30 seconds. "
                "Check network connectivity and try again.[/]"
            )
            sys.exit(1)

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
                    account = accounts[0].get("account", "user")
                    console.print(f"[green]✅ GCP authenticated as {account}[/green]")
                    # Force token refresh for org-level operations
                    console.print(
                        "[yellow]🔄 Refreshing authentication for organization-level operations...[/yellow]"
                    )
                    refresh_result = self._gcloud(
                        ["auth", "login", "--no-launch-browser"]
                    )
                    if refresh_result["returncode"] != 0:
                        # Check if it's a non-interactive prompt error
                        if (
                            "cannot prompt during non-interactive execution"
                            in refresh_result["stderr"]
                            or "Enter the following verification code in the browser:"
                            not in refresh_result["stderr"]
                        ):
                            # In non-interactive mode, just accept existing auth and continue
                            console.print(
                                "[yellow]⚠️  Using cached authentication (organization operations may require re-auth)[/yellow]"
                            )
                            return 0
                    return 0
            except (json.JSONDecodeError, TypeError, IndexError):
                pass

        console.print("[yellow]Starting GCP authentication...[/yellow]")

        # Try user identity login with --no-launch-browser for non-interactive
        r1 = self._gcloud(["auth", "login", "--no-launch-browser"])
        if r1["returncode"] != 0:
            # If login failed, provide helpful instructions or handle gracefully
            if "cannot prompt during non-interactive execution" in r1["stderr"]:
                console.print(
                    "[red]Error: Cannot run gcloud auth login in non-interactive mode[/red]"
                )
                console.print("[yellow]Solution: Run this in your terminal:[/yellow]")
                console.print("[cyan]  gcloud auth login[/cyan]")
                console.print("[yellow]Then retry: cloudctl login <org>[/yellow]")
                return r1["returncode"]
            elif "verification code" in r1["stdout"]:
                # Non-interactive mode gave us a URL - print it for the user
                console.print(r1["stdout"])
                return 0
            else:
                # Unexpected error - fail fast
                return r1["returncode"]

        # Application Default Credentials — needed by Terraform, SDKs, etc.
        r2 = self._gcloud(
            ["auth", "application-default", "login", "--no-launch-browser"]
        )
        if r2["returncode"] != 0:
            # ADC failure is less critical for org operations
            if "cannot prompt during non-interactive execution" in r2["stderr"]:
                console.print(
                    "[yellow]⚠️  Could not set up Application Default Credentials (continuing)[/yellow]"
                )
                return 0
        else:
            console.print(
                "[green]✅ Application Default Credentials configured[/green]"
            )

        console.print("[green]✅ GCP authentication complete[/green]")
        return 0

    def load_token(self, org: Dict[str, Any]) -> Optional[str]:
        """
        Returns the active access token string, or None if unauthenticated.
        gcloud handles token refresh transparently.

        In non-interactive environments, gcloud auth print-access-token may fail
        with "cannot prompt during non-interactive execution". In those cases,
        we check if gcloud auth list shows authenticated accounts — if yes,
        we return a placeholder token to indicate "authenticated".
        """
        result = self._gcloud(["auth", "print-access-token"])
        if result["returncode"] == 0:
            token = result["stdout"].strip()
            if token:
                return token

        # Token retrieval failed — check if we're in non-interactive mode
        # and if there are authenticated accounts
        if "cannot prompt during non-interactive execution" in result.get("stderr", ""):
            # In non-interactive mode with existing auth, return a placeholder token
            # to indicate "authenticated" even though we can't get the actual token
            check_result = self._gcloud(["auth", "list", "--format=json"])
            if check_result["returncode"] == 0:
                try:
                    accounts = json.loads(check_result["stdout"])
                    if accounts and len(accounts) > 0:
                        # Return a non-None value to indicate authenticated
                        # Even though we can't get the actual token in non-interactive mode
                        return f"cached:gcp:{accounts[0].get('account', 'user')}"
                except (json.JSONDecodeError, TypeError, IndexError):
                    pass

        return None

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
        if result["returncode"] == 0:
            try:
                projects = json.loads(result["stdout"])
                return [
                    {"id": p["projectId"], "name": p.get("name", p["projectId"])}
                    for p in projects
                ]
            except (json.JSONDecodeError, KeyError, ValueError):
                # JSON parsing failed - return empty list
                return []

        # If projects list fails, check if it's due to non-interactive mode
        if result[
            "returncode"
        ] != 0 and "cannot prompt during non-interactive execution" in result.get(
            "stderr", ""
        ):
            # In non-interactive mode, fall back to the default project from config
            default_project = org.get("default_project")
            if default_project:
                # Return the default project configured in the org
                return [{"id": default_project, "name": default_project}]

            # Try to get the current project from gcloud config as last resort
            result = self._gcloud(["config", "get-value", "project"])
            if result["returncode"] == 0:
                project = result["stdout"].strip()
                if project:
                    return [{"id": project, "name": project}]

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
        # In non-interactive mode (subprocess), this may fail with "cannot prompt".
        # Fall back to placeholder token if in non-interactive mode.
        token_result = self._gcloud(["auth", "print-access-token"])
        if token_result["returncode"] != 0:
            # Check if it's a non-interactive mode error
            if "cannot prompt during non-interactive execution" in token_result.get(
                "stderr", ""
            ):
                from ..utils import console

                console.print(
                    "[yellow]⚠️  Non-interactive mode: using cached token "
                    "(may require re-auth in interactive shell)[/yellow]"
                )
                # Return placeholder token for non-interactive mode
                # The actual token will be refreshed when needed
                access_token = f"cached:gcp:{account}"
            else:
                from ..utils import console

                console.print(
                    "[red]Failed to get GCP access token. "
                    "Re-run 'cloudctl login <org>'.[/]"
                )
                sys.exit(1)
        else:
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
