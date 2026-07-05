"""
Tests for break-glass reason secret redaction in the audit log.

A break-glass justification is free text supplied by a human (or an agent via
CLOUDCTL_BREAK_GLASS_REASON). If it accidentally contains a token/secret/
password/key, that value must never be written verbatim to ~/.cloudctl/audit.log.
"""

from cloudctl import guardrails


def test_redact_secrets_masks_token_value():
    assert guardrails._redact_secrets("token=abc123") == "token=***"


def test_redact_secrets_leaves_plain_reason_untouched():
    reason = "prod incident bridge, approved by on-call"
    assert guardrails._redact_secrets(reason) == reason


def test_audit_log_stores_reason_masked(tmp_path, monkeypatch):
    """A reason containing token=abc123 is written masked, not verbatim."""
    log_path = tmp_path / ".cloudctl" / "audit.log"
    monkeypatch.setattr(guardrails, "AUDIT_LOG", log_path)

    guardrails._audit_log("myorg", "AdministratorAccess", "token=abc123 please")

    content = log_path.read_text(encoding="utf-8")
    assert "abc123" not in content
    assert "token=***" in content
