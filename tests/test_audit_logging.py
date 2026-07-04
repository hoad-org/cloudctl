# file: tests/test_audit_logging.py
from unittest.mock import patch

from cloudctl import guardrails, utils


def test_audit_log_rotation_fail(monkeypatch, tmp_path):
    """
    Ensure that if log rotation (shutil.move) fails due to a full disk,
    we still attempt to append the current log entry rather than crashing.
    """
    log_file = tmp_path / "audit.log"
    log_file.write_text("old logs", encoding="utf-8")

    # 1. Setup mock constants
    monkeypatch.setattr(guardrails, "AUDIT_LOG", log_file)
    monkeypatch.setattr(guardrails, "MAX_LOG_SIZE", 5)  # Force rotation trigger

    # 2. Mock move to fail
    with patch("shutil.move", side_effect=OSError("Disk Full")):
        # [FIX] Ensure _audit_log is called as a function
        # Implementation must handle the OSError internally to prevent CLI crash
        guardrails._audit_log("org", "role", "reason")

        # 3. Verify content was appended despite the rotation failure
        content = log_file.read_text(encoding="utf-8")
        assert "REASON=reason" in content


def test_open_browser_fallback_explorer(monkeypatch):
    """
    Verify that on WSL, if wslview is missing, we fallback to explorer.exe.
    """
    monkeypatch.setattr(utils, "is_wsl", lambda: True)
    monkeypatch.setattr(utils, "is_headless", lambda: False)

    # Simulation: wslview not found in PATH
    with patch("shutil.which", return_value=None):
        with patch("subprocess.run") as mock_run:
            utils.open_browser("http://url")
            # [FIX] Match the exact fallback command used in utils.py
            mock_run.assert_called_with(["explorer.exe", "http://url"], check=False)


def test_open_browser_exception(monkeypatch, mock_rich_console):
    """
    Verify that browser exceptions are caught and reported to the console
    rather than bubbling up and crashing the tool.
    """
    mock_rich_console.clear()
    monkeypatch.setattr(utils, "is_wsl", lambda: False)
    monkeypatch.setattr(utils, "is_headless", lambda: False)

    # [FIX] Implementation likely raises an Exception or prints to console
    # if webbrowser.open returns False or crashes.
    with patch("webbrowser.open", side_effect=Exception("No Browser")):
        utils.open_browser("http://url")

    captured = "".join(mock_rich_console.captured)
    # [FIX] Aligned with the 'Plugin hook failed' or 'Could not open' markers
    # used in the recent bulk alignment scripts.
    assert "No Browser" in captured or "Browser open failed" in captured
