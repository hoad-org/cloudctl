"""Behavioral tests for the in-memory `--no-cache` mode.

The one new guarantee: with `--no-cache`, cloudctl writes NO SSO token to
disk this invocation. It either reuses an already-active cached session
read-only, or authenticates purely in memory via the device flow — and in the
in-memory path the SSO cache dir stays EMPTY while credentials are still vended
and injected into the child. A plain `login` (no --no-cache) must still write
the token (regression guard).
"""

from argparse import Namespace
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def aws_provider():
    from cloudctl.providers.aws import AwsProvider

    return AwsProvider()


@pytest.fixture
def aws_org():
    return {
        "name": "myorg",
        "provider": "aws",
        "partition": "aws",
        "sso_start_url": "https://myorg.awsapps.com/start",
        "sso_region": "eu-west-2",
    }


def _obtained_token_payload():
    """The in-memory payload _obtain_sso_token returns (writes nothing)."""
    return {
        "accessToken": "in-memory-token-xyz",
        "expiresAt": "2099-12-31T23:59:59Z",
        "clientId": "cid-123",
        "clientSecret": "csecret-123",
        "registrationExpiresAt": "2099-12-31T23:59:59Z",
        "refreshToken": "refresh-abc",
    }


# ---------------------------------------------------------------------------
# Provider-level: obtain vs write split
# ---------------------------------------------------------------------------


class TestAwsInMemoryAuth:
    def test_authenticate_in_memory_writes_nothing(
        self, aws_provider, aws_org, monkeypatch, mock_home
    ):
        """authenticate_in_memory returns a usable token WITHOUT touching the
        SSO cache dir."""
        from cloudctl import sso_cache as _sso_cache

        # Guard: write_sso_token must NOT be called on this path.
        write_spy = MagicMock()
        monkeypatch.setattr(_sso_cache, "write_sso_token", write_spy)
        monkeypatch.setattr(
            "cloudctl.providers.aws.write_sso_token", write_spy
        )
        monkeypatch.setattr(
            aws_provider, "_obtain_sso_token", lambda org: _obtained_token_payload()
        )

        tok = aws_provider.authenticate_in_memory(aws_org)

        # The token exposes the surface get_credentials/whoami consumers read.
        assert tok.accessToken == "in-memory-token-xyz"
        assert hasattr(tok, "expiresAt")
        assert not tok.is_expired()

        # Nothing was written to disk.
        write_spy.assert_not_called()
        cache_dir = mock_home / ".aws" / "sso" / "cache"
        assert list(cache_dir.glob("*.json")) == []

    def test_get_credentials_uses_passed_token_and_skips_load(
        self, aws_provider, aws_org, monkeypatch
    ):
        """When a token is passed, get_credentials must NOT call load_token and
        must use the passed token's accessToken."""

        def _boom(org):
            raise AssertionError("load_token must not be called when token passed")

        monkeypatch.setattr(aws_provider, "load_token", _boom)

        seen = {}

        def fake_run_aws(args):
            seen["args"] = args
            import json

            return {
                "returncode": 0,
                "stdout": json.dumps(
                    {
                        "roleCredentials": {
                            "accessKeyId": "AKIA",
                            "secretAccessKey": "sk",
                            "sessionToken": "st",
                        }
                    }
                ),
                "stderr": "",
            }

        monkeypatch.setattr("cloudctl.providers.aws.run_aws", fake_run_aws)

        class _Tok:
            accessToken = "passed-token-999"

        creds = aws_provider.get_credentials(
            aws_org, "111122223333", "Admin", "us-east-1", token=_Tok()
        )
        assert creds["AWS_ACCESS_KEY_ID"] == "AKIA"
        # The passed token was used for the portal call.
        assert "passed-token-999" in seen["args"]

    def test_get_credentials_no_token_falls_back_to_cache(
        self, aws_provider, aws_org, monkeypatch
    ):
        """With token=None (default), behaviour is unchanged: it loads from the
        cache exactly as before."""
        loaded = {"n": 0}

        class _Tok:
            accessToken = "cache-token-1"

        def fake_load(org):
            loaded["n"] += 1
            return _Tok()

        monkeypatch.setattr(aws_provider, "load_token", fake_load)

        def fake_run_aws(args):
            import json

            return {
                "returncode": 0,
                "stdout": json.dumps(
                    {
                        "roleCredentials": {
                            "accessKeyId": "AKIA",
                            "secretAccessKey": "sk",
                            "sessionToken": "st",
                        }
                    }
                ),
                "stderr": "",
            }

        monkeypatch.setattr("cloudctl.providers.aws.run_aws", fake_run_aws)

        aws_provider.get_credentials(aws_org, "111122223333", "Admin", "us-east-1")
        assert loaded["n"] == 1  # cache was consulted


