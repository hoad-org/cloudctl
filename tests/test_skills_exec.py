"""Tests for cloudctl:exec skill (Phase 3)."""

import pytest
from unittest.mock import patch, MagicMock

from cloudctl.skills.cloudctl_exec import CloudctlExecSkill
from cloudctl.skills.command_filter import CommandFilter
from cloudctl.skills.output_sanitizer import OutputSanitizer
from cloudctl.skills.audit_log import AuditLog


@pytest.fixture
def temp_audit_log(tmp_path):
    """Create temporary audit log."""
    audit_path = tmp_path / "audit.jsonl"
    return AuditLog(audit_path)


@pytest.fixture
def skill(temp_audit_log):
    """Create CloudctlExecSkill with temp audit log."""
    skill = CloudctlExecSkill("test-session-exec-123")
    skill.audit = temp_audit_log
    return skill


class TestCommandFilter:
    """Tests for CommandFilter."""

    def test_filter_initializes_with_defaults(self):
        """Test filter initializes with default whitelist/blacklist."""
        filter = CommandFilter()
        assert filter.whitelist
        assert filter.blacklist

    def test_whitelist_allows_describe_commands(self):
        """Test describe commands are whitelisted."""
        filter = CommandFilter()
        allowed, reason = filter.is_allowed("aws describe-instances")
        assert allowed is True

    def test_whitelist_allows_list_commands(self):
        """Test list commands are whitelisted."""
        filter = CommandFilter()
        allowed, reason = filter.is_allowed("aws s3 ls")
        assert allowed is True

    def test_blacklist_denies_delete_commands(self):
        """Test delete commands are blacklisted."""
        filter = CommandFilter()
        allowed, reason = filter.is_allowed("aws s3api delete-object")
        assert allowed is False
        assert "blacklist" in reason.lower()

    def test_blacklist_denies_terminate_commands(self):
        """Test terminate commands are blacklisted."""
        filter = CommandFilter()
        allowed, reason = filter.is_allowed("aws ec2 terminate-instances")
        assert allowed is False

    def test_unknown_commands_denied_by_default(self):
        """Test unknown commands are denied (fail-closed)."""
        filter = CommandFilter()
        allowed, reason = filter.is_allowed("aws unknown-command")
        assert allowed is False
        assert "whitelist" in reason.lower()

    def test_terraform_plan_allowed(self):
        """Test terraform plan is whitelisted."""
        filter = CommandFilter()
        allowed, _ = filter.is_allowed("terraform plan")
        assert allowed is True

    def test_terraform_destroy_denied(self):
        """Test terraform destroy is blacklisted."""
        filter = CommandFilter()
        allowed, _ = filter.is_allowed("terraform destroy")
        assert allowed is False

    def test_pattern_matching_with_wildcards(self):
        """Test wildcard pattern matching."""
        filter = CommandFilter(
            whitelist=["aws describe-*"],
            blacklist=[],
        )
        assert filter.is_allowed("aws describe-instances")[0] is True
        assert filter.is_allowed("aws describe-regions")[0] is True
        assert filter.is_allowed("aws describe-xyz")[0] is True

    def test_filter_command_returns_category(self):
        """Test filter_command returns command category."""
        filter = CommandFilter()
        result = filter.filter_command("aws describe-instances")
        assert result["category"] == "read"
        assert result["allowed"] is True

    def test_custom_whitelist(self):
        """Test custom whitelist."""
        filter = CommandFilter(
            whitelist=["custom-command"],
            blacklist=[],
        )
        assert filter.is_allowed("custom-command")[0] is True
        assert filter.is_allowed("aws describe-instances")[0] is False


