# file: awsctl/__main__.py
# isort: skip_file
# SPDX-License-Identifier: MIT
"""Module entrypoint for `python -m awsctl`."""

from __future__ import annotations

# Changed to absolute import path to resolve mypy's attribute error
from awsctl.cli import main as _main


if __name__ == "__main__":  # pragma: no cover
    # Cast exit code to int to satisfy NoReturn function signature if applicable,
    # and to fix potential remaining return type issues.
    raise SystemExit(int(_main()))
