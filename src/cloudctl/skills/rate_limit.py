"""Rate limiting for skill operations with persistent storage."""

import json
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional


class RateLimit:
    """Enforce rate limits on skill operations with persistent state."""

    def __init__(
        self, max_ops: int, window_seconds: int, storage_dir: Optional[Path] = None
    ):
        """Initialize rate limiter.

        Args:
            max_ops: Maximum operations allowed
            window_seconds: Time window in seconds
            storage_dir: Directory to store rate limit state (default: ~/.cloudctl)
        """
        self.max_ops = max_ops
        self.window_seconds = window_seconds

        # Set storage directory
        if storage_dir is None:
            storage_dir = Path("~/.cloudctl").expanduser()
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.operations: deque = deque()

    def _get_state_file(self, session_id: str) -> Path:
        """Get the rate limit state file path for a session."""
        return self.storage_dir / f".ratelimit_{session_id}.json"

    def _load_state(self, session_id: str) -> None:
        """Load rate limit state from disk."""
        state_file = self._get_state_file(session_id)
        if state_file.exists():
            try:
                data = json.loads(state_file.read_text())
                # Convert ISO timestamps back to datetime objects
                self.operations = deque(
                    datetime.fromisoformat(ts) for ts in data.get("operations", [])
                )
            except Exception:
                # If file is corrupted, start fresh
                self.operations = deque()
        else:
            self.operations = deque()

    def _save_state(self, session_id: str) -> None:
        """Save rate limit state to disk."""
        state_file = self._get_state_file(session_id)
        data = {
            "operations": [ts.isoformat() for ts in self.operations],
            "max_ops": self.max_ops,
            "window_seconds": self.window_seconds,
        }
        state_file.write_text(json.dumps(data))

    def check(self, session_id: str) -> tuple[bool, Optional[str]]:
        """Check if operation is allowed under rate limit.

        Returns:
            (allowed, error_message)
        """
        # Load state from disk
        self._load_state(session_id)

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=self.window_seconds)

        # Remove old operations outside the window
        while self.operations and self.operations[0] < cutoff:
            self.operations.popleft()

        if len(self.operations) >= self.max_ops:
            oldest_op = self.operations[0]
            wait_time = (
                oldest_op + timedelta(seconds=self.window_seconds) - now
            ).total_seconds()
            wait_time = max(0.1, wait_time)  # Ensure at least 0.1s
            return False, f"Rate limit exceeded. Retry in {wait_time:.1f}s"

        self.operations.append(now)

        # Save state to disk
        self._save_state(session_id)

        return True, None

    def remaining(self) -> int:
        """Return remaining operations in current window."""
        return max(0, self.max_ops - len(self.operations))
