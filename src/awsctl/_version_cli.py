# file: awsctl/_version_cli.py
# SPDX-License-Identifier: MIT
"""
Tiny console entry that prints only the version to stdout.
Used for robust testing where shell shims may vary.
"""

from __future__ import annotations

from . import __version__


def main() -> int:
    print(__version__ or "0.0.0")
    return 0
