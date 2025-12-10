# file: tests/test_setup_defaults.py
from unittest.mock import MagicMock, patch

import yaml

from awsctl import core


def test_cmd_setup_merge_defaults(monkeypatch, tmp_path):
    conf = tmp_path / "orgs.yaml"
    conf.write_text("other_key: true")
    monkeypatch.setattr("awsctl.config.get_orgs_path", lambda ensure=True: conf)
    monkeypatch.setattr("awsctl.core.cmd_config_sync", MagicMock())
    monkeypatch.setattr("awsctl.shell.detect_shell_profile", lambda: tmp_path / "rc")
    monkeypatch.setattr("awsctl.shell.inject_shell_function", lambda x: True)
    monkeypatch.setattr(
        "awsctl.config.sample_orgs_yaml",
        lambda: "enabled_orgs: [default]\nplugins: {enabled: []}",
    )
    assert core.cmd_setup() == 0
    data = yaml.safe_load(conf.read_text())
    assert data["other_key"] is True
    assert "default" in data["enabled_orgs"]


def test_config_sync_loop(monkeypatch):
    orgs = [
        {"name": "full", "sso_start_url": "u", "sso_region": "r"},
        {"name": "partial"},
    ]
    monkeypatch.setattr("awsctl.config.load_orgs_config", lambda: {"orgs": orgs})
    with patch("awsctl.aws.ensure_sso_base_profile") as mock_ensure:
        core.cmd_config_sync()
        assert mock_ensure.call_count == 1