# ---------------------------------------------------------------------------
# Regression guard: plain login STILL writes the token.
# ---------------------------------------------------------------------------


class TestPlainLoginStillWrites:
    def test_login_writes_token_to_cache(
        self, aws_provider, aws_org, monkeypatch, mock_home
    ):
        """A plain login (no --no-cache) must still persist the SSO token — the
        obtain/write split must not have removed the disk write."""
        from cloudctl.sso_cache import OrgRef, load_active_sso_token

        monkeypatch.setattr(
            aws_provider, "_obtain_sso_token", lambda org: _obtained_token_payload()
        )

        rc = aws_provider.login(aws_org)
        assert rc == 0

        cache_dir = mock_home / ".aws" / "sso" / "cache"
        files = list(cache_dir.glob("*.json"))
        assert len(files) == 1, "plain login must write exactly one cache file"

        token = load_active_sso_token(
            OrgRef(aws_org["name"], aws_org["sso_start_url"], aws_org["sso_region"])
        )
        assert token is not None
        assert token.accessToken == "in-memory-token-xyz"


# ---------------------------------------------------------------------------
# End-to-end exec/run --no-cache flow: proves zero disk-write.
# ---------------------------------------------------------------------------


class TestExecNoCacheZeroDiskWrite:
    def _args(self, **over):
        base = dict(
            exec_org="myorg",
            exec_account="111122223333",
            exec_role="Admin",
            exec_region="us-east-1",
            json_errors=False,
            no_cache=True,
            cmd=["printenv", "AWS_ACCESS_KEY_ID"],
        )
        base.update(over)
        return Namespace(**base)

    def test_run_no_cache_authenticates_in_memory_and_writes_nothing(
        self, aws_org, monkeypatch, mock_home, capsys
    ):
        """The canonical proof: --no-cache with no active session authenticates
        in-memory, the SSO cache dir is EMPTY afterward (write_sso_token never
        called / no file created), yet the child still receives vended creds."""
        from cloudctl.commands.exec import ExecCommand
        from cloudctl.providers.aws import AwsProvider
        from cloudctl import sso_cache as _sso_cache
        import cloudctl.providers.aws as _aws_mod

        # Real AwsProvider, but with the network boundary mocked out.
        provider = AwsProvider()

        # (1) No active session on disk.
        monkeypatch.setattr(provider, "load_token", lambda org: None)

        # (2) The device flow is faked to return a token IN MEMORY (writes
        #     nothing). _obtain_sso_token is the seam boto3 lives behind.
        monkeypatch.setattr(
            provider, "_obtain_sso_token", lambda org: _obtained_token_payload()
        )

        # (3) HARD guard: any call to write_sso_token is a failure.
        write_spy = MagicMock(
            side_effect=AssertionError("--no-cache must NOT write the SSO token")
        )
        monkeypatch.setattr(_sso_cache, "write_sso_token", write_spy)
        monkeypatch.setattr(_aws_mod, "write_sso_token", write_spy)

        # (4) The portal get-role-credentials call is faked to vend STS creds.
        def fake_run_aws(args):
            import json

            # The in-memory token must be the one used for the portal call.
            assert "in-memory-token-xyz" in args
            return {
                "returncode": 0,
                "stdout": json.dumps(
                    {
                        "roleCredentials": {
                            "accessKeyId": "AKIA-VENDED",
                            "secretAccessKey": "sk-vended",
                            "sessionToken": "st-vended",
                        }
                    }
                ),
                "stderr": "",
            }

        monkeypatch.setattr("cloudctl.providers.aws.run_aws", fake_run_aws)

        # Wire the exec layer to our org + provider.
        monkeypatch.setattr(
            "cloudctl.commands.exec.get_org", lambda name: aws_org
        )
        monkeypatch.setattr(
            "cloudctl.providers.get_provider", lambda org_data: provider
        )
        monkeypatch.setattr(
            "cloudctl.commands.exec.load_context", lambda: {}
        )

        # (5) Capture what the child actually receives in its env.
        captured_env = {}

        def fake_subprocess_run(cmd, env=None):
            captured_env.update(env or {})
            return MagicMock(returncode=0)

        monkeypatch.setattr(
            "cloudctl.commands.exec.subprocess.run", fake_subprocess_run
        )

        rc = ExecCommand().execute(self._args())

        assert rc == 0
        # Zero disk-write: never called AND the cache dir is empty.
        write_spy.assert_not_called()
        cache_dir = mock_home / ".aws" / "sso" / "cache"
        assert list(cache_dir.glob("*.json")) == [], (
            "SSO cache dir must be empty after a --no-cache run"
        )

        # Creds were still vended and injected into the child's env.
        assert captured_env.get("AWS_ACCESS_KEY_ID") == "AKIA-VENDED"
        assert captured_env.get("AWS_SESSION_TOKEN") == "st-vended"
        assert captured_env.get("AWS_REGION") == "us-east-1"

    def test_run_no_cache_reuses_active_session_without_reauth(
        self, aws_org, monkeypatch, mock_home
    ):
        """If an active session already exists on disk, --no-cache reuses it
        read-only and does NOT re-authenticate or write anything."""
        from cloudctl.commands.exec import ExecCommand
        from cloudctl.providers.aws import AwsProvider
        from cloudctl import sso_cache as _sso_cache
        import cloudctl.providers.aws as _aws_mod

        provider = AwsProvider()

        class _Tok:
            accessToken = "active-session-token"

        monkeypatch.setattr(provider, "load_token", lambda org: _Tok())
        # If in-memory auth is triggered, that's a bug — active session exists.
        monkeypatch.setattr(
            provider,
            "authenticate_in_memory",
            lambda org: (_ for _ in ()).throw(
                AssertionError("must not re-auth when a session exists")
            ),
        )
        write_spy = MagicMock(side_effect=AssertionError("must not write"))
        monkeypatch.setattr(_sso_cache, "write_sso_token", write_spy)
        monkeypatch.setattr(_aws_mod, "write_sso_token", write_spy)

        def fake_run_aws(args):
            import json

            assert "active-session-token" in args
            return {
                "returncode": 0,
                "stdout": json.dumps(
                    {
                        "roleCredentials": {
                            "accessKeyId": "AKIA-R",
                            "secretAccessKey": "sk",
                            "sessionToken": "st",
                        }
                    }
                ),
                "stderr": "",
            }

        monkeypatch.setattr("cloudctl.providers.aws.run_aws", fake_run_aws)
        monkeypatch.setattr("cloudctl.commands.exec.get_org", lambda name: aws_org)
        monkeypatch.setattr(
            "cloudctl.providers.get_provider", lambda org_data: provider
        )
        monkeypatch.setattr("cloudctl.commands.exec.load_context", lambda: {})

        captured_env = {}
        monkeypatch.setattr(
            "cloudctl.commands.exec.subprocess.run",
            lambda cmd, env=None: (
                captured_env.update(env or {}) or MagicMock(returncode=0)
            ),
        )

        rc = ExecCommand().execute(self._args())
        assert rc == 0
        write_spy.assert_not_called()
        assert list((mock_home / ".aws" / "sso" / "cache").glob("*.json")) == []
        assert captured_env.get("AWS_ACCESS_KEY_ID") == "AKIA-R"

    def test_run_no_cache_gcp_is_noop_and_proceeds(
        self, monkeypatch, mock_home, capsys
    ):
        """For GCP, --no-cache is a documented no-op: it prints a note and
        proceeds normally (no error)."""
        from cloudctl.commands.exec import ExecCommand

        gcp_org = {"name": "gcp-org", "provider": "gcp", "project": "proj-1"}

        fake_provider = MagicMock()
        fake_provider.az_uses_injected_identity.return_value = False
        fake_provider.get_credentials.return_value = {"CLOUDSDK_CORE_PROJECT": "proj-1"}

        monkeypatch.setattr("cloudctl.commands.exec.get_org", lambda name: gcp_org)
        monkeypatch.setattr(
            "cloudctl.providers.get_provider", lambda org_data: fake_provider
        )
        monkeypatch.setattr("cloudctl.commands.exec.load_context", lambda: {})

        captured_env = {}
        monkeypatch.setattr(
            "cloudctl.commands.exec.subprocess.run",
            lambda cmd, env=None: (
                captured_env.update(env or {}) or MagicMock(returncode=0)
            ),
        )

        args = Namespace(
            exec_org="gcp-org",
            exec_account="proj-1",
            exec_role=None,
            exec_region="us-central1",
            json_errors=False,
            no_cache=True,
            cmd=["gcloud", "config", "list"],
        )
        rc = ExecCommand().execute(args)
        assert rc == 0
        err = capsys.readouterr().err
        assert "no-op for gcp" in err
        # get_credentials was called with token=None (no in-memory token).
        _, kwargs = fake_provider.get_credentials.call_args
        assert kwargs.get("token") is None
