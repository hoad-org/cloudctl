"""Output sanitization for cloudctl:exec skill (Phase 3).

Redacts secrets from command output before logging to audit trail.
Prevents accidental credential exposure in immutable audit logs.
"""

import re
import hashlib
from typing import Tuple


class OutputSanitizer:
    """Redact sensitive data from command output.

    Patterns redacted:
    - AWS_SECRET_ACCESS_KEY=...
    - AWS_ACCESS_KEY_ID=... (leave first 4 chars visible)
    - PRIVATE_KEY blocks
    - API tokens
    - Bearer tokens
    """

    # Redaction patterns (secret_type, regex_pattern)
    DEFAULT_PATTERNS = [
        (
            "AWS_SECRET_ACCESS_KEY",
            r"AWS_SECRET_ACCESS_KEY=([^\s\n]+)",
        ),
        (
            "AWS_ACCESS_KEY_ID",
            r"AKIA[\dA-Z]{16}",  # AWS access key format
        ),
        (
            "PRIVATE_KEY",
            r"-----BEGIN RSA PRIVATE KEY-----[\s\S]*?-----END RSA PRIVATE KEY-----",
        ),
        (
            "PRIVATE_KEY",
            r"-----BEGIN PRIVATE KEY-----[\s\S]*?-----END PRIVATE KEY-----",
        ),
        (
            "BEARER_TOKEN",
            r"Bearer\s+([a-zA-Z0-9._-]+)",
        ),
        (
            "API_TOKEN",
            r"(api[_-]?key|token|authorization)[\s:=]+([^\s\n,;]+)",
        ),
        (
            "PASSWORD",
            r"password[\s:=]+([^\s\n,;]+)",
        ),
        (
            "GITHUB_TOKEN",
            r"ghp_[a-zA-Z0-9_]{36,255}",
        ),
    ]

    def __init__(self, patterns: list = None):
        """Initialize output sanitizer.

        Args:
            patterns: List of (secret_type, regex_pattern) tuples
        """
        self.patterns = patterns or self.DEFAULT_PATTERNS

    def sanitize(self, output: str) -> str:
        """Redact sensitive data from output.

        Args:
            output: Command output (stdout/stderr)

        Returns:
            Sanitized output with secrets replaced by ***REDACTED***
        """
        sanitized = output

        for secret_type, pattern in self.patterns:
            sanitized = re.sub(
                pattern,
                f"***REDACTED_{secret_type}***",
                sanitized,
                flags=re.IGNORECASE | re.MULTILINE,
            )

        return sanitized

    def hash_output(self, output: str) -> str:
        """Compute SHA256 hash of output.

        Used to detect tampering while keeping audit trail small.

        Args:
            output: Output to hash (use original, not sanitized)

        Returns:
            SHA256 hash in hex format
        """
        return hashlib.sha256(output.encode()).hexdigest()

    def redact_secrets(self, output: str) -> Tuple[str, str]:
        """Redact secrets and compute hash.

        Args:
            output: Original command output

        Returns:
            (sanitized_output, output_hash)
        """
        sanitized = self.sanitize(output)
        output_hash = self.hash_output(output)
        return sanitized, output_hash

    def has_redactions(self, original: str, sanitized: str) -> bool:
        """Check if any redactions were made.

        Args:
            original: Original output
            sanitized: Sanitized output

        Returns:
            True if redactions were made (original != sanitized)
        """
        return original != sanitized

    def get_redaction_summary(self, original: str, sanitized: str) -> dict:
        """Get summary of what was redacted.

        Args:
            original: Original output
            sanitized: Sanitized output

        Returns:
            {
                "redacted": bool,
                "redaction_count": int,
                "secret_types": ["AWS_SECRET_ACCESS_KEY", ...],
            }
        """
        if original == sanitized:
            return {"redacted": False, "redaction_count": 0, "secret_types": []}

        # Count redactions by counting ***REDACTED_TYPE*** in sanitized
        secret_types = []
        redaction_count = 0
        for secret_type, pattern in self.patterns:
            matches = len(
                re.findall(pattern, original, flags=re.IGNORECASE | re.MULTILINE)
            )
            if matches > 0:
                secret_types.append(secret_type)
                redaction_count += matches

        return {
            "redacted": True,
            "redaction_count": redaction_count,
            "secret_types": list(set(secret_types)),  # Deduplicate
        }
