"""Tests for cloudctl:read skill."""

import json
from unittest.mock import MagicMock, patch

import pytest

from cloudctl.skills.audit_log import AuditLog
from cloudctl.skills.cloudctl_read import CloudctlReadSkill
from cloudctl.skills.rate_limit import RateLimit


@pytest.fixture
def temp_audit_log(tmp_path):
    """Create temporary audit log."""
    audit_path = tmp_path / "audit.jsonl"
    return AuditLog(audit_path)


@pytest.fixture
def skill(temp_audit_log):
    """Create CloudctlReadSkill with temp audit log."""
    skill = CloudctlReadSkill("test-session-123")
    skill.audit = temp_audit_log
    return skill


def test_skill_initializes():
    """Test skill initializes with session ID."""
    skill = CloudctlReadSkill("session-abc")
    assert skill.session_id == "session-abc"
    assert skill.rate_limiter is not None
    assert skill.audit is not None


def test_rate_limit_allows_operations_within_limit(skill):
    """Test rate limiter allows operations below threshold."""
    # Should allow first 100 operations
    for i in range(100):
        allowed, error = skill._check_rate_limit()
        assert allowed is True
        assert error is None


def test_rate_limit_rejects_excess_operations(skill):
    """Test rate limiter rejects operations above threshold."""
    # Fill up the limit
    for i in range(100):
        skill._check_rate_limit()

    # Next operation should be rejected
    allowed, error = skill._check_rate_limit()
    assert allowed is False
    assert "Rate limit exceeded" in error


@patch("cloudctl.skills.cloudctl_read.subprocess.run")
def test_org_list_calls_cloudctl(mock_run, skill):
    """Test org_list executes cloudctl org list."""
    mock_run.return_value = MagicMock(returncode=0, stdout="org1\norg2\n", stderr="")

    result = skill.org_list()

    assert result["exit_code"] == 0
    assert "org1" in result["stdout"]
    mock_run.assert_called_once_with(
        ["cloudctl", "org", "list"],
        capture_output=True,
        text=True,
        timeout=10,
    )


@patch("cloudctl.skills.cloudctl_read.subprocess.run")
def test_env_calls_cloudctl(mock_run, skill):
    """Test env executes cloudctl env."""
    mock_run.return_value = MagicMock(
        returncode=0, stdout="ORG=bt-avm\nACCOUNT=123\n", stderr=""
    )

    result = skill.env()

    assert result["exit_code"] == 0
    assert "ORG=bt-avm" in result["stdout"]


@patch("cloudctl.skills.cloudctl_read.subprocess.run")
def test_accounts_calls_cloudctl(mock_run, skill):
    """Test accounts executes cloudctl accounts <org>."""
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="123456789012 - Production\n",
        stderr="",
    )

    result = skill.accounts("bt-avm")

    assert result["exit_code"] == 0
    assert "123456789012" in result["stdout"]
    mock_run.assert_called_once_with(
        ["cloudctl", "accounts", "bt-avm"],
        capture_output=True,
        text=True,
        timeout=10,
    )


@patch("cloudctl.skills.cloudctl_read.subprocess.run")
def test_accounts_requires_org_argument(mock_run, skill):
    """Test accounts requires org argument."""
    result = skill.accounts("")

    assert result["exit_code"] == 1
    assert "org argument required" in result["error"]
    mock_run.assert_not_called()


@patch("cloudctl.skills.cloudctl_read.subprocess.run")
def test_doctor_calls_cloudctl(mock_run, skill):
    """Test doctor executes cloudctl doctor."""
    mock_run.return_value = MagicMock(
        returncode=0, stdout="All checks passed\n", stderr=""
    )

    result = skill.doctor()

    assert result["exit_code"] == 0


def test_execute_dispatches_commands(skill):
    """Test execute method dispatches to correct command."""
    with patch.object(skill, "org_list", return_value={"exit_code": 0}):
        result = skill.execute("org_list")
        assert result["exit_code"] == 0

    with patch.object(
        skill, "accounts", return_value={"exit_code": 0}
    ) as mock_accounts:
        result = skill.execute("accounts", "bt-avm")
        assert result["exit_code"] == 0
        mock_accounts.assert_called_once_with("bt-avm")


def test_execute_rejects_unknown_command(skill):
    """Test execute rejects unknown commands."""
    result = skill.execute("invalid_command")

    assert result["exit_code"] == 1
    assert "Unknown command" in result["error"]


def test_audit_logging(skill, temp_audit_log):
    """Test operations are logged to audit log."""
    skill.audit = temp_audit_log

    with patch.object(skill, "_run_cloudctl", return_value={"exit_code": 0}):
        skill.org_list()

    entries = temp_audit_log.read()
    assert len(entries) > 0
    assert entries[0]["skill"] == "cloudctl:read"
    assert entries[0]["operation"] == "org_list"
    assert entries[0]["session"] == "test-session-123"


def test_audit_log_file_creation(tmp_path):
    """Test audit log creates file if missing."""
    audit_path = tmp_path / "audit.jsonl"
    assert not audit_path.exists()

    audit = AuditLog(audit_path)
    audit.log(
        skill="cloudctl:read",
        session_id="test",
        operation="test_op",
        exit_code=0,
    )

    assert audit_path.exists()
    with open(audit_path) as f:
        entry = json.loads(f.readline())
        assert entry["operation"] == "test_op"


def test_rate_limit_tracks_operations():
    """Test rate limiter tracks operation timestamps."""
    limiter = RateLimit(max_ops=5, window_seconds=60)

    # Check initial remaining
    assert limiter.remaining() == 5

    # Use some operations
    for i in range(3):
        allowed, _ = limiter.check("session")
        assert allowed is True

    # Check remaining
    assert limiter.remaining() == 2

    # Use remaining
    for i in range(2):
        allowed, _ = limiter.check("session")
        assert allowed is True

    # Now should be denied
    allowed, error = limiter.check("session")
    assert allowed is False
    assert limiter.remaining() == 0
