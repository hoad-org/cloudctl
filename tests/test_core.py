# file: tests/test_core.py
import configparser
import json

from awsctl import core


def test_write_target_profile(monkeypatch):
    calls = []
    monkeypatch.setattr(core, "aws_configure_set", lambda p, k, v: calls.append((p, k, v)))
    profile = core.write_target_profile(
        {"name": "x", "sso_start_url": "u", "sso_region": "r"},
        "111111111111",
        "AdministratorAccess",
        "eu-west-2",
    )
    assert profile.endswith("eu-west-2")
    keys = [k for _, k, _ in calls]
    assert set(keys) >= {"sso_start_url", "sso_region", "region", "sso_account_id", "sso_role_name"}


def test_token_reader_handles_missing_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(core.pathlib.Path, "home", lambda: tmp_path)
    assert core.get_valid_sso_access_token("x", "y") is None


def test_sso_listing_parses(monkeypatch):
    out = type(
        "Proc",
        (),
        {
            "stdout": json.dumps({"accountList": [{"accountId": "1", "accountName": "A"}]}),
            "returncode": 0,
        },
    )
    monkeypatch.setattr("subprocess.run", lambda *a, **k: out)
    res = core.sso_list_accounts("T", "eu-west-2", "sso-x")
    assert res and res[0]["accountId"] == "1"


def test_config_sync_writes_sections(tmp_path, monkeypatch):
    # Redirect ~/.aws/config
    monkeypatch.setattr(core, "AWS_DIR", tmp_path / ".aws")
    monkeypatch.setattr(core, "AWS_CONFIG", core.AWS_DIR / "config")
    org = {
        "name": "dev",
        "sso_start_url": "https://d-x.awsapps.com/start",
        "sso_region": "eu-west-2",
        "default_region": "eu-west-2",
    }
    prof = core.ensure_sso_base_profile(org)
    assert prof == "sso-dev"
    assert core.AWS_CONFIG.exists()
    cfg = configparser.RawConfigParser()
    cfg.read(core.AWS_CONFIG)
    assert "sso-session dev" in cfg
    assert "profile sso-dev" in cfg
