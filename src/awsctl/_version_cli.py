# SPDX-License-Identifier: MIT
"""
Tiny console entry that prints only the version to stdout.
Used for robust testing where shell shims may vary.
"""

from __future__ import annotations

try:
    from ._version import __version__
except ImportError:
    __version__ = "0.0.0"


def main() -> int:
    print(__version__ or "0.0.0")
    return 0
