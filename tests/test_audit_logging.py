# file: tests/test_audit_logging.py
from unittest.mock import patch

from awsctl import guardrails, utils


def test_audit_log_rotation_fail(monkeypatch, tmp_path):
    log_file = tmp_path / "audit.log"
    log_file.write_text("old logs")
    monkeypatch.setattr(guardrails, "AUDIT_LOG", log_file)
    monkeypatch.setattr(guardrails, "MAX_LOG_SIZE", 5)
    with patch("shutil.move", side_effect=OSError("Disk Full")):
        guardrails._audit_log("org", "role", "reason")
        assert "REASON=reason" in log_file.read_text()


def test_open_browser_fallback_explorer(monkeypatch):
    monkeypatch.setattr(utils, "is_wsl", lambda: True)
    with patch("shutil.which", return_value=None):
        with patch("subprocess.run") as mock_run:
            utils.open_browser("http://url")
            mock_run.assert_called_with(["explorer.exe", "http://url"], check=False)


def test_open_browser_exception(monkeypatch, mock_rich_console):
    monkeypatch.setattr(utils, "is_wsl", lambda: False)
    with patch("webbrowser.open", side_effect=Exception("No Browser")):
        utils.open_browser("http://url")
    assert "Could not open browser" in "".join(mock_rich_console.captured)
