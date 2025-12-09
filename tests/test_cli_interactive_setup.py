# file: tests/test_cli_interactive_setup.py
"""
Coverage boost for interactive setup path in cli.py.
"""

from unittest.mock import MagicMock

from awsctl import cli


def test_setup_interactive(monkeypatch):
    # Ensure headless is OFF
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("AWSCTL_HEADLESS", raising=False)

    mock_wizard = MagicMock()
    monkeypatch.setattr("awsctl.wizard.run_wizard", mock_wizard)

    # Run setup
    args = type("Args", (), {})
    assert cli.cmd_setup(args) == 0

    mock_wizard.assert_called_once()


def test_setup_keyboard_interrupt(monkeypatch):
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("AWSCTL_HEADLESS", raising=False)

    # Mock wizard to raise KeyboardInterrupt
    mock_wizard = MagicMock(side_effect=KeyboardInterrupt)
    monkeypatch.setattr("awsctl.wizard.run_wizard", mock_wizard)

    # Run setup
    args = type("Args", (), {})
    # Should exit 1 gracefully
    assert cli.cmd_setup(args) == 1


def test_setup_exception(monkeypatch, capsys):
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("AWSCTL_HEADLESS", raising=False)

    # Mock wizard to raise generic exception
    mock_wizard = MagicMock(side_effect=Exception("Boom"))
    monkeypatch.setattr("awsctl.wizard.run_wizard", mock_wizard)

    args = type("Args", (), {})
    assert cli.cmd_setup(args) == 1

    out, err = capsys.readouterr()
    assert "Setup failed" in err
