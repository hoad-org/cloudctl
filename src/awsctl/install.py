# file: src/awsctl/install.py
"""
Back-compat installer for shell integration.
Delegates to the authoritative function in awsctl.shell.
"""

from __future__ import annotations

import sys
from typing import NoReturn

# [FIX] Import directly from shell to avoid heavy CLI imports and circular deps
from awsctl.shell import detect_shell_profile, inject_shell_function


def install_shell_function() -> None:
    """Inject awsctl shell function into the user's shell rc file."""
    rc_file = detect_shell_profile()
    inject_shell_function(rc_file)
    print(
        "✅ awsctl shell integration installed via delegated installer. Restart your shell."
    )


def main() -> NoReturn:
    try:
        install_shell_function()
        raise SystemExit(0)
    except Exception as e:
        print(f"⚠️ Failed to install shell integration: {e}", file=sys.stderr)
        raise SystemExit(1) from e


if __name__ == "__main__":
    main()
