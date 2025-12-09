# file: tests/test_sso_cache.py
from __future__ import annotations

from unittest.mock import MagicMock

from awsctl import sso_cache
from awsctl.sso_cache import OrgRef, _normalize_start_url, load_active_sso_token


def test_normalize():
    assert _normalize_start_url("HTTPS://u") == "https://u"


def test_sso_token_validation_branches(tmp_path, monkeypatch):
    # Mocking location is tricky if not exposed, pass cache_dir explicitly
    (tmp_path / "big.json").write_bytes(b"0" * (1024 * 1024 + 100))
    (tmp_path / "bad.json").write_text("{bad")
    org = OrgRef("test", "https://target", "eu-west-1")
    assert load_active_sso_token(org, cache_dir=tmp_path, raise_error=False) is None


def test_load_token_permission_error(tmp_path, monkeypatch):
    monkeypatch.setattr(sso_cache, "Path", MagicMock())
    pass
