# file: tests/conftest.py
"""
Shared pytest configuration and mocks for awsctl test suite.
"""

import subprocess
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def no_real_subprocess(monkeypatch):
    """Prevent hitting real system commands during unit tests."""
    mock_run = MagicMock()
    mock_run.return_value = subprocess.CompletedProcess(
        args=["cmd"], returncode=0, stdout="", stderr=""
    )
    monkeypatch.setattr(subprocess, "run", mock_run)
    yield mock_run


# -------------------------
# Summary
# - Simplified fixtures; CLI now handles context within tests directly.
# -------------------------