class TestOutputSanitizer:
    """Tests for OutputSanitizer."""

    def test_sanitizer_initializes(self):
        """Test sanitizer initializes with default patterns."""
        sanitizer = OutputSanitizer()
        assert sanitizer.patterns

    def test_redacts_aws_secret_access_key(self):
        """Test AWS_SECRET_ACCESS_KEY is redacted."""
        sanitizer = OutputSanitizer()
        output = "AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        sanitized = sanitizer.sanitize(output)
        assert "wJalrXUtnFEMI" not in sanitized
        assert "REDACTED" in sanitized

    def test_redacts_bearer_token(self):
        """Test Bearer tokens are redacted."""
        sanitizer = OutputSanitizer()
        # Example JWT-like string (fake token for testing, not a real credential)
        output = "Bearer TEST_JWT_PAYLOAD_PLACEHOLDER_NOT_A_REAL_TOKEN"
        sanitized = sanitizer.sanitize(output)
        assert "TEST_JWT_PAYLOAD_PLACEHOLDER_NOT_A_REAL_TOKEN" not in sanitized
        assert "REDACTED" in sanitized

    def test_hash_output(self):
        """Test output hashing."""
        sanitizer = OutputSanitizer()
        output = "test output"
        hash_val = sanitizer.hash_output(output)
        assert (
            hash_val
            == "0883407507398f58e21ab97dfc45a7795e51dfe427fdd605fbce08db750727f9"
        )
        assert len(hash_val) == 64  # SHA256 hex is 64 chars

    def test_redact_secrets_returns_tuple(self):
        """Test redact_secrets returns (sanitized, hash)."""
        sanitizer = OutputSanitizer()
        output = "AWS_SECRET_ACCESS_KEY=secret123 data"
        sanitized, output_hash = sanitizer.redact_secrets(output)
        assert "REDACTED" in sanitized
        assert len(output_hash) == 64

    def test_has_redactions_detects_changes(self):
        """Test has_redactions detects when redactions were made."""
        sanitizer = OutputSanitizer()
        original = "AWS_SECRET_ACCESS_KEY=secret"
        sanitized = sanitizer.sanitize(original)
        assert sanitizer.has_redactions(original, sanitized) is True

    def test_has_redactions_no_changes(self):
        """Test has_redactions returns False when no changes."""
        sanitizer = OutputSanitizer()
        output = "normal output with no secrets"
        sanitized = sanitizer.sanitize(output)
        assert sanitizer.has_redactions(output, sanitized) is False

    def test_redaction_summary(self):
        """Test redaction summary includes secret types."""
        sanitizer = OutputSanitizer()
        original = "AWS_SECRET_ACCESS_KEY=secret123"
        sanitized = sanitizer.sanitize(original)
        summary = sanitizer.get_redaction_summary(original, sanitized)
        assert summary["redacted"] is True
        assert summary["redaction_count"] > 0


