"""Command filtering for cloudctl:exec skill (Phase 3).

Enforces whitelist/blacklist for cloud CLI commands.
Secure default: deny all commands not explicitly whitelisted.
"""

from typing import Tuple, List


class CommandFilter:
    """Filter and validate cloud CLI commands (AWS, Azure, GCP).

    Pattern matching:
    - Whitelist: AWS describe-*, list-*, get-* (read-only operations)
    - Blacklist: Dangerous operations (delete, terminate, destroy, etc.)
    - Unknown commands: DENIED (fail-closed)
    """

    # Default whitelist patterns (safe, read-only operations)
    DEFAULT_WHITELIST = [
        "aws describe-*",
        "aws list-*",
        "aws get-*",
        "aws ec2 describe-*",
        "aws s3 ls",
        "aws s3api list-*",
        "aws iam list-*",
        "aws iam get-*",
        "terraform plan",
        "terraform validate",
        "terraform show",
        "azure account show",
        "azure resource group list",
        "gcloud describe",
        "gcloud list",
    ]

    # Default blacklist patterns (dangerous operations)
    DEFAULT_BLACKLIST = [
        "aws ec2 terminate-*",
        "aws ec2 stop-instances",
        "aws ec2 reboot-instances",
        "aws iam delete-*",
        "aws iam put-*",
        "aws s3api delete-*",
        "aws s3api delete-object",
        "aws s3 rm",
        "aws cloudformation delete-*",
        "terraform apply",
        "terraform destroy",
        "terraform taint",
        "azure resource delete",
        "gcloud compute instances delete",
    ]

    def __init__(
        self,
        whitelist: List[str] = None,
        blacklist: List[str] = None,
    ):
        """Initialize command filter.

        Args:
            whitelist: List of allowed command patterns (default: DEFAULT_WHITELIST)
            blacklist: List of denied command patterns (default: DEFAULT_BLACKLIST)
        """
        self.whitelist = whitelist or self.DEFAULT_WHITELIST
        self.blacklist = blacklist or self.DEFAULT_BLACKLIST

    def _pattern_matches(self, command: str, pattern: str) -> bool:
        """Check if command matches a pattern (with * wildcard support).

        Args:
            command: Full command string (e.g., "aws describe-instances")
            pattern: Pattern with optional * wildcard (e.g., "aws describe-*")

        Returns:
            True if command matches pattern
        """
        if "*" not in pattern:
            # Exact match
            return command.lower() == pattern.lower()

        # Wildcard matching
        parts = pattern.lower().split("*")
        command_lower = command.lower()

        # Check if all parts exist in order
        pos = 0
        for part in parts:
            if part:  # Skip empty parts from leading/trailing *
                idx = command_lower.find(part, pos)
                if idx == -1:
                    return False
                pos = idx + len(part)

        # If pattern started with *, command must start with first part (if exists)
        if parts[0]:  # Pattern didn't start with *
            if not command_lower.startswith(parts[0]):
                return False

        return True

    def is_allowed(self, command: str) -> Tuple[bool, str]:
        """Check if a command is allowed to execute.

        Secure default: commands not in whitelist are DENIED.

        Args:
            command: Full command string (e.g., "aws s3 ls")

        Returns:
            (allowed: bool, reason: str)
        """
        # Check blacklist first (explicit deny)
        for pattern in self.blacklist:
            if self._pattern_matches(command, pattern):
                return False, f"Command denied by blacklist: {pattern}"

        # Check whitelist (explicit allow)
        for pattern in self.whitelist:
            if self._pattern_matches(command, pattern):
                return True, "Command allowed by whitelist"

        # Default: DENY (fail-closed)
        return False, "Command not in whitelist (unknown commands denied by default)"

    def filter_command(self, command: str) -> dict:
        """Filter and validate a command.

        Args:
            command: Full command string

        Returns:
            {
                "allowed": bool,
                "reason": str,
                "command": str,
                "category": "read" | "write" | "dangerous" | "unknown",
            }
        """
        allowed, reason = self.is_allowed(command)

        # Categorize command
        if command.lower().startswith("terraform plan") or command.lower().startswith(
            "terraform show"
        ):
            category = "read"
        elif "describe" in command or "list" in command or "get" in command:
            category = "read"
        elif any(
            pattern in command.lower() for pattern in ["delete", "destroy", "terminate"]
        ):
            category = "dangerous"
        elif any(pattern in command.lower() for pattern in ["create", "update", "put"]):
            category = "write"
        else:
            category = "unknown"

        return {
            "allowed": allowed,
            "reason": reason,
            "command": command,
            "category": category,
        }
