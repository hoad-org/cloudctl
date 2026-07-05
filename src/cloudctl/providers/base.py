import shlex
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class ProviderCredentialError(Exception):
    """
    Raised by a provider's get_credentials/list_accounts when credential
    acquisition fails, carrying a classified exit code so the CLI/exec layer
    can render a single, *faithful* message and set the right process exit
    status.

    ``code`` uses the numeric scheme in ``cloudctl.exit_codes``:
        1 ERROR      general / uncategorised failure
        2 AUTH       authentication required (no/expired SSO session)
        3 NOT_FOUND   invalid org / account / role
        4 DENIED      permission / access denied (real reason, not "auth")

    The provider does NOT print prose — it classifies the failure and hands the
    code + message up. The exec/CLI layer owns rendering. This is what stops a
    DENIED (Forbidden) being misreported downstream as an AUTH ("no SSO
    session") failure.
    """

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code: int = code
        self.message: str = message


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
        self,
        org: Dict[str, Any],
        account: str,
        role: str,
        region: str,
        token: Optional[Any] = None,
    ) -> Dict[str, str]:
        """Return env var dict suitable for subprocess injection or shell export.

        ``token`` is an optional pre-obtained session token. When supplied (the
        ``--no-cache`` in-memory path), the provider MUST use it directly and
        skip any on-disk token lookup; when ``None`` it behaves exactly as
        before (loads from the provider's own cache). Providers for which a
        pre-obtained token is meaningless simply ignore it.
        """
        ...

    def authenticate_in_memory(self, org: Dict[str, Any]) -> Optional[Any]:
        """Acquire a session token WITHOUT writing it to disk.

        Returns an in-memory token object (exposing at least ``.accessToken``
        and ``.expiresAt``) suitable to pass back into ``get_credentials(...,
        token=...)``, so a full credential flow can run with nothing persisted
        by cloudctl. This is the ``--no-cache`` acquisition path.

        Default: not implemented. Providers whose tokens are owned by the
        underlying cloud CLI (gcloud/az) — i.e. cloudctl never writes them —
        have no in-memory token to hand back and leave this unimplemented.
        """
        raise NotImplementedError(
            "This provider does not support in-memory (--no-cache) authentication."
        )

    @abstractmethod
    def get_unsets(self) -> str:
        """Return newline-separated 'unset VAR' lines for this provider's env vars."""
        ...

    @abstractmethod
    def logout(self, org: Dict[str, Any]) -> int:
        """Terminate the active session. Returns exit code."""
        ...

    def get_identity(self, org: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """
        Return the LIVE, verified caller identity for the active session, or
        None if it cannot be verified.

        This is a *contract of honesty*: implementations MUST query the cloud
        (e.g. `sts get-caller-identity`, `az account show`) and report what the
        cloud says the identity actually is. They must NEVER fabricate a result
        or echo back stored/config context — an unverifiable identity returns
        None, never a guess. The shape is provider-specific but always a flat
        dict of str→str (e.g. AWS: {"account","arn","user_id"}).

        Default: None (provider has not implemented live identity resolution).
        """
        return None

    def az_uses_injected_identity(self, org: Dict[str, Any]) -> bool:
        """
        Return True only when this provider's get_credentials will emit
        credentials that the bare cloud CLI actually runs under (i.e. the child
        command executes as the injected identity, not the ambient login).

        Default False. Only the Azure provider overrides this, and only when
        service-principal creds are configured — see AzureProvider. The exec
        layer queries this to warn when a bare `az` would silently run under the
        ambient login instead of the injected identity.
        """
        return False

    def get_token_expiry(self, org: Dict[str, Any]) -> "Optional[Any]":
        """
        Return the expiry datetime for the active session, or None if unknown.

        The default implementation calls load_token() and checks for an
        expiresAt attribute (AWS SSO token pattern).  Providers that carry
        expiry information in a different form should override this method.

        Returns a timezone-aware datetime.datetime, or None.
        """

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
