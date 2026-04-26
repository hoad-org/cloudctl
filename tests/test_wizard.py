# file: tests/test_wizard.py
"""Tests for the interactive setup wizard."""

from unittest.mock import MagicMock, patch

import yaml
from cloudctl import config, core, shell, wizard
from cloudctl.wizard import inquirer


# ---------------------------------------------------------------------------
# Helpers — build sequential mocks for multi-call inquirer prompts
# ---------------------------------------------------------------------------


def _seq_mock(values):
    """Return an inquirer-compatible factory whose .execute() yields *values* in order."""
    it = iter(values)

    def factory(**kw):
        m = MagicMock()
        m.execute.return_value = next(it)
        return m

    return factory


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_wizard_happy_path(monkeypatch, tmp_path, mock_rich_console):
    """Full run with one AWS org from registry — config written, shell installed."""

    # ── filesystem ──────────────────────────────────────────────────────────
    monkeypatch.setattr(config, "HOME", tmp_path)
    orgs_file = tmp_path / ".cloudctl" / "orgs.yaml"
    monkeypatch.setattr(config, "ORGS_USER", orgs_file)

    mock_org = {
        "name": "engineering",
        "provider": "aws",
        "sso_start_url": "https://d-xxxx.awsapps.com/start",
        "sso_region": "us-east-1",
        "default_region": "us-east-1",
    }

    # ── registry ─────────────────────────────────────────────────────────────
    # _load_registry_choices() calls registry.get_choices() internally
    monkeypatch.setattr(
        "cloudctl.wizard._load_registry_choices",
        lambda: [{"name": "Engineering — [dim]Main stuff[/]", "value": mock_org}],
    )

    # ── prompts ──────────────────────────────────────────────────────────────
    # checkbox calls: (1) provider selection → ["aws"]
    #                 (2) registry org picker  → [mock_org]
    monkeypatch.setattr(inquirer, "checkbox", _seq_mock([["aws"], [mock_org]]))

    # confirm calls: (1) "Add manually?" → False
    #                (2) "Save?"         → True
    #                (3) "Shell?"        → True
    monkeypatch.setattr(inquirer, "confirm", _seq_mock([False, True, True]))

    # ── dependencies ─────────────────────────────────────────────────────────
    monkeypatch.setattr(core, "cmd_config_sync", lambda: 0)
    monkeypatch.setattr(core, "get_orgs_path", lambda ensure=True: orgs_file)
    monkeypatch.setattr(shell, "detect_shell_profile", lambda: tmp_path / ".zshrc")
    monkeypatch.setattr(shell, "inject_shell_function", MagicMock(return_value=True))

    # ── run ───────────────────────────────────────────────────────────────────
    success = wizard.run_wizard()

    assert success is True
    assert orgs_file.exists()
    data = yaml.safe_load(orgs_file.read_text(encoding="utf-8"))
    assert "engineering" in data["enabled_orgs"]


# ---------------------------------------------------------------------------
# Config write failure
# ---------------------------------------------------------------------------


def test_wizard_config_update_fail(monkeypatch, tmp_path, mock_rich_console):
    """Wizard returns False and reports error when config read raises."""

    # Provide a registry org so we can reach the write step without manual entry
    mock_org = {"name": "org", "provider": "aws"}
    monkeypatch.setattr(
        "cloudctl.wizard._load_registry_choices",
        lambda: [{"name": "Org", "value": mock_org}],
    )

    # checkbox: provider → ["aws"], registry → [mock_org]
    monkeypatch.setattr(inquirer, "checkbox", _seq_mock([["aws"], [mock_org]]))
    # confirm: no manual, yes save
    monkeypatch.setattr(inquirer, "confirm", _seq_mock([False, True]))

    # Force config read to raise inside _write_config
    mock_path = MagicMock()
    mock_path.parent = tmp_path
    mock_path.exists.return_value = True
    mock_path.read_text.side_effect = Exception("Disk IO Error")
    monkeypatch.setattr(core, "get_orgs_path", lambda ensure=True: mock_path)

    success = wizard.run_wizard()

    assert success is False
    captured = "".join(mock_rich_console.captured)
    assert "Disk IO Error" in captured
