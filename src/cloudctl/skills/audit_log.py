"""Immutable audit logging for skill operations."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class AuditLog:
    """Write immutable audit log entries for skill operations."""

    def __init__(self, log_path: Optional[Path] = None):
        if log_path is None:
            log_path = Path("~/.cloudctl/audit.jsonl").expanduser()
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        skill: str,
        session_id: str,
        operation: str,
        org: Optional[str] = None,
        account: Optional[str] = None,
        role: Optional[str] = None,
        exit_code: int = 0,
        output_hash: Optional[str] = None,
        approval_id: Optional[str] = None,
    ) -> None:
        """Write audit log entry for skill operation."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session": session_id,
            "skill": skill,
            "operation": operation,
            "org": org,
            "account": account,
            "role": role,
            "exit_code": exit_code,
            "output_hash": output_hash,
            "approval_id": approval_id,
            "user": os.environ.get("USER", "unknown"),
        }
        with open(self.log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def read(self, limit: int = 100) -> list[dict]:
        """Read recent audit entries."""
        if not self.log_path.exists():
            return []
        entries = []
        with open(self.log_path, "r") as f:
            for line in f.readlines()[-limit:]:
                if line.strip():
                    entries.append(json.loads(line))
        return entries
