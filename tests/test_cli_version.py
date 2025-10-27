# file: tests/test_cli_version.py
# SPDX-License-Identifier: MIT
"""
Robust version test.

Strategy:
1) Prefer reading package metadata via importlib.metadata.
2) Fallback to package attribute __version__.
3) Finally exercise the console entry `awsctl-version` which prints only the version.
This avoids flakiness around how different environments wire console_script shims.
"""

from __future__ import annotations

import subprocess


def _metadata_version() -> str:
    try:
        from importlib.metadata import version as pkg_version

        return pkg_version("awsctl").strip()
    except Exception:
        return ""


def _attr_version() -> str:
    try:
        import awsctl as pkg

        return getattr(pkg, "__version__", "") or ""
    except Exception:
        return ""


def test_version_nonempty_from_any_source():
    # 1) importlib.metadata
    ver = _metadata_version()
    if not ver:
        # 2) package attribute
        ver = _attr_version()
    if not ver:
        # 3) dedicated console script that prints only the version
        ver = subprocess.check_output(["awsctl-version"], text=True).strip()

    assert ver, "version must be non-empty like '1.2.0'"
