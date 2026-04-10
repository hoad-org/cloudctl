"""
tests/test_upgrade.py — Unit tests for `awsctl upgrade`.

cmd_upgrade flow:
  1. Requires GITHUB_TOKEN — returns 1 without it
  2. Queries GitHub Releases API for latest release
  3. Finds .whl asset in release assets
  4. Downloads wheel to temp file via asset API URL (Accept: application/octet-stream)
  5. pip install --upgrade <tmp.whl> --extra-index-url https://pypi.org/simple/
  6. Cleans up temp file
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch


import awsctl.cli as cli

# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

FAKE_RELEASE = {
    "tag_name": "v3.1.0",
    "assets": [
        {
            "name": "awsctl-3.1.0-py3-none-any.whl",
            "url": "https://api.github.com/repos/ORG/REPO/releases/assets/12345",
        },
        {
            "name": "awsctl-3.1.0.tar.gz",
            "url": "https://api.github.com/repos/ORG/REPO/releases/assets/12346",
        },
    ],
}

FAKE_WHEEL_BYTES = b"PK fake wheel content"


def _make_urlopen_mock(release_json, wheel_bytes):
    """Build a context-manager mock for urllib.request.urlopen."""

    class _FakeResponse:
        def __init__(self, data: bytes):
            self._data = data

        def read(self):
            return self._data

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

    call_count = [0]

    def _urlopen(req):
        call_count[0] += 1
        if call_count[0] == 1:
            # First call → GitHub Releases API
            return _FakeResponse(json.dumps(release_json).encode())
        else:
            # Second call → wheel asset download
            return _FakeResponse(wheel_bytes)

    return _urlopen


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestCmdUpgradeSuccess:
    def test_success_downloads_and_installs_wheel(self):
        """End-to-end happy path: token set, release found, wheel downloaded, pip ok."""
        fake_urlopen = _make_urlopen_mock(FAKE_RELEASE, FAKE_WHEEL_BYTES)
        mock_pip = MagicMock()
        mock_pip.returncode = 0
        messages = []
        mock_console = MagicMock()
        mock_console.print.side_effect = lambda m, **_: messages.append(str(m))

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            with patch("subprocess.run", return_value=mock_pip):
                with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_test"}, clear=False):
                    with patch.object(cli, "console", mock_console):
                        rc = cli.cmd_upgrade(None)

        assert rc == 0
        assert any("v3.1.0" in m for m in messages)
        assert any("upgraded" in m.lower() for m in messages)

    def test_pip_receives_extra_index_url(self):
        """pip must be called with --extra-index-url so transitive deps resolve."""
        fake_urlopen = _make_urlopen_mock(FAKE_RELEASE, FAKE_WHEEL_BYTES)
        mock_pip = MagicMock()
        mock_pip.returncode = 0

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            with patch("subprocess.run", return_value=mock_pip) as mock_run:
                with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_test"}, clear=False):
                    with patch.object(cli, "console", MagicMock()):
                        cli.cmd_upgrade(None)

        argv = mock_run.call_args[0][0]
        assert "--extra-index-url" in argv
        assert any("pypi.org/simple" in str(a) for a in argv)

    def test_uses_sys_executable(self):
        """pip must be called via sys.executable, not a bare 'python' string."""
        fake_urlopen = _make_urlopen_mock(FAKE_RELEASE, FAKE_WHEEL_BYTES)
        mock_pip = MagicMock()
        mock_pip.returncode = 0

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            with patch("subprocess.run", return_value=mock_pip) as mock_run:
                with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_test"}, clear=False):
                    with patch.object(cli, "console", MagicMock()):
                        cli.cmd_upgrade(None)

        argv = mock_run.call_args[0][0]
        assert argv[0] == sys.executable

    def test_temp_file_cleaned_up_on_success(self):
        """Temp wheel file must be deleted after successful install."""
        fake_urlopen = _make_urlopen_mock(FAKE_RELEASE, FAKE_WHEEL_BYTES)
        mock_pip = MagicMock()
        mock_pip.returncode = 0
        created_paths = []

        real_mktemp = __import__("tempfile").NamedTemporaryFile

        def capture_tmp(*a, **kw):
            f = real_mktemp(*a, **kw)
            created_paths.append(f.name)
            return f

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            with patch("subprocess.run", return_value=mock_pip):
                with patch("tempfile.NamedTemporaryFile", side_effect=capture_tmp):
                    with patch.dict(
                        os.environ, {"GITHUB_TOKEN": "ghp_test"}, clear=False
                    ):
                        with patch.object(cli, "console", MagicMock()):
                            cli.cmd_upgrade(None)

        # All temp files should have been deleted
        for p in created_paths:
            assert not os.path.exists(p), f"Temp file {p} was not cleaned up"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestCmdUpgradeErrors:
    def test_returns_1_without_token(self):
        """Without GITHUB_TOKEN cmd_upgrade returns 1 immediately."""
        env_clean = {k: v for k, v in os.environ.items() if k != "GITHUB_TOKEN"}
        with patch.dict(os.environ, env_clean, clear=True):
            messages = []
            mock_console = MagicMock()
            mock_console.print.side_effect = lambda m, **_: messages.append(str(m))
            with patch.object(cli, "console", mock_console):
                rc = cli.cmd_upgrade(None)

        assert rc == 1
        assert any("GITHUB_TOKEN" in m for m in messages)

    def test_returns_1_on_api_http_error(self):
        """If the GitHub API returns a non-200, cmd_upgrade reports error and returns 1."""
        import urllib.error

        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.HTTPError(
                url="https://api.github.com/...",
                code=404,
                msg="Not Found",
                hdrs=None,
                fp=None,
            ),
        ):
            with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_test"}, clear=False):
                with patch.object(cli, "console", MagicMock()):
                    rc = cli.cmd_upgrade(None)

        assert rc == 1

    def test_returns_1_when_no_whl_asset(self):
        """If the release has no .whl asset, cmd_upgrade reports error and returns 1."""
        release_no_whl = {
            "tag_name": "v3.1.0",
            "assets": [{"name": "awsctl-3.1.0.tar.gz", "url": "..."}],
        }
        fake_urlopen = _make_urlopen_mock(release_no_whl, b"")

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_test"}, clear=False):
                messages = []
                mock_console = MagicMock()
                mock_console.print.side_effect = lambda m, **_: messages.append(str(m))
                with patch.object(cli, "console", mock_console):
                    rc = cli.cmd_upgrade(None)

        assert rc == 1
        assert any("whl" in m.lower() or "asset" in m.lower() for m in messages)

    def test_pip_failure_propagated(self):
        """When pip returns non-zero, cmd_upgrade returns that exit code."""
        fake_urlopen = _make_urlopen_mock(FAKE_RELEASE, FAKE_WHEEL_BYTES)
        mock_pip = MagicMock()
        mock_pip.returncode = 2

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            with patch("subprocess.run", return_value=mock_pip):
                with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_test"}, clear=False):
                    with patch.object(cli, "console", MagicMock()):
                        rc = cli.cmd_upgrade(None)

        assert rc == 2


# ---------------------------------------------------------------------------
# Dispatch / parser
# ---------------------------------------------------------------------------


class TestCmdUpgradeDispatch:
    def test_in_dispatch_table(self):
        assert "upgrade" in cli._DISPATCH
        assert cli._DISPATCH["upgrade"] == "cmd_upgrade"

    def test_main_routes_upgrade(self):
        """main(['upgrade']) with token set must invoke cmd_upgrade and return 0."""
        fake_urlopen = _make_urlopen_mock(FAKE_RELEASE, FAKE_WHEEL_BYTES)
        mock_pip = MagicMock()
        mock_pip.returncode = 0

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            with patch("subprocess.run", return_value=mock_pip):
                with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_test"}, clear=False):
                    with patch.object(cli, "console", MagicMock()):
                        rc = cli.main(["upgrade"])

        assert rc == 0
