"""
Back-compat installer for shell integration.

This module is kept to avoid breaking older docs/links.
It now delegates to the single authoritative function in awsctl.cli
to prevent drift between two implementations.
"""

from __future__ import annotations

import sys
from typing import NoReturn

# Reuse the CLI implementation to avoid drift
from awsctl.cli import detect_shell_profile, inject_shell_function


def install_shell_function() -> None:
    """Inject awsctl shell function into the user's shell rc file by delegating to cli."""
    rc_file = detect_shell_profile()
    inject_shell_function(rc_file)
    print("✅ awsctl shell integration installed via delegated installer. Restart your shell.")


def main() -> NoReturn:
    try:
        install_shell_function()
        # FIX: Add an explicit exit to satisfy the NoReturn type hint
        raise SystemExit(0)
    except Exception as e:
        print(f"⚠️ Failed to install shell integration: {e}", file=sys.stderr)
        raise SystemExit(1) from e


if __name__ == "__main__":
    main()
