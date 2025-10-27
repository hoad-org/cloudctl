# file: tests/test_cli_config.py
from __future__ import annotations

from awsctl import cli


def test_config_sync_dispatch(monkeypatch):
    called = {"v": 0}

    def _fake_sync():
        called["v"] += 1
        return 0

    monkeypatch.setattr("awsctl.core.cmd_config_sync", _fake_sync)
    rc = cli.main(["config", "sync"])
    assert rc == 0
    assert called["v"] == 1
