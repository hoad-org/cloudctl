"""cloudctl:read skill — Safe, read-only access to cloudctl operations.

Provides:
- org list          # List configured organizations
- env               # Show active context
- accounts <org>    # List accounts in organization
- status            # Show status
- doctor            # System health check

Zero-risk operations with full audit trail and rate limiting.
"""

import json
import os
import subprocess
import sys
from typing import Optional

from cloudctl.skills.audit_log import AuditLog
from cloudctl.skills.rate_limit import RateLimit


class CloudctlReadSkill:
    """Read-only skill for safe cloudctl operations."""

    RATE_LIMIT_OPS_PER_MIN = 100

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.audit = AuditLog()
        self.rate_limiter = RateLimit(
            max_ops=self.RATE_LIMIT_OPS_PER_MIN, window_seconds=60
        )

    def _check_rate_limit(self) -> tuple[bool, Optional[str]]:
        """Check if operation is within rate limit."""
        allowed, error = self.rate_limiter.check(self.session_id)
        if not allowed:
            self.audit.log(
                skill="cloudctl:read",
                session_id=self.session_id,
                operation="rate_limit_exceeded",
                exit_code=429,
            )
        return allowed, error

    def _run_cloudctl(self, *args: str) -> dict:
        """Run cloudctl command and capture output."""
        try:
            result = subprocess.run(
                ["cloudctl"] + list(args),
                capture_output=True,
                text=True,
                timeout=10,
            )
            return {
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except subprocess.TimeoutExpired:
            return {
                "exit_code": 124,
                "stdout": "",
                "stderr": "cloudctl command timed out",
            }
        except FileNotFoundError:
            return {
                "exit_code": 127,
                "stdout": "",
                "stderr": "cloudctl command not found",
            }

    def org_list(self) -> dict:
        """List configured organizations."""
        allowed, error = self._check_rate_limit()
        if not allowed:
            return {"exit_code": 429, "error": error}

        result = self._run_cloudctl("org", "list")
        self.audit.log(
            skill="cloudctl:read",
            session_id=self.session_id,
            operation="org_list",
            exit_code=result["exit_code"],
        )
        return result

    def env(self) -> dict:
        """Show active context."""
        allowed, error = self._check_rate_limit()
        if not allowed:
            return {"exit_code": 429, "error": error}

        result = self._run_cloudctl("env")
        self.audit.log(
            skill="cloudctl:read",
            session_id=self.session_id,
            operation="env",
            exit_code=result["exit_code"],
        )
        return result

    def accounts(self, org: str) -> dict:
        """List accounts in organization."""
        allowed, error = self._check_rate_limit()
        if not allowed:
            return {"exit_code": 429, "error": error}

        if not org:
            return {"exit_code": 1, "error": "org argument required"}

        result = self._run_cloudctl("accounts", org)
        self.audit.log(
            skill="cloudctl:read",
            session_id=self.session_id,
            operation="accounts",
            org=org,
            exit_code=result["exit_code"],
        )
        return result

    def status(self) -> dict:
        """Show status."""
        allowed, error = self._check_rate_limit()
        if not allowed:
            return {"exit_code": 429, "error": error}

        result = self._run_cloudctl("status")
        self.audit.log(
            skill="cloudctl:read",
            session_id=self.session_id,
            operation="status",
            exit_code=result["exit_code"],
        )
        return result

    def doctor(self) -> dict:
        """System health check."""
        allowed, error = self._check_rate_limit()
        if not allowed:
            return {"exit_code": 429, "error": error}

        result = self._run_cloudctl("doctor")
        self.audit.log(
            skill="cloudctl:read",
            session_id=self.session_id,
            operation="doctor",
            exit_code=result["exit_code"],
        )
        return result

    def execute(self, command: str, *args: str) -> dict:
        """Execute a read-only command."""
        if command == "org_list":
            return self.org_list()
        elif command == "env":
            return self.env()
        elif command == "accounts":
            return self.accounts(args[0] if args else "")
        elif command == "status":
            return self.status()
        elif command == "doctor":
            return self.doctor()
        else:
            return {
                "exit_code": 1,
                "error": f"Unknown command: {command}. Allowed: org_list, env, accounts, status, doctor",
            }


def main():
    """Entry point for skill runtime."""
    session_id = os.environ.get("CLAUDE_SESSION_ID", "unknown")
    skill = CloudctlReadSkill(session_id)

    if len(sys.argv) < 2:
        result = {
            "exit_code": 1,
            "error": "Usage: cloudctl_read_skill <command> [args]",
        }
    else:
        command = sys.argv[1]
        args = sys.argv[2:] if len(sys.argv) > 2 else ()
        result = skill.execute(command, *args)

    print(json.dumps(result, indent=2))
    sys.exit(result.get("exit_code", 1))


if __name__ == "__main__":
    main()
