# file: tests/test_install.py
from unittest.mock import MagicMock

import pytest

from awsctl import install


def test_install_wrapper(monkeypatch):
    # [FIX] Patch the functions directly in the install module namespace
    monkeypatch.setattr(install, "detect_shell_profile", lambda: "rc")
    monkeypatch.setattr(install, "inject_shell_function", lambda x: True)

    # The installer prints and exits 0
    with pytest.raises(SystemExit) as e:
        install.main()
    assert e.value.code == 0


def test_install_failure(monkeypatch):
    monkeypatch.setattr(install, "detect_shell_profile", lambda: "rc")
    monkeypatch.setattr(
        install, "inject_shell_function", MagicMock(side_effect=Exception("Fail"))
    )

    with pytest.raises(SystemExit) as e:
        install.main()
    assert e.value.code == 1
