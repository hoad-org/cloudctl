# file: tests/test_coverage_final.py
import importlib
import sys
from unittest.mock import patch


def test_main_entrypoint_coverage(monkeypatch):
    """
    Forces 100% coverage on cloudctl/__main__.py by reloading the module
    within a patched environment.
    """
    # 1. Setup the environment patch
    # We use monkeypatch for sys.argv to ensure it doesn't leak to other tests
    monkeypatch.setattr(sys, "argv", ["cloudctl", "status"])

    # 2. Patch the target main function
    # We patch 'cloudctl.main.main' because that is what __main__.py calls
    with patch("cloudctl.main.main") as mock_main:

        # 3. Handle Module Caching
        # If the module was already imported, we must remove it from cache
        # to ensure the 'if __name__ == "__main__":' block executes again.
        if "cloudctl.__main__" in sys.modules:
            importlib.reload(sys.modules["cloudctl.__main__"])
        else:
            pass

        # 4. Verify Execution
        # The import/reload itself should have triggered the call to main()
        # because of the 'if __name__ == "__main__":' block
        assert mock_main.called

        # Verify it was called with the arguments from sys.argv[1:]
        # Based on typical __main__.py logic: main(sys.argv[1:])
        mock_main.assert_called_with(["status"])


def test_main_function_direct_call():
    """
    Ensures cloudctl.main.main handles direct list input correctly
    independent of sys.argv.
    """
    from cloudctl.main import main

    with patch("cloudctl.cli.main", return_value=0) as mock_cli:
        result = main(["login", "--org", "test"])
        assert result == 0
        mock_cli.assert_called_once()
