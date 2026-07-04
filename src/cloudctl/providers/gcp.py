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
                   GCP has NO runtime role-switching the way AWS SSO permission
                   sets do; roles are static IAM bindings on the project. `--role`
                   is therefore NOT a functional credential selector on GCP — the
                   effective permissions come entirely from the IAM policy bound
                   to the authenticated identity. The selected role is retained
                   only for display/audit; see list_roles().
        region   → GCP region (e.g. us-central1, europe-west1)

    Credential injection contract (exec):
        get_credentials() is side-effect free. Project and region selection are
        passed *per invocation* via CLOUDSDK_* env vars — cloudctl never mutates
        the user's global gcloud config (no `gcloud config set`). Both the gcloud
        CLI (CLOUDSDK_AUTH_ACCESS_TOKEN, CLOUDSDK_CORE_PROJECT,
        CLOUDSDK_COMPUTE_REGION) and Google client libraries / ADC
        (GOOGLE_OAUTH_ACCESS_TOKEN, GOOGLE_CLOUD_PROJECT) are covered.

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
        "CLOUDSDK_COMPUTE_REGION",
        "GCLOUD_PROJECT",
        "GOOGLE_OAUTH_ACCESS_TOKEN",
        "CLOUDSDK_AUTH_ACCESS_TOKEN",
    ]

    # ------------------------------------------------------------------ helpers

    def _gcloud(self, args: List[str], capture: bool = True) -> Dict[str, Any]:
        gcloud_bin = shutil.which("gcloud")
        if not gcloud_bin:
            from ..utils import console

            console.print(
                "[red]gcloud CLI not found in PATH. "
                "Install from https://cloud.google.com/sdk/docs/install[/]"
            )
            sys.exit(1)
        # capture=False inherits stdio for interactive auth (browser opens + the
        # user completes consent); capture=True is for parsed, non-interactive queries.
        result = subprocess.run(
            [gcloud_bin] + args,
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
        # Interactive (capture=False): gcloud opens the browser for consent.
        # User identity login
        r1 = self._gcloud(["auth", "login"], capture=False)
        if r1["returncode"] != 0:
            return r1["returncode"]
        # Application Default Credentials — needed by Terraform, SDKs, etc.
        r2 = self._gcloud(["auth", "application-default", "login"], capture=False)
        return r2["returncode"]

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
        Return the expiry of the active gcloud access token.

        Prefer the real expiry when gcloud exposes it: `gcloud auth
        print-access-token --format=json` emits a ``token_expiry`` field
        (RFC3339). If that is available we parse and return it.

        Fallback: older gcloud builds (and the plain, non-JSON token print)
        do not surface an issue/expiry time. GCP OAuth access tokens live
        exactly 3600 s and gcloud refreshes them transparently, so when no
        real expiry is readable we conservatively estimate now + 1 h — this
        estimate only feeds proactive near-threshold re-auth checks, so
        over-estimating expiry would be the only harmful direction, and
        now+1h never does that.
        """
        from datetime import datetime, timezone, timedelta

        # Try to read a real expiry from the JSON token output first.
        json_result = self._gcloud(["auth", "print-access-token", "--format=json"])
        if json_result["returncode"] == 0 and json_result["stdout"].strip():
            try:
                data = json.loads(json_result["stdout"])
                expiry_raw = data.get("token_expiry") or data.get("expiry")
                if expiry_raw:
                    # RFC3339, e.g. "2024-03-15T10:30:00Z" or with offset.
                    normalized = expiry_raw.replace("Z", "+00:00")
                    dt = datetime.fromisoformat(normalized)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt
            except (json.JSONDecodeError, ValueError, KeyError):
                pass

        token = self.load_token(org)
        if not token:
            return None
        # No real expiry available — conservative fallback (see docstring).
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
        # NOTE: `--role` is NOT a functional credential selector on GCP. Unlike
        # AWS SSO permission sets, GCP has no runtime role assumption — the
        # effective permissions are fixed by the IAM policy bound to the
        # authenticated identity on the project. This returns the static
        # configured list purely for display/audit in the picker; selecting a
        # different entry here does NOT change the credentials that
        # get_credentials() emits.
        return list(org.get("roles", ["roles/viewer", "roles/editor", "roles/owner"]))

    def get_credentials(
        self, org: Dict[str, Any], account: str, role: str, region: str
    ) -> Dict[str, str]:
        # Side-effect free: project/region are selected *per invocation* through
        # CLOUDSDK_* env vars below. We deliberately do NOT run
        # `gcloud config set project ...` — mutating the user's global gcloud
        # config violates exec's "without changing context" contract and races
        # across concurrent invocations.

        # Fetch a fresh access token (read-only; no global state change).
        token_result = self._gcloud(["auth", "print-access-token"])
        if token_result["returncode"] != 0:
            from ..utils import console

            console.print(
                "[red]Failed to get GCP access token. "
                "Re-run 'cloudctl login <org>'.[/]"
            )
            sys.exit(1)

        access_token = token_result["stdout"].strip()

        creds = {
            "GOOGLE_CLOUD_PROJECT": account,
            # gcloud CLI reads CLOUDSDK_CORE_PROJECT for project selection
            # per-invocation (no `gcloud config set` needed); many third-party
            # tools use GCLOUD_PROJECT.
            "CLOUDSDK_CORE_PROJECT": account,
            "GCLOUD_PROJECT": account,
            # The gcloud CLI honors CLOUDSDK_AUTH_ACCESS_TOKEN — this is what
            # makes the child `gcloud`/`gsutil` run under the injected identity
            # instead of the ambient login.
            "CLOUDSDK_AUTH_ACCESS_TOKEN": access_token,
            # Google client libraries / ADC honor GOOGLE_OAUTH_ACCESS_TOKEN.
            "GOOGLE_OAUTH_ACCESS_TOKEN": access_token,
        }

        # Region is optional; only inject it when provided so we don't force a
        # region on tools that don't need one.
        if region:
            creds["CLOUDSDK_COMPUTE_REGION"] = region

        return creds

    def get_unsets(self) -> str:
        return "\n".join(f"unset {v}" for v in self._ENV_VARS)

    def logout(self, org: Dict[str, Any]) -> int:
        r1 = self._gcloud(["auth", "revoke", "--all"])
        r2 = self._gcloud(["auth", "application-default", "revoke"])
        return r1["returncode"] or r2["returncode"]
