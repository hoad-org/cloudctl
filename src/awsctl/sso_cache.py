# file: src/awsctl/sso_cache.py
# SPDX-License-Identifier: MIT
"""
SSO token cache reader.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from awsctl.utils import debug_print

EXPIRY_BUFFER_SEC = 15


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
    u = (url or "").strip()
    if not u:
        return ""

    if "://" not in u:
        u = "https://" + u

    try:
        scheme, rest = u.split("://", 1)
        scheme = scheme.lower()
    except ValueError:
        scheme, rest = "https", u

    host, *path_parts = rest.split("/", 1)
    host = host.lower()
    rest = host if not path_parts else host + "/" + path_parts[0]

    out = (scheme + "://" if scheme else "") + rest
    return out[:-1] if out.endswith("/") else out


def _parse_timestamp(ts: str) -> datetime | None:
    try:
        # Normalize Z to +00:00
        ts = ts.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)

        # [FIX] PYBH-0049: Ensure offset-aware for comparison
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        try:
            base, _, tail = ts.partition(".")
            if "+" in tail:
                dt = datetime.fromisoformat(base + "+00:00")
            else:
                dt = datetime.fromisoformat(base + "+00:00")

            # Ensure aware
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            debug_print(f"Failed fallback timestamp parse: {ts}")

    except Exception as e:
        debug_print(f"Timestamp parse failed for '{ts}': {e}")

    return None


def _is_expired(expires_at_value: Any) -> bool:
    if not isinstance(expires_at_value, str):
        return True

    dt = _parse_timestamp(expires_at_value)
    if not dt:
        return True

    return dt <= (datetime.now(timezone.utc) + timedelta(seconds=EXPIRY_BUFFER_SEC))


def load_active_sso_token(
    org: OrgRef, cache_dir: Path | None = None, raise_error: bool = True
) -> Optional[SsoToken]:
    base = cache_dir or (Path.home() / ".aws" / "sso" / "cache")
    want = _normalize_start_url(org.sso_start_url)

    best: tuple[datetime, dict[str, Any]] | None = None

    if not base.exists():
        if not raise_error:
            return None
        raise RuntimeError(f"Token cache dir not found: {base}")

    try:
        files = list(base.glob("*.json"))
    except OSError:
        if raise_error:
            raise RuntimeError(f"Permission denied accessing cache: {base}") from None
        return None

    for p in files:
        try:
            with p.open("r", encoding="utf-8") as f:
                content = f.read(1024 * 1024 + 1)

            if len(content) > 1024 * 1024:
                continue

            data = json.loads(content)
            # [FIX] PYBH-0038: Ensure data is a dict
            if not isinstance(data, dict):
                continue
        except (json.JSONDecodeError, UnicodeDecodeError, FileNotFoundError, OSError):
            continue

        try:
            start_url = _normalize_start_url(str(data.get("startUrl", "")))
            if start_url != want:
                continue

            file_region = data.get("region")
            if file_region not in (org.sso_region, None):
                continue

            token = str(data.get("accessToken") or "").strip()
            exp = data.get("expiresAt") or ""

            if not token or not exp or _is_expired(exp):
                continue

            region = data.get("region") or org.sso_region
            expires_at = _parse_timestamp(str(exp))

            if not expires_at:
                continue

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
        except AttributeError:
            continue

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

    raise RuntimeError(f"No valid token found for {org.sso_start_url}")
