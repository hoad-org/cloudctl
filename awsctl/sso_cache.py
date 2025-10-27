# file: awsctl/sso_cache.py
# SPDX-License-Identifier: MIT
"""
SSO token cache reader.

- Selects the newest, non-expired token whose startUrl matches the org.
- Normalizes startUrl for case and a trailing slash.
- Keeps dataclass shapes used by tests.
- On missing/expired token, prints a plain error line to **stdout** and raises
  SystemExit with a detailed message. This satisfies the smoke script which
  greps for 'Token.*does not exist' in stdout or logs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class OrgRef:
    name: str
    sso_start_url: str
    sso_region: str


@dataclass(frozen=True)
class SsoToken:
    access_token: str
    start_url: str
    region: str
    expires_at: datetime
    raw: dict[str, Any]


def _normalize_start_url(url: str) -> str:
    """Case-fold host and scheme, and strip a trailing slash for reliable comparisons."""
    u = (url or "").strip()
    if not u:
        return ""

    try:
        scheme, rest = u.split("://", 1)
        # Lowercase the scheme
        scheme = scheme.lower()
    except ValueError:
        # No scheme present; treat whole string as host+path
        scheme, rest = "", u

    # Split host and path
    host, *path_parts = rest.split("/", 1)
    # Lowercase the host
    host = host.lower()
    rest = host if not path_parts else host + "/" + path_parts[0]

    # Reconstruct with lowercased scheme
    out = (scheme + "://" if scheme else "") + rest

    # Drop a single trailing slash
    return out[:-1] if out.endswith("/") else out


def _is_expired(expires_at_iso8601: str) -> bool:
    """Return True if expiresAt has passed."""
    try:
        dt = datetime.fromisoformat(expires_at_iso8601.replace("Z", "+00:00"))
    except Exception:
        return True
    return dt <= datetime.now(timezone.utc)


def load_active_sso_token(org: OrgRef, cache_dir: Path | None = None) -> SsoToken:
    """
    Load the active SSO token for `org` from the AWS CLI cache.

    Search directory: ~/.aws/sso/cache  (or `cache_dir` if provided)
    Match rule: startUrl normalized equals org.sso_start_url normalized.
    Choose the newest non-expired token when multiple match.
    """
    base = cache_dir or (Path.home() / ".aws" / "sso" / "cache")
    want = _normalize_start_url(org.sso_start_url)

    best: tuple[datetime, dict[str, Any]] | None = None

    if not base.exists():
        msg = f"Token for {org.sso_start_url} does not exist"
        # Print a plain line to stdout so smoke tests can grep it.
        print(msg)
        raise SystemExit(f"Error loading SSO Token: {msg}")

    for p in base.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue

        start_url = _normalize_start_url(str(data.get("startUrl", "")))
        if start_url != want:
            continue

        # Filter by region. The cache file must match the org's region
        # or have no region specified (which is a valid case).
        file_region = data.get("region")
        if file_region not in (org.sso_region, None):
            continue

        token = data.get("accessToken") or ""
        exp = data.get("expiresAt") or ""
        if not token or not exp or _is_expired(exp):
            continue

        # Prefer region from cache else fallback to org default
        region = data.get("region") or org.sso_region
        expires_at = datetime.fromisoformat(exp.replace("Z", "+00:00"))

        if best is None or expires_at > best[0]:
            best = (
                expires_at,
                {
                    "accessToken": token,
                    "startUrl": start_url,
                    "region": region,
                    "expiresAt": exp,
                    "_raw": data,
                },
            )

    if best:
        expires_at, payload = best
        return SsoToken(
            access_token=str(payload["accessToken"]),
            start_url=str(payload["startUrl"]),
            region=str(payload["region"]),
            expires_at=expires_at,
            raw=dict(payload["_raw"]),
        )

    msg = f"Token for {org.sso_start_url} does not exist"
    # Print a plain line to stdout so the smoke script matches it reliably.
    print(msg)
    raise SystemExit(f"Error loading SSO Token: {msg}")
