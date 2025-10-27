# file: awsctl/__init__.py
# SPDX-License-Identifier: MIT
"""
awsctl package metadata and console entrypoint.

- This is __init__.py.
- Console script in pyproject.toml points here: awsctl = "awsctl:main".
"""

from __future__ import annotations

import sys

__all__ = ["__version__", "main"]

# Keep in sync with pyproject.toml
__version__ = "1.2.0"


def _resolved_version() -> str:
    try:
        from importlib.metadata import version as pkg_version

        v = pkg_version("awsctl").strip()
        if v:
            return v
    except Exception:
        pass
    # Fallback to package attribute to guarantee non-empty output
    return __version__ or "0.0.0"


def main(argv: list[str] | None = None) -> int:
    """
    Package-level entrypoint used by console_script.
    Handles --version early to avoid CLI import cycles or parser quirks.
    """
    if argv is None:
        argv = sys.argv[1:]

    if any(flag in argv for flag in ("--version", "-V")):
        sys.stdout.write(_resolved_version() + "\n")
        sys.stdout.flush()
        return 0

    # Import lazily to avoid side-effects during packaging introspection
    from .cli import main as _cli_main

    return _cli_main(argv)
