"""Tests for cloudctl:switch skill (Phase 2)."""

import json

import pytest
from unittest.mock import MagicMock, patch

from cloudctl.skills.cloudctl_switch import CloudctlSwitchSkill
from cloudctl.skills.approval_client import ApprovalClient
from cloudctl.skills.audit_log import AuditLog


@pytest.fixture
def temp_audit_log(tmp_path):
    """Create temporary audit log."""
    audit_path = tmp_path / "audit.jsonl"
    return AuditLog(audit_path)


@pytest.fixture
def mock_sso_session():
    """Simulate a valid cached SSO session + AWS role credentials.

    switch() retrieves real credentials (load_active_sso_token + aws sso
    get-role-credentials) before saving context, so tests of the post-approval
    path must stand in a valid session. Patches at the source modules (the
    functions are imported inside switch()).
    """
    fake_token = MagicMock()
    fake_token.accessToken = "test-access-token"
    creds_json = json.dumps(
        {
            "roleCredentials": {
                "accessKeyId": "AKIATEST",
                "secretAccessKey": "test-secret",
                "sessionToken": "test-session",
            }
        }
    )
    with patch(
        "cloudctl.sso_cache.load_active_sso_token", return_value=fake_token
    ), patch(
        "cloudctl.aws.run_aws",
        return_value={"returncode": 0, "stdout": creds_json, "stderr": ""},
    ):
        yield


@pytest.fixture
def skill(temp_audit_log):
    """Create CloudctlSwitchSkill with temp audit log."""
    skill = CloudctlSwitchSkill("test-session-switch-123")
    skill.audit = temp_audit_log
    return skill


class TestApprovalClient:
    """Tests for ApprovalClient."""

    def test_approval_client_initializes(self):
        """Test approval client initializes successfully."""
        client = ApprovalClient()
        assert client is not None

    def test_request_approval_returns_approval_id(self):
        """Test request_approval returns a valid approval ID."""
        client = ApprovalClient()
        approval_id = client.request_approval(
            skill="cloudctl:switch",
            operation="switch",
            org="bt-avm",
            role="admin",
            reason="Test approval",
            num_approvers=2,
        )
        assert approval_id.startswith("APPR-")
        assert len(approval_id) > 5

    def test_poll_approval_auto_approves_in_mock(self):
        """Test poll_approval auto-approves in mock implementation."""
        client = ApprovalClient()
        approval_id = client.request_approval(
            skill="cloudctl:switch",
            operation="switch",
            org="bt-avm",
            role="admin",
            reason="Test approval",
        )
        result = client.poll_approval(approval_id, timeout=5)
        assert result is True

    def test_poll_approval_timeout_raises_on_invalid_id(self):
        """Test poll_approval raises KeyError for invalid approval ID."""
        client = ApprovalClient()
        with pytest.raises(KeyError):
            client.poll_approval("INVALID-ID", timeout=1)

    def test_get_approval_status_returns_approved(self):
        """Test get_approval_status returns correct status after approval."""
        client = ApprovalClient()
        approval_id = client.request_approval(
            skill="cloudctl:switch",
            operation="switch",
            org="bt-avm",
            role="admin",
            reason="Test approval",
        )
        client.poll_approval(approval_id)
        status = client.get_approval_status(approval_id)
        assert status["status"] == "approved"
        assert status["approver"] is not None

    def test_reject_approval_changes_status(self):
        """Test reject_approval sets status to rejected."""
        client = ApprovalClient()
        approval_id = client.request_approval(
            skill="cloudctl:switch",
            operation="switch",
            org="bt-avm",
            role="admin",
            reason="Test approval",
        )
        client.reject_approval(approval_id, "Test rejection")
        status = client.get_approval_status(approval_id)
        assert status["status"] == "rejected"
        assert status["rejection_reason"] == "Test rejection"


