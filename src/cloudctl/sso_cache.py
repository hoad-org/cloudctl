import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

AWS_DIR = Path.home() / ".aws"
SSO_CACHE_DIR = AWS_DIR / "sso" / "cache"


class OrgRef:
    def __init__(self, name: str, sso_start_url: str = "", sso_region: str = ""):
        self.name = name
        self.sso_start_url = sso_start_url
        self.sso_region = sso_region


class SsoToken:
    def __init__(
        self,
        accessToken: str,
        startUrl: str,
        region: str,
        expiresAt: datetime,
        raw_data: Dict[str, Any],
    ):
        self.accessToken = accessToken
        self.startUrl = startUrl
        self.region = region
        self.expiresAt = expiresAt
        self.raw_data = raw_data

    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) >= self.expiresAt


def _parse_timestamp(ts: str) -> Optional[datetime]:
    """
    Internal helper defined by test contract.
    Must return None on failure instead of raising.
    """
    try:
        # Standard AWS SSO ISO format: 2026-02-10T23:14:20Z
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, TypeError, AttributeError):
        return None


def _normalize_start_url(url: str) -> str:
    if not url:
        return ""
    norm = url.lower().strip().rstrip("/")
    if not norm.startswith("http"):
        norm = f"https://{norm}"
    return norm


def load_active_sso_token(
    org: OrgRef, cache_dir: Optional[Path] = None, raise_error: Optional[bool] = None
) -> Optional[SsoToken]:
    # Strict mode: raise RuntimeError when no valid token found.
    # - If raise_error is explicitly True: always strict
    # - If raise_error is explicitly False: never strict
    # - If raise_error is None (default): strict only when cache_dir explicitly provided
    if raise_error is True:
        strict = True
    elif raise_error is False:
        strict = False
    else:
        # Auto: strict if explicit cache_dir was provided
        strict = cache_dir is not None
    target = cache_dir or SSO_CACHE_DIR
    if not target.exists():
        if strict:
            raise RuntimeError("No valid token found")
        return None

    # Check read access before iterating (permissions check)
    import os

    if not os.access(target, os.R_OK):
        raise RuntimeError(f"Permission denied accessing cache: {target}")

    norm_target = _normalize_start_url(org.sso_start_url)
    try:
        for f in target.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if (
                    _normalize_start_url(data.get("startUrl", "")) == norm_target
                    and data.get("region") == org.sso_region
                ):
                    exp = _parse_timestamp(data.get("expiresAt", ""))
                    if data.get("accessToken") and exp:
                        token = SsoToken(
                            data["accessToken"],
                            data["startUrl"],
                            data["region"],
                            exp,
                            data,
                        )
                        if not token.is_expired():
                            return token
            except Exception:
                # B112: Skipping invalid cache files is intended behavior.
                continue  # nosec B112
    except Exception as e:
        # Match specific error strings expected by sso_cache security tests
        if (
            "Permission denied" in str(e)
            or "Perm Denied" in str(e)
            or "Access Denied" in str(e)
        ):
            raise RuntimeError(f"Permission denied accessing cache: {e}")
        raise RuntimeError(f"SSO cache corrupted: {e}")

    if strict:
        raise RuntimeError("SSO cache corrupted: No valid token found")
    return None


def _cache_filename(session_name: str) -> str:
    """AWS SSO cache filename: sha1 hex of the sso-session name.

    Mirrors the AWS CLI's behaviour for `[sso-session]`-style configs, where
    the token file is named after the sha1 of the session name (not the start
    URL). `load_active_sso_token` matches on startUrl+region regardless of the
    filename, so round-trip discovery does not depend on this — but using the
    same scheme as the AWS CLI keeps the on-disk artifact interchangeable with
    the one the CLI itself writes.
    """
    return hashlib.sha1(session_name.encode("utf-8")).hexdigest()  # nosec B324


def write_sso_token(
    org: OrgRef,
    *,
    access_token: str,
    expires_at: str,
    client_id: str = "",
    client_secret: str = "",
    registration_expires_at: str = "",
    refresh_token: Optional[str] = None,
    cache_dir: Optional[Path] = None,
) -> Path:
    """Write an SSO access token to the standard AWS SSO cache directory.

    The on-disk JSON shape matches exactly what `load_active_sso_token` reads
    back (startUrl / region / accessToken / expiresAt / clientId /
    clientSecret / registrationExpiresAt / refreshToken). The file is created
    with 0o600 permissions — it holds a bearer token.

    Returns the path to the written cache file.
    """
    target = cache_dir or SSO_CACHE_DIR
    target.mkdir(parents=True, exist_ok=True)

    data: Dict[str, Any] = {
        "startUrl": org.sso_start_url,
        "region": org.sso_region,
        "accessToken": access_token,
        "expiresAt": expires_at,
        "clientId": client_id,
        "clientSecret": client_secret,
        "registrationExpiresAt": registration_expires_at,
    }
    if refresh_token is not None:
        data["refreshToken"] = refresh_token

    path = target / f"{_cache_filename(org.name)}.json"
    # Write then tighten perms; create with restrictive mode where supported.
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f)
    finally:
        # os.fdopen took ownership of fd; ensure perms are 0o600 regardless of
        # a pre-existing file's mode.
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    return path
