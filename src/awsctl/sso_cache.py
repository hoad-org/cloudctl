# file: src/awsctl/sso_cache.py
# SPDX-License-Identifier: MIT
"""
SSO token cache reader.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


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
        scheme = scheme.lower()
    except ValueError:
        scheme, rest = "", u

    host, *path_parts = rest.split("/", 1)
    host = host.lower()
    rest = host if not path_parts else host + "/" + path_parts[0]

    out = (scheme + "://" if scheme else "") + rest
    return out[:-1] if out.endswith("/") else out


def _is_expired(expires_at_iso8601: str) -> bool:
    try:
        dt = datetime.fromisoformat(expires_at_iso8601.replace("Z", "+00:00"))
    except Exception:
        return True
    return dt <= datetime.now(timezone.utc)


def load_active_sso_token(
    org: OrgRef, cache_dir: Path | None = None, raise_error: bool = True
) -> Optional[SsoToken]:
    base = cache_dir or (Path.home() / ".aws" / "sso" / "cache")
    want = _normalize_start_url(org.sso_start_url)

    best: tuple[datetime, dict[str, Any]] | None = None

    if not base.exists():
        if not raise_error:
            return None
        msg = f"Token for {org.sso_start_url} does not exist"
        print(msg)
        raise SystemExit(f"Error loading SSO Token: {msg}")

    for p in base.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, FileNotFoundError):
            continue

        start_url = _normalize_start_url(str(data.get("startUrl", "")))
        if start_url != want:
            continue

        file_region = data.get("region")
        if file_region not in (org.sso_region, None):
            continue

        # [FIX] Sanitize token string by stripping whitespace/newlines
        token = str(data.get("accessToken") or "").strip()
        exp = data.get("expiresAt") or ""

        if not token or not exp or _is_expired(exp):
            continue

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

    if not raise_error:
        return None

    msg = f"Token for {org.sso_start_url} does not exist"
    print(msg)
    raise SystemExit(f"Error loading SSO Token: {msg}")