class TestCloudctlSwitchSkill:
    """Tests for CloudctlSwitchSkill."""

    def test_skill_initializes(self):
        """Test skill initializes with session ID."""
        skill = CloudctlSwitchSkill("session-abc")
        assert skill.session_id == "session-abc"
        assert skill.audit is not None
        assert skill.login_limiter is not None
        assert skill.switch_limiter is not None

    def test_login_checks_rate_limit(self, skill):
        """Test login respects rate limit (5 logins/hour)."""
        # Mock config to have no approval required for login
        with patch("cloudctl.skills.cloudctl_switch.get_org") as mock_get_org:
            mock_get_org.return_value = {"name": "bt-avm", "provider": "aws"}
            with patch(
                "cloudctl.skills.cloudctl_switch.check_approval_required"
            ) as mock_check:
                mock_check.return_value = (False, 0)
                with patch.object(
                    skill,
                    "_run_cloudctl",
                    return_value={"exit_code": 0, "stdout": "", "stderr": ""},
                ):
                    # First 5 logins should succeed
                    for i in range(5):
                        result = skill.login("bt-avm")
                        assert result["exit_code"] == 0

                    # 6th login should be rate limited
                    result = skill.login("bt-avm")
                    assert result["exit_code"] == 429
                    assert "Rate limit" in result["error"]

    def test_login_validates_org_exists(self, skill):
        """Test login fails if org doesn't exist."""
        with patch("cloudctl.skills.cloudctl_switch.get_org") as mock_get_org:
            mock_get_org.side_effect = Exception("Org not found")
            result = skill.login("invalid-org")
            assert result["exit_code"] == 1
            assert "Organization not found" in result["error"]

    def test_login_without_approval_succeeds_immediately(self, skill):
        """Test login succeeds immediately if no approval required."""
        with patch("cloudctl.skills.cloudctl_switch.get_org") as mock_get_org:
            mock_get_org.return_value = {"name": "bt-avm", "provider": "aws"}
            with patch(
                "cloudctl.skills.cloudctl_switch.check_approval_required"
            ) as mock_check:
                mock_check.return_value = (False, 0)
                with patch.object(
                    skill,
                    "_run_cloudctl",
                    return_value={"exit_code": 0, "stdout": "", "stderr": ""},
                ):
                    result = skill.login("bt-avm")
                    assert result["exit_code"] == 0
                    assert "approval_id" in result

    def test_login_with_approval_requests_and_polls(self, skill):
        """Test login with approval required goes through approval flow."""
        with patch("cloudctl.skills.cloudctl_switch.get_org") as mock_get_org:
            mock_get_org.return_value = {"name": "bt-avm", "provider": "aws"}
            with patch(
                "cloudctl.skills.cloudctl_switch.check_approval_required"
            ) as mock_check:
                mock_check.return_value = (True, 2)  # Requires 2 approvers
                with patch.object(
                    skill.approval_client, "request_approval"
                ) as mock_req:
                    with patch.object(
                        skill.approval_client, "poll_approval"
                    ) as mock_poll:
                        with patch.object(
                            skill,
                            "_run_cloudctl",
                            return_value={"exit_code": 0, "stdout": "", "stderr": ""},
                        ):
                            mock_req.return_value = "APPR-TEST123"
                            mock_poll.return_value = True
                            result = skill.login("bt-avm")
                            assert result["exit_code"] == 0
                            assert result["approval_id"] == "APPR-TEST123"
                            mock_req.assert_called_once()
                            mock_poll.assert_called_once()

    def test_switch_checks_rate_limit(self, skill, mock_sso_session):
        """Test switch respects rate limit (10 switches/min)."""
        with patch("cloudctl.skills.cloudctl_switch.get_org") as mock_get_org:
            mock_get_org.return_value = {"name": "bt-avm", "provider": "aws"}
            with patch(
                "cloudctl.skills.cloudctl_switch.check_approval_required"
            ) as mock_check:
                mock_check.return_value = (False, 0)
                with patch("cloudctl.skills.cloudctl_switch.save_context"):
                    # First 10 switches should succeed
                    for i in range(10):
                        result = skill.switch("bt-avm", "123456789", "read-only")
                        assert result["exit_code"] == 0

                    # 11th switch should be rate limited
                    result = skill.switch("bt-avm", "123456789", "read-only")
                    assert result["exit_code"] == 429

    def test_switch_to_non_sensitive_role_no_approval(self, skill, mock_sso_session):
        """Test switch to non-sensitive role doesn't require approval."""
        with patch("cloudctl.skills.cloudctl_switch.get_org") as mock_get_org:
            mock_get_org.return_value = {"name": "bt-avm", "provider": "aws"}
            with patch(
                "cloudctl.skills.cloudctl_switch.check_approval_required"
            ) as mock_check:
                mock_check.return_value = (False, 0)
                with patch("cloudctl.skills.cloudctl_switch.save_context"):
                    result = skill.switch("bt-avm", "123456789", "read-only")
                    assert result["exit_code"] == 0
                    assert result["approval_id"] is None

    def test_switch_to_sensitive_role_requires_approval(self, skill, mock_sso_session):
        """Test switch to sensitive role requires approval."""
        with patch("cloudctl.skills.cloudctl_switch.get_org") as mock_get_org:
            mock_get_org.return_value = {
                "name": "bt-avm",
                "provider": "aws",
                "approval_gate_roles": {"admin": 2},
            }
            with patch(
                "cloudctl.skills.cloudctl_switch.check_approval_required"
            ) as mock_check:
                mock_check.return_value = (True, 2)
                with patch.object(
                    skill.approval_client, "request_approval"
                ) as mock_req:
                    with patch.object(
                        skill.approval_client, "poll_approval"
                    ) as mock_poll:
                        with patch("cloudctl.skills.cloudctl_switch.save_context"):
                            mock_req.return_value = "APPR-ADM001"
                            mock_poll.return_value = True
                            result = skill.switch("bt-avm", "123456789", "admin")
                            assert result["exit_code"] == 0
                            assert result["approval_id"] == "APPR-ADM001"

    def test_switch_approval_rejection_blocks_switch(self, skill):
        """Test switch fails if approval is rejected."""
        with patch("cloudctl.skills.cloudctl_switch.get_org") as mock_get_org:
            mock_get_org.return_value = {"name": "bt-avm", "provider": "aws"}
            with patch(
                "cloudctl.skills.cloudctl_switch.check_approval_required"
            ) as mock_check:
                mock_check.return_value = (True, 1)
                with patch.object(
                    skill.approval_client, "request_approval"
                ) as mock_req:
                    with patch.object(
                        skill.approval_client, "poll_approval"
                    ) as mock_poll:
                        mock_req.return_value = "APPR-REJ001"
                        mock_poll.return_value = False
                        result = skill.switch("bt-avm", "123456789", "admin")
                        assert result["exit_code"] == 403
                        assert "Approval denied" in result["error"]

    def test_logout_succeeds(self, skill):
        """Test logout operation."""
        result = skill.logout()
        assert result["exit_code"] == 0
        assert "Logged out" in result["message"]

    def test_execute_login_command(self, skill):
        """Test execute dispatches to login."""
        with patch.object(skill, "login", return_value={"exit_code": 0}):
            result = skill.execute("login", "bt-avm")
            assert result["exit_code"] == 0

    def test_execute_switch_command(self, skill):
        """Test execute dispatches to switch."""
        with patch.object(skill, "switch", return_value={"exit_code": 0}):
            result = skill.execute("switch", "bt-avm", "123456789", "admin")
            assert result["exit_code"] == 0

    def test_execute_logout_command(self, skill):
        """Test execute dispatches to logout."""
        result = skill.execute("logout")
        assert result["exit_code"] == 0

    def test_execute_rejects_unknown_command(self, skill):
        """Test execute rejects unknown commands."""
        result = skill.execute("invalid_command")
        assert result["exit_code"] == 1
        assert "Unknown command" in result["error"]

    def test_audit_logging_on_login(self, skill, temp_audit_log):
        """Test login operations are logged to audit trail."""
        skill.audit = temp_audit_log
        with patch("cloudctl.skills.cloudctl_switch.get_org") as mock_get_org:
            mock_get_org.return_value = {"name": "bt-avm", "provider": "aws"}
            with patch(
                "cloudctl.skills.cloudctl_switch.check_approval_required"
            ) as mock_check:
                mock_check.return_value = (False, 0)
                skill.login("bt-avm")

        entries = temp_audit_log.read()
        assert len(entries) > 0
        assert entries[-1]["skill"] == "cloudctl:switch"
        assert entries[-1]["operation"] == "login"
        assert entries[-1]["session"] == "test-session-switch-123"

    def test_audit_logging_on_switch(self, skill, temp_audit_log, mock_sso_session):
        """Test switch operations are logged with approval_id."""
        skill.audit = temp_audit_log
        with patch("cloudctl.skills.cloudctl_switch.get_org") as mock_get_org:
            mock_get_org.return_value = {"name": "bt-avm", "provider": "aws"}
            with patch(
                "cloudctl.skills.cloudctl_switch.check_approval_required"
            ) as mock_check:
                mock_check.return_value = (True, 1)
                with patch.object(
                    skill.approval_client, "request_approval"
                ) as mock_req:
                    with patch.object(
                        skill.approval_client, "poll_approval"
                    ) as mock_poll:
                        with patch("cloudctl.skills.cloudctl_switch.save_context"):
                            mock_req.return_value = "APPR-TEST001"
                            mock_poll.return_value = True
                            skill.switch("bt-avm", "123456789", "admin")

        entries = temp_audit_log.read()
        assert len(entries) > 0
        assert entries[-1]["skill"] == "cloudctl:switch"
        assert entries[-1]["operation"] == "switch"
        assert entries[-1]["approval_id"] == "APPR-TEST001"

    def test_session_isolation_different_rate_limits(self):
        """Test two skills have independent rate limits."""
        skill_a = CloudctlSwitchSkill("session-a")
        skill_b = CloudctlSwitchSkill("session-b")

        # Use up skill_a's login limit
        for i in range(5):
            skill_a.login_limiter.check("session-a")

        # skill_a should be rate limited
        allowed_a, _ = skill_a.login_limiter.check("session-a")
        assert not allowed_a

        # skill_b should still have logins available
        allowed_b, _ = skill_b.login_limiter.check("session-b")
        assert allowed_b
