# file: tests/test_sso_cache.py
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from awsctl.sso_cache import OrgRef, _normalize_start_url, load_active_sso_token


def _write(tmp: Path, name: str, start_url: str, region: str, ttl: int, token: str):
    exp = (datetime.now(timezone.utc) + timedelta(seconds=ttl)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    (tmp / f"{name}.json").write_text(
        json.dumps(
            {
                "startUrl": start_url,
                "region": region,
                "accessToken": token,
                "expiresAt": exp,
            }
        )
    )


def test_normalize():
    assert _normalize_start_url(
        "HTTPS://D-ABC.awsapps.com/start/"
    ) == _normalize_start_url("https://d-ABC.awsapps.com/start")


def test_selects_matching_region(tmp_path: Path):
    # Write OLD token with 3600s TTL
    _write(tmp_path, "old", "https://d-abc.awsapps.com/start", "eu-west-1", 3600, "OLD")
    # Write NEW token with 7200s TTL, ensuring it is "best"
    _write(
        tmp_path, "new", "https://d-abc.awsapps.com/start/", "eu-west-2", 7200, "NEW"
    )

    # 1. Requesting for eu-west-2 should return NEW (it matches region and is newest)
    tok_new = load_active_sso_token(
        OrgRef("o-new", "https://d-abc.awsapps.com/start", "eu-west-2"),
        cache_dir=tmp_path,
    )
    assert tok_new.access_token == "NEW"

    # 2. Requesting for eu-west-1 should return OLD (it's the only one that matches region)
    tok_old = load_active_sso_token(
        OrgRef("o-old", "https://d-abc.awsapps.com/start", "eu-west-1"),
        cache_dir=tmp_path,
    )
    assert tok_old.access_token == "OLD"
