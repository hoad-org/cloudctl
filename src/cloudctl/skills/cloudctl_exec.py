"""cloudctl:exec skill — Execute cloud CLI commands with mandatory approval (Phase 3).

Provides:
- exec <org> <account> <role> <command> [--dry-run]  # Execute command with approval

Operations:
- All executions require explicit approval (security gate)
- Commands filtered through whitelist/blacklist
- Output sanitized (secrets redacted, hash computed)
- Execution timeout: 30 seconds
"""

import subprocess
import shlex
from typing import Optional

from cloudctl.skills.approval_client import ApprovalClient
from cloudctl.skills.audit_log import AuditLog
from cloudctl.skills.rate_limit import RateLimit
from cloudctl.skills.command_filter import CommandFilter
from cloudctl.skills.output_sanitizer import OutputSanitizer


class CloudctlExecSkill:
    """Execute cloud CLI commands with mandatory approval and output audit."""

    RATE_LIMIT_EXECS_PER_MIN = 20
    APPROVAL_TIMEOUT_SECONDS = 300
    EXECUTION_TIMEOUT_SECONDS = 30

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.audit = AuditLog()
        self.rate_limiter = RateLimit(
            max_ops=self.RATE_LIMIT_EXECS_PER_MIN, window_seconds=60
        )
        self.approval_client = ApprovalClient()
        self.command_filter = CommandFilter()
        self.output_sanitizer = OutputSanitizer()

    def _check_rate_limit(self) -> tuple[bool, Optional[str]]:
        """Check if operation is within rate limit (20 execs/min).

        Returns:
            (allowed, error_message)
        """
        allowed, error = self.rate_limiter.check(self.session_id)
        if not allowed:
            self.audit.log(
                skill="cloudctl:exec",
                session_id=self.session_id,
                operation="rate_limit_exceeded",
                exit_code=429,
            )
        return allowed, error

    def exec(
        self, org: str, account: str, role: str, command: str, dry_run: bool = False
    ) -> dict:
        """Execute a cloud CLI command with mandatory approval.

        Args:
            org: Organization name (e.g., "bt-avm", "fdr-gvc")
            account: AWS Account ID / Azure Subscription ID / GCP Project ID
            role: Role being assumed for execution
            command: Cloud CLI command to execute (e.g., "aws s3 ls")
            dry_run: If True, only validate (don't execute)

        Returns:
            {
                "exit_code": 0 | 1 | 403 | 429,
                "stdout": "...",
                "stderr": "...",
                "output_hash": "sha256...",
                "approval_id": "APPR-...",
                "redacted": bool,
                "error": "..." (if failed),
            }
        """
        # Check rate limit
        allowed, error = self._check_rate_limit()
        if not allowed:
            return {"exit_code": 429, "error": error}

        # Filter command (whitelist/blacklist check)
        filter_result = self.command_filter.filter_command(command)
        if not filter_result["allowed"]:
            self.audit.log(
                skill="cloudctl:exec",
                session_id=self.session_id,
                operation="exec",
                org=org,
                account=account,
                role=role,
                exit_code=403,
            )
            return {
                "exit_code": 403,
                "error": f"Command denied: {filter_result['reason']}",
                "command": command,
            }

        # Request approval (MANDATORY for all execs, Phase 3 difference from Phase 2)
        try:
            approval_id = self.approval_client.request_approval(
                skill="cloudctl:exec",
                operation="exec",
                org=org,
                role=role,
                reason=f"Execute '{command}' in {org}/{account} as {role}",
                num_approvers=1,
            )
        except Exception as e:
            return {"exit_code": 1, "error": f"Approval request failed: {e}"}

        # Poll for approval (blocking)
        try:
            approved = self.approval_client.poll_approval(
                approval_id, timeout=self.APPROVAL_TIMEOUT_SECONDS
            )
            if not approved:
                return {
                    "exit_code": 403,
                    "error": f"Approval denied or timed out (ID: {approval_id})",
                }
        except Exception as e:
            return {"exit_code": 1, "error": f"Approval polling failed: {e}"}

        # If dry-run, skip execution
        if dry_run:
            self.audit.log(
                skill="cloudctl:exec",
                session_id=self.session_id,
                operation="exec",
                org=org,
                account=account,
                role=role,
                exit_code=0,
                approval_id=approval_id,
            )
            return {
                "exit_code": 0,
                "message": f"[DRY-RUN] Would execute: {command}",
                "stdout": "",
                "stderr": "",
                "output_hash": "",
                "approval_id": approval_id,
                "redacted": False,
            }

        # Execute command in subprocess
        try:
            result = subprocess.run(
                shlex.split(command),
                capture_output=True,
                text=True,
                timeout=self.EXECUTION_TIMEOUT_SECONDS,
            )
            stdout = result.stdout
            stderr = result.stderr
            exit_code = result.returncode
        except subprocess.TimeoutExpired:
            stderr = f"Command timed out after {self.EXECUTION_TIMEOUT_SECONDS} seconds"
            stdout = ""
            exit_code = 124
        except Exception as e:
            stderr = str(e)
            stdout = ""
            exit_code = 1

        # Combine stdout/stderr for redaction
        full_output = stdout + stderr

        # Sanitize output (redact secrets, compute hash)
        sanitized_output, output_hash = self.output_sanitizer.redact_secrets(
            full_output
        )
        redaction_summary = self.output_sanitizer.get_redaction_summary(
            full_output, sanitized_output
        )

        # Audit the execution
        self.audit.log(
            skill="cloudctl:exec",
            session_id=self.session_id,
            operation="exec",
            org=org,
            account=account,
            role=role,
            exit_code=exit_code,
            output_hash=output_hash,
            approval_id=approval_id,
        )

        return {
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "sanitized_output": sanitized_output,
            "output_hash": output_hash,
            "approval_id": approval_id,
            "redacted": redaction_summary["redacted"],
            "redaction_summary": redaction_summary,
        }

    def execute(self, command: str, *args: str) -> dict:
        """Dispatch skill command.

        Args:
            command: "exec"
            *args: org, account, role, cloud_command, [--dry-run]

        Returns:
            Result dict
        """
        if command == "exec":
            if len(args) < 4:
                return {
                    "exit_code": 1,
                    "error": "exec requires org, account, role, command arguments",
                }

            org = args[0]
            account = args[1]
            role = args[2]
            cloud_command = args[3]
            dry_run = "--dry-run" in args

            return self.exec(org, account, role, cloud_command, dry_run=dry_run)
        else:
            return {"exit_code": 1, "error": f"Unknown command: {command}"}
