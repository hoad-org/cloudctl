"""Tests for the native RBAC orchestration in cloudctl.guardrails.

Covers validate_role_access (allowed-roles allowlist, break-glass, approval and
MFA gates), validate_multi_cloud_access (provider role-format checks),
get_rbac_policy_summary, and the native audit-log query helpers. They live in
guardrails and write to the single native audit log (~/.cloudctl/audit.log).
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from cloudctl import guardrails as rbac


class TestValidateRoleAccess:
    def test_allowed_role_no_gates(self):
        org = {"name": "test-org", "allowed_roles": ["ReadOnly", "PowerUser", "Admin"]}
        allowed, message = rbac.validate_role_access(org, "ReadOnly", "123456789012")
        assert allowed is True
        assert message == ""

    def test_disallowed_role(self):
        org = {"name": "test-org", "allowed_roles": ["ReadOnly", "PowerUser"]}
        allowed, message = rbac.validate_role_access(org, "Admin", "123456789012")
        assert allowed is False
        assert "not allowed" in message.lower()

    def test_empty_allowed_roles_no_filtering(self):
        org = {"name": "test-org", "allowed_roles": []}
        allowed, _ = rbac.validate_role_access(org, "ReadOnly", "123456789012")
        assert allowed is True

    def test_no_allowed_roles_defined_allows_all(self):
        org = {"name": "test-org"}
        allowed, _ = rbac.validate_role_access(org, "ReadOnly", "123456789012")
        assert allowed is True

    @patch("cloudctl.guardrails.check_break_glass")
    def test_sensitive_role_triggers_break_glass(self, mock_break_glass):
        org = {
            "name": "test-org",
            "allowed_roles": ["ReadOnly", "Admin"],
            "sensitive_roles": ["Admin"],
        }
        allowed, message = rbac.validate_role_access(org, "Admin", "123456789012")
        assert allowed is True
        assert message == ""
        mock_break_glass.assert_called_once_with(org, "Admin")

    @patch("cloudctl.guardrails.check_approval_required")
    def test_approval_gate_returns_pending(self, mock_check_approval):
        mock_check_approval.return_value = (True, 2)
        org = {"name": "test-org", "allowed_roles": ["ReadOnly", "Admin"]}
        allowed, message = rbac.validate_role_access(org, "Admin", "123456789012")
        assert allowed is True
        assert message == "approval_required"

    @patch("cloudctl.guardrails.check_mfa_required")
    @patch("cloudctl.guardrails.check_approval_required")
    def test_mfa_gate_returns_pending(self, mock_check_approval, mock_check_mfa):
        mock_check_approval.return_value = (False, 0)
        mock_check_mfa.return_value = (True, "totp")
        org = {"name": "test-org", "allowed_roles": ["ReadOnly", "Admin"]}
        allowed, message = rbac.validate_role_access(org, "Admin", "123456789012")
        assert allowed is True
        assert message == "mfa_required"


class TestInputValidation:
    def test_none_org_raises_error(self):
        with pytest.raises(AttributeError):
            rbac.validate_role_access(None, "ReadOnly", "123456789012")

    def test_empty_role_name_is_denied(self):
        org = {"name": "test-org", "allowed_roles": ["ReadOnly"]}
        allowed, _ = rbac.validate_role_access(org, "", "123456789012")
        assert allowed is False

    def test_whitespace_role_name(self):
        org = {"name": "test-org", "allowed_roles": ["ReadOnly"]}
        allowed, _ = rbac.validate_role_access(org, "   ", "123456789012")
        assert allowed is False

    def test_case_sensitive_role_matching(self):
        org = {"name": "test-org", "allowed_roles": ["ReadOnly"]}
        allowed, _ = rbac.validate_role_access(org, "readonly", "123456789012")
        assert allowed is False

    def test_special_characters_in_role(self):
        org = {
            "name": "test-org",
            "allowed_roles": ["Role-With-Dashes", "Role_With_Underscores"],
        }
        allowed, _ = rbac.validate_role_access(org, "Role-With-Dashes", "123456789012")
        assert allowed is True

    def test_none_account_id_is_logged(self):
        org = {"name": "test-org"}
        with patch("cloudctl.guardrails._audit_log") as mock_log:
            allowed, _ = rbac.validate_role_access(org, "ReadOnly", None)
            assert allowed is True
            mock_log.assert_called()  # account no longer a positional arg; folded into reason

    def test_empty_account_id(self):
        org = {"name": "test-org"}
        allowed, _ = rbac.validate_role_access(org, "ReadOnly", "")
        assert allowed is True

    def test_very_long_role_name(self):
        long_name = "A" * 10000
        org = {"name": "test-org", "allowed_roles": [long_name]}
        allowed, _ = rbac.validate_role_access(org, long_name, "123456789012")
        assert allowed is True

    def test_unicode_role_name(self):
        org = {"name": "test-org", "allowed_roles": ["管理员", "ReadOnly"]}
        allowed, _ = rbac.validate_role_access(org, "管理员", "123456789012")
        assert allowed is True

    def test_role_with_newlines(self):
        org = {"name": "test-org", "allowed_roles": ["ReadOnly"]}
        allowed, _ = rbac.validate_role_access(org, "ReadOnly\nAdmin", "123456789012")
        assert allowed is False


class TestAllowedRolesValidation:
    def test_allowed_roles_is_not_list(self):
        org = {"name": "test-org", "allowed_roles": "ReadOnly"}
        allowed, msg = rbac.validate_role_access(org, "R", "123456789012")
        assert allowed is False
        assert "Invalid allowed_roles configuration" in msg

    def test_allowed_roles_is_none(self):
        org = {"name": "test-org", "allowed_roles": None}
        allowed, _ = rbac.validate_role_access(org, "ReadOnly", "123456789012")
        assert allowed is True

    def test_allowed_roles_is_dict(self):
        org = {"name": "test-org", "allowed_roles": {"role": "ReadOnly"}}
        allowed, msg = rbac.validate_role_access(org, "role", "123456789012")
        assert allowed is False
        assert "Invalid allowed_roles configuration" in msg

    def test_allowed_roles_with_none_elements(self):
        org = {"name": "test-org", "allowed_roles": ["ReadOnly", None, "Admin"]}
        allowed, _ = rbac.validate_role_access(org, "ReadOnly", "123456789012")
        assert allowed is True


class TestSensitiveRolesValidation:
    def test_sensitive_roles_is_string(self):
        org = {"name": "test-org", "sensitive_roles": "Admin"}
        with patch("cloudctl.guardrails.check_break_glass") as mock_break_glass:
            # "A" in "Admin" == True, so "A" is treated as sensitive
            rbac.validate_role_access(org, "A", "123456789012")
            mock_break_glass.assert_called_once()

    @patch("cloudctl.guardrails.check_break_glass")
    def test_break_glass_exception_handling(self, mock_break_glass):
        mock_break_glass.side_effect = ValueError("Break glass failed")
        org = {"name": "test-org", "sensitive_roles": ["Admin"]}
        with pytest.raises(ValueError):
            rbac.validate_role_access(org, "Admin", "123456789012")


class TestApprovalGateValidation:
    @patch("cloudctl.guardrails.check_approval_required")
    def test_approval_required_returns_invalid_tuple(self, mock_check):
        mock_check.return_value = "invalid"
        org = {"name": "test-org"}
        with pytest.raises((TypeError, ValueError)):
            rbac.validate_role_access(org, "Admin", "123456789012")

    @patch("cloudctl.guardrails.check_approval_required")
    def test_approval_required_negative_approvers(self, mock_check):
        mock_check.return_value = (True, -5)
        org = {"name": "test-org"}
        allowed, msg = rbac.validate_role_access(org, "Admin", "123456789012")
        assert allowed is True
        assert msg == "approval_required"


class TestMFAGateValidation:
    @patch("cloudctl.guardrails.check_mfa_required")
    def test_mfa_required_returns_invalid_tuple(self, mock_check):
        mock_check.return_value = "invalid"
        org = {"name": "test-org"}
        with pytest.raises((TypeError, ValueError)):
            rbac.validate_role_access(org, "Admin", "123456789012")

    @patch("cloudctl.guardrails.check_mfa_required")
    def test_mfa_required_empty_method(self, mock_check):
        mock_check.return_value = (True, "")
        org = {"name": "test-org"}
        allowed, msg = rbac.validate_role_access(org, "Admin", "123456789012")
        assert allowed is True
        assert msg == "mfa_required"


class TestMultiCloudValidation:
    def test_validate_aws_role(self):
        org = {"name": "test-org", "allowed_roles": ["ReadOnly", "PowerUser"]}
        allowed, _ = rbac.validate_multi_cloud_access(
            org, "aws", "ReadOnly", "123456789012"
        )
        assert allowed is True

    def test_validate_gcp_role_invalid_format(self):
        org = {"name": "test-org"}
        allowed, message = rbac.validate_multi_cloud_access(
            org, "gcp", "viewer", "gcp-project-123"
        )
        assert allowed is False
        assert "Invalid GCP role format" in message

    def test_validate_gcp_role_valid_format(self):
        org = {"name": "test-org"}
        allowed, _ = rbac.validate_multi_cloud_access(
            org, "gcp", "roles/viewer", "gcp-project-123"
        )
        assert allowed is True

    def test_validate_azure_role(self):
        org = {"name": "test-org", "allowed_roles": ["Reader", "Contributor"]}
        allowed, _ = rbac.validate_multi_cloud_access(
            org, "azure", "Reader", "subscription-id-123"
        )
        assert allowed is True

    def test_validate_gcp_role_with_forward_slashes(self):
        org = {"name": "test-org"}
        allowed, _ = rbac.validate_multi_cloud_access(
            org, "gcp", "roles/viewer/custom", "project"
        )
        assert allowed is True

    def test_validate_gcp_role_empty_string(self):
        org = {"name": "test-org"}
        allowed, _ = rbac.validate_multi_cloud_access(org, "gcp", "", "project")
        assert allowed is False

    def test_validate_provider_case_insensitivity(self):
        org = {"name": "test-org", "allowed_roles": ["ReadOnly"]}
        for provider in ["AWS", "Aws", "aWs", "GCP", "gcp", "AZURE", "azure"]:
            allowed, _ = rbac.validate_multi_cloud_access(
                org, provider, "ReadOnly", "resource"
            )
            assert allowed is True


class TestRBACPolicySummary:
    def test_summary_with_all_fields(self):
        org = {
            "name": "test-org",
            "allowed_roles": ["ReadOnly", "PowerUser"],
            "sensitive_roles": ["Admin"],
            "approval_gate_roles": {"Admin": 2},
            "mfa_required_roles": ["Admin", "SecurityAdmin"],
        }
        summary = rbac.get_rbac_policy_summary(org)
        assert "test-org" in summary
        assert "ReadOnly" in summary
        assert "break-glass" in summary
        assert "Approval" in summary
        assert "MFA" in summary

    def test_summary_empty_org(self):
        org = {"name": "empty-org"}
        summary = rbac.get_rbac_policy_summary(org)
        assert "empty-org" in summary
        assert "Allowed Roles: None" in summary

    def test_summary_with_non_dict_approval_gates(self):
        org = {"name": "test-org", "approval_gate_roles": "not-a-dict"}
        with pytest.raises(AttributeError):
            rbac.get_rbac_policy_summary(org)

    def test_summary_with_invalid_approval_count_type(self):
        org = {"name": "test-org", "approval_gate_roles": {"Admin": "two approvers"}}
        with pytest.raises(TypeError):
            rbac.get_rbac_policy_summary(org)

    def test_summary_with_zero_approvers(self):
        org = {"name": "test-org", "approval_gate_roles": {"Admin": 0}}
        summary = rbac.get_rbac_policy_summary(org)
        assert "requires 0 approver" in summary

    def test_summary_with_unsorted_roles(self):
        org = {"name": "test-org", "allowed_roles": ["Zebra", "Alpha", "Beta"]}
        summary = rbac.get_rbac_policy_summary(org)
        assert summary.find("Alpha") < summary.find("Beta") < summary.find("Zebra")


class TestNativeAuditLog:
    """The moved functions log to the single native audit log (~/.cloudctl/audit.log)."""

    def test_audit_log_records_decision(self, tmp_path):
        with patch.object(rbac, "AUDIT_LOG", tmp_path / "audit.log"):
            rbac._audit_log("test-org", "ReadOnly", "GRANTED account=123456789012")
            content = (tmp_path / "audit.log").read_text()
            assert "test-org" in content
            assert "ReadOnly" in content
            assert "123456789012" in content

    def test_audit_log_appends(self, tmp_path):
        log_file = tmp_path / "audit.log"
        with patch.object(rbac, "AUDIT_LOG", log_file):
            rbac._audit_log("org1", "Role1", "GRANTED")
            rbac._audit_log("org2", "Role2", "DENIED")
            lines = log_file.read_text().strip().split("\n")
            assert len(lines) == 2
            assert "org1" in lines[0]
            assert "org2" in lines[1]

    def test_audit_log_special_characters(self, tmp_path):
        with patch.object(rbac, "AUDIT_LOG", tmp_path / "audit.log"):
            rbac._audit_log("org|name", "Role|Name", "reason | with\nnewline")
            content = (tmp_path / "audit.log").read_text()
            assert "org|name" in content
            assert "Role|Name" in content

    def test_audit_log_disk_full_is_swallowed(self, tmp_path):
        with patch.object(rbac, "AUDIT_LOG", tmp_path / "audit.log"):
            with patch("builtins.open", side_effect=OSError("No space left on device")):
                rbac._audit_log("org", "Role", "GRANTED")  # must not raise

    def test_audit_log_permission_denied_is_swallowed(self, tmp_path):
        log_file = tmp_path / "audit.log"
        log_file.write_text("existing content\n")
        log_file.chmod(0o000)
        with patch.object(rbac, "AUDIT_LOG", log_file):
            rbac._audit_log("org", "Role", "GRANTED")  # must not raise
        log_file.chmod(0o600)  # restore so tmp cleanup works


class TestAuditLogEntries:
    def test_entries_nonexistent_file(self):
        with patch.object(rbac, "AUDIT_LOG", Path("/nonexistent/path/audit.log")):
            assert rbac.audit_log_entries() == []

    def test_entries_returns_and_filters(self, tmp_path):
        log_file = tmp_path / "audit.log"
        with patch.object(rbac, "AUDIT_LOG", log_file):
            rbac._audit_log("test-org", "ReadOnly", "GRANTED")
            rbac._audit_log("other-org", "Admin", "DENIED")
            assert len(rbac.audit_log_entries()) == 2
            org_entries = rbac.audit_log_entries(org_name="test-org")
            assert len(org_entries) == 1
            assert "test-org" in org_entries[0]

    def test_entries_corrupted_encoding(self, tmp_path):
        log_file = tmp_path / "audit.log"
        log_file.write_bytes(b"Valid line\n\xff\xfe Invalid UTF-8\nAnother line\n")
        with patch.object(rbac, "AUDIT_LOG", log_file):
            with pytest.raises(UnicodeDecodeError):
                rbac.audit_log_entries()

    def test_entries_empty_file(self, tmp_path):
        log_file = tmp_path / "audit.log"
        log_file.write_text("")
        with patch.object(rbac, "AUDIT_LOG", log_file):
            assert rbac.audit_log_entries() == []

    def test_entries_only_whitespace(self, tmp_path):
        log_file = tmp_path / "audit.log"
        log_file.write_text("   \n\n  \n")
        with patch.object(rbac, "AUDIT_LOG", log_file):
            assert rbac.audit_log_entries() == []


class TestGetAuditLogPath:
    def test_path_is_native_cloudctl_log(self):
        path = rbac.get_audit_log_path()
        assert isinstance(path, Path)
        assert path.is_absolute()
        assert ".cloudctl" in str(path)
        assert "audit.log" in str(path)


class TestConcurrency:
    def test_concurrent_log_writes(self, tmp_path):
        import threading

        log_file = tmp_path / "audit.log"
        with patch.object(rbac, "AUDIT_LOG", log_file):

            def write_log(index):
                for i in range(10):
                    rbac._audit_log(f"org{index}", f"role{i}", f"GRANTED acc{index}{i}")

            threads = [threading.Thread(target=write_log, args=(i,)) for i in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            lines = log_file.read_text().strip().split("\n")
            assert len(lines) == 50
