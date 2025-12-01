# file: src/awsctl/__init__.py
# SPDX-License-Identifier: MIT
"""
awsctl package metadata and console entrypoint.

- This is __init__.py.
- Console script in pyproject.toml points here: awsctl = "awsctl:main".
"""

from __future__ import annotations

import sys
from importlib.metadata import PackageNotFoundError

# 1. Try to import the auto-generated version from setuptools_scm
try:
    from ._version import version as __version__
except ImportError:
    # Fallback if package is not installed and _version.py doesn't exist yet
    __version__ = "0.0.0"

__all__ = ["__version__", "main"]


def _resolved_version() -> str:
    """
    Resolve the version dynamically.
    Priority:
    1. importlib.metadata (Installed Package)
    2. src/awsctl/_version.py (Editable Install / Build)
    3. Default "0.0.0"
    """
    try:
        from importlib.metadata import version as pkg_version

        v = pkg_version("awsctl").strip()
        if v:
            return v
    # Catch specific error if package is not installed/resolvable
    except PackageNotFoundError:
        pass

    return __version__


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
    from awsctl.cli import main as _cli_main

    return int(_cli_main(argv))
