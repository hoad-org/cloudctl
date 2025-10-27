# file: awsctl/__main__.py
# isort: skip_file
# SPDX-License-Identifier: MIT
"""Module entrypoint for `python -m awsctl`."""

from __future__ import annotations

from .cli import main as _main


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())
