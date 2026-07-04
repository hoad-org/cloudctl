"""Consistent output formatting for CLI responses.

All CLI commands use this module for:
- Success responses (JSON to stdout)
- Error responses (JSON to stderr)
- Progress messages (human text to stderr, suppressible)
"""

import json
import sys
import logging
from typing import Any, Dict, Optional
from datetime import datetime


class OutputFormatter:
    """Format CLI output consistently across all commands."""

    def __init__(self, quiet: bool = False):
        """
        Initialize formatter.

        Args:
            quiet: Suppress progress messages to stderr
        """
        self.quiet = quiet
        self.logger = logging.getLogger(__name__)

    def success_json(self, data: Dict[str, Any]) -> None:
        """
        Output successful response as JSON to stdout.

        Args:
            data: Response dict (will be serialized to JSON)

        Format:
            Single line JSON, no pretty-printing
            Example:
            {"status":"success","organization":"prod","expires_at":"2026-06-02T17:30:00Z"}
        """
        # Add timestamp if not present
        if "timestamp" not in data:
            data["timestamp"] = datetime.utcnow().isoformat() + "Z"

        # Ensure 'status' is present
        if "status" not in data:
            data["status"] = "success"

        json_str = json.dumps(data, separators=(",", ":"), default=str)
        print(json_str)

    def error_json(
        self,
        error_code: str,
        message: str,
        exit_code: int,
        context: Optional[Dict] = None,
    ) -> None:
        """
        Output error response as JSON to stderr.

        Args:
            error_code: Machine-readable error code (e.g., "RATE_LIMITED")
            message: Human-readable error message
            exit_code: CLI exit code (1-255)
            context: Additional diagnostic data (no secrets!)

        Format:
            Single line JSON to stderr
            Example:
            {"error":"RATE_LIMITED","code":4,"message":"Max 5 credentials per hour","retry_after_seconds":2700}
        """
        error_dict = {
            "error": error_code,
            "code": exit_code,
            "message": message,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

        if context:
            error_dict.update(context)

        json_str = json.dumps(error_dict, separators=(",", ":"), default=str)
        print(json_str, file=sys.stderr)

    def progress(self, message: str, level: str = "info") -> None:
        """
        Output progress message to stderr (human-readable).

        Args:
            message: Progress message
            level: Log level ("info", "warning", "error")

        Behavior:
            - Only prints if not in quiet mode
            - Goes to stderr (not stdout)
            - Human-readable format (no JSON)

        Example:
            formatter.progress("Opening browser for authentication...")
            formatter.progress("✓ Authorization complete")
        """
        if self.quiet:
            return

        if level == "info":
            self.logger.info(message)
            print(f"INFO: {message}", file=sys.stderr)
        elif level == "warning":
            self.logger.warning(message)
            print(f"WARNING: {message}", file=sys.stderr)
        elif level == "error":
            self.logger.error(message)
            print(f"ERROR: {message}", file=sys.stderr)


# Global instance (can be overridden per command)
_formatter = OutputFormatter()


def get_formatter(quiet: bool = False) -> OutputFormatter:
    """Get a formatter instance."""
    return OutputFormatter(quiet=quiet)
