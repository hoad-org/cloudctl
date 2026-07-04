"""Root conftest: pre-load cloudctl.__main__ so test_coverage_final can reload it."""

import sys
from unittest.mock import patch

# Pre-load cloudctl.__main__ with main patched out so the module body is safe to execute.
# This ensures sys.modules["cloudctl.__main__"] exists before test_main_entrypoint_coverage runs.
# __main__.py runs `sys.exit(main(...))`; with main patched to return 0 that raises
# SystemExit(0), which we swallow here (importing it for its side effect only).
with patch("cloudctl.main.main", return_value=0):
    import importlib

    if "cloudctl.__main__" not in sys.modules:
        try:
            importlib.import_module("cloudctl.__main__")
        except SystemExit:
            pass
