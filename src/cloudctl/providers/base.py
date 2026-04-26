import shlex
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class CloudProvider(ABC):
    """
    Abstract base for cloud identity providers.

    Each provider maps the five cloud-specific operations —
    login, token check, account list, role list, credential fetch —
    behind a uniform interface so the interactive layer and shell
    wrapper need know nothing about the underlying cloud.

    Account shape contract:
        list_accounts() returns List[{"id": str, "name": str}]

    Credential shape contract:
        get_credentials() returns Dict[str, str] of env var name → value.
        get_exports() formats those as "export K=V" shell lines.
        get_unsets() formats the matching "unset K" shell lines.
    """

    @abstractmethod
    def login(self, org: Dict[str, Any]) -> int:
        """Initiate interactive authentication. Returns exit code."""
        ...

    @abstractmethod
    def load_token(self, org: Dict[str, Any]) -> Optional[Any]:
        """
        Return a live auth token/session object, or None if unauthenticated.
        The token is opaque to callers — pass it back into list_accounts/list_roles.
        """
        ...

    @abstractmethod
    def list_accounts(self, org: Dict[str, Any], token: Any) -> List[Dict[str, str]]:
        """Return [{"id": ..., "name": ...}] for every accessible account/subscription/project."""
        ...

    @abstractmethod
    def list_roles(self, org: Dict[str, Any], token: Any, account_id: str) -> List[str]:
        """Return role/permission-set names available for the given account."""
        ...

    @abstractmethod
    def get_credentials(
        self, org: Dict[str, Any], account: str, role: str, region: str
    ) -> Dict[str, str]:
        """Return env var dict suitable for subprocess injection or shell export."""
        ...

    @abstractmethod
    def get_unsets(self) -> str:
        """Return newline-separated 'unset VAR' lines for this provider's env vars."""
        ...

    @abstractmethod
    def logout(self, org: Dict[str, Any]) -> int:
        """Terminate the active session. Returns exit code."""
        ...

    def get_token_expiry(self, org: Dict[str, Any]) -> "Optional[Any]":
        """
        Return the expiry datetime for the active session, or None if unknown.

        The default implementation calls load_token() and checks for an
        expiresAt attribute (AWS SSO token pattern).  Providers that carry
        expiry information in a different form should override this method.

        Returns a timezone-aware datetime.datetime, or None.
        """
        from datetime import datetime, timezone

        try:
            token = self.load_token(org)
            if token and hasattr(token, "expiresAt"):
                return token.expiresAt
        except Exception:
            pass
        return None

    def get_exports(
        self, org: Dict[str, Any], account: str, role: str, region: str
    ) -> str:
        """
        Default implementation: call get_credentials() and format as shell exports.
        Providers that need side-effects (e.g. writing a config file) can override.
        """
        creds = self.get_credentials(org, account, role, region)
        return "\n".join(f"export {k}={shlex.quote(v)}" for k, v in creds.items())