class TestCloudctlExecSkill:
    """Tests for CloudctlExecSkill."""

    def test_skill_initializes(self):
        """Test skill initializes with session ID."""
        skill = CloudctlExecSkill("session-exec-abc")
        assert skill.session_id == "session-exec-abc"
        assert skill.audit is not None
        assert skill.rate_limiter is not None
        assert skill.command_filter is not None
        assert skill.output_sanitizer is not None

    def test_exec_checks_rate_limit(self, skill):
        """Test exec respects rate limit (20 execs/min)."""
        # Mock approval to auto-approve
        with patch.object(skill.approval_client, "request_approval") as mock_req:
            with patch.object(skill.approval_client, "poll_approval") as mock_poll:
                with patch("subprocess.run") as mock_run:
                    mock_req.return_value = "APPR-TEST"
                    mock_poll.return_value = True
                    mock_run.return_value = MagicMock(
                        returncode=0, stdout="", stderr=""
                    )

                    # First 20 execs should succeed
                    for i in range(20):
                        result = skill.exec(
                            "bt-avm", "123456789", "read-only", "aws s3 ls"
                        )
                        assert result["exit_code"] == 0

                    # 21st exec should be rate limited
                    result = skill.exec("bt-avm", "123456789", "read-only", "aws s3 ls")
                    assert result["exit_code"] == 429

    def test_exec_filters_commands(self, skill):
        """Test exec filters commands through whitelist/blacklist."""
        # Blacklisted command
        result = skill.exec("bt-avm", "123456789", "admin", "aws s3api delete-object")
        assert result["exit_code"] == 403
        assert "denied" in result["error"].lower()

    def test_exec_requests_approval(self, skill):
        """Test exec requests approval before execution."""
        with patch.object(skill.approval_client, "request_approval") as mock_req:
            with patch.object(skill.approval_client, "poll_approval") as mock_poll:
                with patch("subprocess.run") as mock_run:
                    mock_req.return_value = "APPR-EXEC001"
                    mock_poll.return_value = True
                    mock_run.return_value = MagicMock(
                        returncode=0, stdout="output", stderr=""
                    )

                    result = skill.exec("bt-avm", "123456789", "read-only", "aws s3 ls")
                    assert result["exit_code"] == 0
                    assert result["approval_id"] == "APPR-EXEC001"
                    mock_req.assert_called_once()
                    mock_poll.assert_called_once()

    def test_exec_approval_rejection_blocks_execution(self, skill):
        """Test exec fails if approval is rejected."""
        with patch.object(skill.approval_client, "request_approval") as mock_req:
            with patch.object(skill.approval_client, "poll_approval") as mock_poll:
                with patch("subprocess.run") as mock_run:
                    mock_req.return_value = "APPR-REJECT"
                    mock_poll.return_value = False
                    mock_run.side_effect = AssertionError("Should not be called")

                    result = skill.exec("bt-avm", "123456789", "admin", "aws s3 ls")
                    assert result["exit_code"] == 403
                    assert (
                        "denied" in result["error"].lower()
                        or "timed out" in result["error"].lower()
                    )
                    mock_run.assert_not_called()

    def test_exec_sanitizes_output(self, skill):
        """Test exec sanitizes output before returning."""
        with patch.object(skill.approval_client, "request_approval") as mock_req:
            with patch.object(skill.approval_client, "poll_approval") as mock_poll:
                with patch("subprocess.run") as mock_run:
                    mock_req.return_value = "APPR-EXEC001"
                    mock_poll.return_value = True
                    mock_run.return_value = MagicMock(
                        returncode=0,
                        stdout="AWS_SECRET_ACCESS_KEY=secret123",
                        stderr="",
                    )

                    result = skill.exec(
                        "bt-avm", "123456789", "read-only", "aws iam list-users"
                    )
                    assert result["exit_code"] == 0
                    assert result["redacted"] is True
                    assert "secret123" not in result["sanitized_output"]
                    assert "REDACTED" in result["sanitized_output"]

    def test_exec_computes_output_hash(self, skill):
        """Test exec computes output hash."""
        with patch.object(skill.approval_client, "request_approval") as mock_req:
            with patch.object(skill.approval_client, "poll_approval") as mock_poll:
                with patch("subprocess.run") as mock_run:
                    mock_req.return_value = "APPR-HASH"
                    mock_poll.return_value = True
                    mock_run.return_value = MagicMock(
                        returncode=0, stdout="test output", stderr=""
                    )

                    result = skill.exec("bt-avm", "123456789", "read-only", "aws s3 ls")
                    assert result["exit_code"] == 0
                    assert len(result["output_hash"]) == 64  # SHA256 hex

    def test_exec_dry_run_skips_execution(self, skill):
        """Test exec with --dry-run skips actual execution."""
        with patch.object(skill.approval_client, "request_approval") as mock_req:
            with patch.object(skill.approval_client, "poll_approval") as mock_poll:
                with patch("subprocess.run") as mock_run:
                    mock_req.return_value = "APPR-DRY"
                    mock_poll.return_value = True

                    result = skill.exec(
                        "bt-avm",
                        "123456789",
                        "read-only",
                        "aws s3 ls",
                        dry_run=True,
                    )
                    assert result["exit_code"] == 0
                    assert "DRY-RUN" in result["message"]
                    mock_run.assert_not_called()

    def test_exec_timeout(self, skill):
        """Test exec command timeout."""
        import subprocess

        with patch.object(skill.approval_client, "request_approval") as mock_req:
            with patch.object(skill.approval_client, "poll_approval") as mock_poll:
                with patch("subprocess.run") as mock_run:
                    mock_req.return_value = "APPR-TIMEOUT"
                    mock_poll.return_value = True
                    mock_run.side_effect = subprocess.TimeoutExpired("cmd", 30)

                    result = skill.exec("bt-avm", "123456789", "read-only", "aws s3 ls")
                    assert result["exit_code"] == 124  # timeout exit code

    def test_execute_dispatches_exec_command(self, skill):
        """Test execute dispatches to exec."""
        with patch.object(skill, "exec", return_value={"exit_code": 0}):
            result = skill.execute("exec", "bt-avm", "123456789", "admin", "aws s3 ls")
            assert result["exit_code"] == 0

    def test_execute_rejects_unknown_command(self, skill):
        """Test execute rejects unknown commands."""
        result = skill.execute("invalid_command")
        assert result["exit_code"] == 1
        assert "Unknown command" in result["error"]

    def test_audit_logging_on_successful_exec(self, skill, temp_audit_log):
        """Test successful exec is logged with output hash."""
        skill.audit = temp_audit_log
        with patch.object(skill.approval_client, "request_approval") as mock_req:
            with patch.object(skill.approval_client, "poll_approval") as mock_poll:
                with patch("subprocess.run") as mock_run:
                    mock_req.return_value = "APPR-AUD001"
                    mock_poll.return_value = True
                    mock_run.return_value = MagicMock(
                        returncode=0, stdout="result", stderr=""
                    )

                    skill.exec("bt-avm", "123456789", "read-only", "aws s3 ls")

        entries = temp_audit_log.read()
        assert len(entries) > 0
        assert entries[-1]["skill"] == "cloudctl:exec"
        assert entries[-1]["operation"] == "exec"
        assert entries[-1]["approval_id"] == "APPR-AUD001"
        assert entries[-1]["output_hash"] is not None

    def test_audit_logging_on_denied_command(self, skill, temp_audit_log):
        """Test denied command is logged with exit code 403."""
        skill.audit = temp_audit_log
        skill.exec("bt-avm", "123456789", "admin", "aws s3api delete-object")

        entries = temp_audit_log.read()
        assert len(entries) > 0
        assert entries[-1]["exit_code"] == 403
