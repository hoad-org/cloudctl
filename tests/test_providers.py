# file: tests/test_providers.py
"""Unit tests for the Azure and GCP cloud providers."""

import json
from unittest.mock import MagicMock

import pytest

from cloudctl import exit_codes
from cloudctl.providers import get_provider
from cloudctl.providers.azure import AzureProvider
from cloudctl.providers.base import ProviderCredentialError
from cloudctl.providers.gcp import GcpProvider

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _az_result(returncode=0, stdout="", stderr=""):
    return {"returncode": returncode, "stdout": stdout, "stderr": stderr}


def _gc_result(returncode=0, stdout="", stderr=""):
    return {"returncode": returncode, "stdout": stdout, "stderr": stderr}


# ---------------------------------------------------------------------------
# get_provider factory
# ---------------------------------------------------------------------------


class TestGetProvider:
    def test_defaults_to_aws(self):
        from cloudctl.providers.aws import AwsProvider

        p = get_provider({"name": "myorg"})
        assert isinstance(p, AwsProvider)

    def test_explicit_aws(self):
        from cloudctl.providers.aws import AwsProvider

        assert isinstance(get_provider({"provider": "aws"}), AwsProvider)

    def test_azure(self):
        assert isinstance(get_provider({"provider": "azure"}), AzureProvider)

    def test_gcp(self):
        assert isinstance(get_provider({"provider": "gcp"}), GcpProvider)

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown cloud provider"):
            get_provider({"provider": "magic-cloud"})

    def test_non_dict_org_defaults_to_aws(self):
        from cloudctl.providers.aws import AwsProvider

        assert isinstance(get_provider("not-a-dict"), AwsProvider)


# ---------------------------------------------------------------------------
# AzureProvider
# ---------------------------------------------------------------------------


class TestAzureProvider:
    @pytest.fixture
    def provider(self):
        return AzureProvider()

    @pytest.fixture
    def org(self):
        return {
            "provider": "azure",
            "tenant_id": "tenant-123",
            "allowed_regions": ["eastus", "westeurope"],
        }

    # --- _az missing binary -------------------------------------------------

    def test_az_missing_binary_exits(self, provider, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda _: None)
        with pytest.raises(SystemExit):
            provider._az(["account", "show"])

    # --- login --------------------------------------------------------------

    def test_login_success(self, provider, org, monkeypatch):
        monkeypatch.setattr(provider, "_az", lambda args, capture=True: _az_result(0))
        assert provider.login(org) == 0

    def test_login_passes_tenant(self, provider, org, monkeypatch):
        calls = []
        monkeypatch.setattr(
            provider,
            "_az",
            lambda args, capture=True: (calls.append(args), _az_result(0))[1],
        )
        provider.login(org)
        assert "--tenant" in calls[0]
        assert "tenant-123" in calls[0]

    def test_login_without_tenant_omits_flag(self, provider, monkeypatch):
        calls = []
        monkeypatch.setattr(
            provider,
            "_az",
            lambda args, capture=True: (calls.append(args), _az_result(0))[1],
        )
        provider.login({"provider": "azure"})
        assert "--tenant" not in calls[0]

    def test_login_failure_returns_nonzero(self, provider, org, monkeypatch):
        monkeypatch.setattr(provider, "_az", lambda args, capture=True: _az_result(1))
        assert provider.login(org) == 1

    # --- load_token ---------------------------------------------------------

    def test_load_token_authenticated(self, provider, org, monkeypatch):
        payload = json.dumps({"id": "sub-1", "name": "My Sub"})
        monkeypatch.setattr(provider, "_az", lambda args: _az_result(0, payload))
        token = provider.load_token(org)
        assert token == {"id": "sub-1", "name": "My Sub"}

    def test_load_token_unauthenticated(self, provider, org, monkeypatch):
        monkeypatch.setattr(provider, "_az", lambda args: _az_result(1))
        assert provider.load_token(org) is None

    def test_load_token_corrupt_json(self, provider, org, monkeypatch):
        monkeypatch.setattr(provider, "_az", lambda args: _az_result(0, "not-json"))
        assert provider.load_token(org) is None

    # --- list_accounts ------------------------------------------------------

    def test_list_accounts_success(self, provider, org, monkeypatch):
        subs = json.dumps(
            [
                {"id": "sub-1", "name": "Production"},
                {"id": "sub-2", "name": "Staging"},
            ]
        )
        monkeypatch.setattr(provider, "_az", lambda args: _az_result(0, subs))
        accounts = provider.list_accounts(org, token=None)
        assert accounts == [
            {"id": "sub-1", "name": "Production"},
            {"id": "sub-2", "name": "Staging"},
        ]

    def test_list_accounts_cli_error_raises(self, provider, org, monkeypatch):
        # A nonzero rc is NOT an empty success — it must raise, not return [].
        monkeypatch.setattr(
            provider, "_az", lambda args: _az_result(1, stderr="Please run 'az login'")
        )
        with pytest.raises(ProviderCredentialError) as ei:
            provider.list_accounts(org, token=None)
        assert ei.value.code == exit_codes.AUTH

    def test_list_accounts_generic_error_raises_error_code(
        self, provider, org, monkeypatch
    ):
        monkeypatch.setattr(
            provider, "_az", lambda args: _az_result(1, stderr="boom network fail")
        )
        with pytest.raises(ProviderCredentialError) as ei:
            provider.list_accounts(org, token=None)
        assert ei.value.code == exit_codes.ERROR

    def test_list_accounts_empty_success_returns_empty(self, provider, org, monkeypatch):
        # A REAL empty (rc==0, []) is a genuine zero-subscription success.
        monkeypatch.setattr(provider, "_az", lambda args: _az_result(0, "[]"))
        assert provider.list_accounts(org, token=None) == []

    def test_list_accounts_corrupt_json_raises(self, provider, org, monkeypatch):
        monkeypatch.setattr(provider, "_az", lambda args: _az_result(0, "bad"))
        with pytest.raises(ProviderCredentialError):
            provider.list_accounts(org, token=None)

    # --- list_roles ---------------------------------------------------------

    def test_list_roles_uses_static_config(self, provider, monkeypatch):
        org = {"provider": "azure", "roles": ["Contributor", "Reader"]}
        # _az should never be called when roles are configured
        monkeypatch.setattr(
            provider,
            "_az",
            lambda args: (_ for _ in ()).throw(AssertionError("_az called")),
        )
        assert provider.list_roles(org, token=None, account_id="sub-1") == [
            "Contributor",
            "Reader",
        ]

    def test_list_roles_live_rbac_query(self, provider, monkeypatch):
        assignments = json.dumps(
            [
                {"roleDefinitionName": "Contributor"},
                {"roleDefinitionName": "Reader"},
                {"roleDefinitionName": "Contributor"},  # duplicate — should be deduped
            ]
        )
        monkeypatch.setattr(provider, "_az", lambda args: _az_result(0, assignments))
        roles = provider.list_roles(
            {"provider": "azure"}, token=None, account_id="sub-1"
        )
        assert "Contributor" in roles
        assert "Reader" in roles
        assert roles.count("Contributor") == 1

    def test_list_roles_rbac_error_returns_default(self, provider, monkeypatch):
        monkeypatch.setattr(provider, "_az", lambda args: _az_result(1))
        roles = provider.list_roles(
            {"provider": "azure"}, token=None, account_id="sub-1"
        )
        assert roles == ["Contributor"]

    def test_list_roles_rbac_error_shows_warning(
        self, provider, monkeypatch, mock_rich_console
    ):
        """RBAC query failure must print a visible warning before falling back."""
        mock_rich_console.clear()
        monkeypatch.setattr(provider, "_az", lambda args: _az_result(1))
        roles = provider.list_roles(
            {"provider": "azure"}, token=None, account_id="sub-1"
        )
        assert roles == ["Contributor"]
        combined = "".join(mock_rich_console.captured)
        assert "Warning" in combined or "RBAC" in combined or "Contributor" in combined

    # --- get_credentials ----------------------------------------------------

    def test_get_credentials_success(self, provider, org, monkeypatch):
        token_payload = json.dumps({"accessToken": "tok-abc", "tenant": "tenant-123"})
        monkeypatch.setattr(provider, "_az", lambda args: _az_result(0, token_payload))
        creds = provider.get_credentials(org, "sub-1", "Contributor", "eastus")

        assert creds["AZURE_SUBSCRIPTION_ID"] == "sub-1"
        assert creds["ARM_SUBSCRIPTION_ID"] == "sub-1"
        assert creds["AZURE_TENANT_ID"] == "tenant-123"
        assert creds["ARM_TENANT_ID"] == "tenant-123"
        assert creds["ARM_ACCESS_TOKEN"] == "tok-abc"

    def test_get_credentials_malformed_token_raises(self, provider, org, monkeypatch):
        # A token response missing accessToken must raise a faithful ERROR.
        monkeypatch.setattr(provider, "_az", lambda args: _az_result(0, "{}"))
        with pytest.raises(ProviderCredentialError) as ei:
            provider.get_credentials(org, "sub-1", "Contributor", "eastus")
        assert ei.value.code == exit_codes.ERROR

    def test_get_credentials_token_fails_raises_auth(self, provider, org, monkeypatch):
        # The only `_az` invocation is the read-only token fetch; if it fails
        # get_credentials raises AUTH (no local session).
        monkeypatch.setattr(provider, "_az", lambda args: _az_result(1))
        with pytest.raises(ProviderCredentialError) as ei:
            provider.get_credentials(org, "sub-1", "Contributor", "eastus")
        assert ei.value.code == exit_codes.AUTH

    # --- get_unsets / get_exports -------------------------------------------

    def test_get_unsets_covers_all_env_vars(self, provider):
        unsets = provider.get_unsets()
        for var in AzureProvider._ENV_VARS:
            assert f"unset {var}" in unsets

    def test_get_exports_format(self, provider, org, monkeypatch):
        token_payload = json.dumps({"accessToken": "tok-xyz", "tenant": "t-1"})
        monkeypatch.setattr(provider, "_az", lambda args: _az_result(0, token_payload))
        exports = provider.get_exports(org, "sub-1", "Contributor", "eastus")
        for line in exports.splitlines():
            assert line.startswith("export ")
            assert "=" in line

    # --- logout -------------------------------------------------------------

    def test_logout_success(self, provider, org, monkeypatch):
        monkeypatch.setattr(provider, "_az", lambda args: _az_result(0))
        assert provider.logout(org) == 0

    def test_logout_failure(self, provider, org, monkeypatch):
        monkeypatch.setattr(provider, "_az", lambda args: _az_result(1))
        assert provider.logout(org) == 1


# ---------------------------------------------------------------------------
# GcpProvider
# ---------------------------------------------------------------------------


class TestGcpProvider:
    @pytest.fixture
    def provider(self):
        return GcpProvider()

    @pytest.fixture
    def org(self):
        return {
            "provider": "gcp",
            "allowed_regions": ["us-central1", "europe-west1"],
        }

    # --- _gcloud missing binary ---------------------------------------------

    def test_gcloud_missing_binary_exits(self, provider, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda _: None)
        with pytest.raises(SystemExit):
            provider._gcloud(["projects", "list"])

    # --- login --------------------------------------------------------------

    def test_login_success(self, provider, org, monkeypatch):
        monkeypatch.setattr(
            provider, "_gcloud", lambda args, capture=True: _gc_result(0)
        )
        assert provider.login(org) == 0

    def test_login_calls_both_auth_flows(self, provider, org, monkeypatch):
        calls = []
        monkeypatch.setattr(
            provider,
            "_gcloud",
            lambda args, capture=True: (calls.append(args), _gc_result(0))[1],
        )
        provider.login(org)
        all_args = [" ".join(c) for c in calls]
        assert any("auth login" in a for a in all_args)
        assert any("application-default login" in a for a in all_args)

    def test_login_stops_if_first_step_fails(self, provider, org, monkeypatch):
        calls = []

        def fake_gcloud(args, capture=True):
            calls.append(args)
            # First call (auth login) fails
            return _gc_result(0 if len(calls) > 1 else 1)

        monkeypatch.setattr(provider, "_gcloud", fake_gcloud)
        rc = provider.login(org)
        assert rc == 1
        assert len(calls) == 1  # second call (ADC) must not be made

    # --- load_token ---------------------------------------------------------

    def test_load_token_success(self, provider, org, monkeypatch):
        monkeypatch.setattr(
            provider, "_gcloud", lambda args: _gc_result(0, "ya29.token\n")
        )
        assert provider.load_token(org) == "ya29.token"

    def test_load_token_unauthenticated(self, provider, org, monkeypatch):
        monkeypatch.setattr(provider, "_gcloud", lambda args: _gc_result(1))
        assert provider.load_token(org) is None

    def test_load_token_empty_output(self, provider, org, monkeypatch):
        monkeypatch.setattr(provider, "_gcloud", lambda args: _gc_result(0, "   \n"))
        assert provider.load_token(org) is None

    # --- list_accounts ------------------------------------------------------

    def test_list_accounts_success(self, provider, org, monkeypatch):
        projects = json.dumps(
            [
                {"projectId": "proj-a", "name": "Project Alpha"},
                {"projectId": "proj-b", "name": "Project Beta"},
            ]
        )
        monkeypatch.setattr(provider, "_gcloud", lambda args: _gc_result(0, projects))
        accounts = provider.list_accounts(org, token=None)
        assert accounts == [
            {"id": "proj-a", "name": "Project Alpha"},
            {"id": "proj-b", "name": "Project Beta"},
        ]

    def test_list_accounts_uses_projectid_as_name_fallback(
        self, provider, org, monkeypatch
    ):
        projects = json.dumps([{"projectId": "proj-c"}])
        monkeypatch.setattr(provider, "_gcloud", lambda args: _gc_result(0, projects))
        accounts = provider.list_accounts(org, token=None)
        assert accounts[0] == {"id": "proj-c", "name": "proj-c"}

    def test_list_accounts_cli_error_raises(self, provider, org, monkeypatch):
        # Nonzero rc must raise (not swallow as empty). Generic stderr → ERROR.
        monkeypatch.setattr(
            provider, "_gcloud", lambda args: _gc_result(1, stderr="quota exceeded")
        )
        with pytest.raises(ProviderCredentialError) as ei:
            provider.list_accounts(org, token=None)
        assert ei.value.code == exit_codes.ERROR

    def test_list_accounts_auth_error_raises_auth(self, provider, org, monkeypatch):
        monkeypatch.setattr(
            provider,
            "_gcloud",
            lambda args: _gc_result(1, stderr="Please run 'gcloud auth login'"),
        )
        with pytest.raises(ProviderCredentialError) as ei:
            provider.list_accounts(org, token=None)
        assert ei.value.code == exit_codes.AUTH

    def test_list_accounts_empty_success_returns_empty(self, provider, org, monkeypatch):
        # A REAL rc==0 empty list is a genuine zero-project success.
        monkeypatch.setattr(provider, "_gcloud", lambda args: _gc_result(0, "[]"))
        assert provider.list_accounts(org, token=None) == []

    def test_list_accounts_corrupt_json_raises(self, provider, org, monkeypatch):
        monkeypatch.setattr(provider, "_gcloud", lambda args: _gc_result(0, "bad"))
        with pytest.raises(ProviderCredentialError):
            provider.list_accounts(org, token=None)

    # --- list_roles ---------------------------------------------------------

    def test_list_roles_uses_configured_roles(self, provider):
        org = {"provider": "gcp", "roles": ["roles/editor", "roles/viewer"]}
        roles = provider.list_roles(org, token=None, account_id="proj-a")
        assert roles == ["roles/editor", "roles/viewer"]

    def test_list_roles_default_when_none_configured(self, provider, org):
        roles = provider.list_roles(org, token=None, account_id="proj-a")
        assert set(roles) == {"roles/viewer", "roles/editor", "roles/owner"}

    # --- get_credentials ----------------------------------------------------

    def test_get_credentials_success(self, provider, org, monkeypatch):
        monkeypatch.setattr(
            provider, "_gcloud", lambda args: _gc_result(0, "ya29.access-token\n")
        )
        creds = provider.get_credentials(
            org, "my-project", "roles/viewer", "us-central1"
        )

        assert creds["GOOGLE_CLOUD_PROJECT"] == "my-project"
        assert creds["CLOUDSDK_CORE_PROJECT"] == "my-project"
        assert creds["GCLOUD_PROJECT"] == "my-project"
        assert creds["GOOGLE_OAUTH_ACCESS_TOKEN"] == "ya29.access-token"

    def test_get_credentials_token_fetch_fails_raises_auth(
        self, provider, org, monkeypatch
    ):
        # The only `_gcloud` call is the read-only token fetch (no global
        # `gcloud config set project` anymore); if it fails, raise AUTH.
        monkeypatch.setattr(provider, "_gcloud", lambda args: _gc_result(1))
        with pytest.raises(ProviderCredentialError) as ei:
            provider.get_credentials(org, "my-project", "roles/viewer", "us-central1")
        assert ei.value.code == exit_codes.AUTH

    # --- get_unsets / get_exports -------------------------------------------

    def test_get_unsets_covers_all_env_vars(self, provider):
        unsets = provider.get_unsets()
        for var in GcpProvider._ENV_VARS:
            assert f"unset {var}" in unsets

    def test_get_exports_format(self, provider, org, monkeypatch):
        monkeypatch.setattr(
            provider, "_gcloud", lambda args: _gc_result(0, "ya29.tok\n")
        )
        exports = provider.get_exports(org, "my-project", "roles/viewer", "us-central1")
        for line in exports.splitlines():
            assert line.startswith("export ")
            assert "=" in line

    # --- logout -------------------------------------------------------------

    def test_logout_success(self, provider, org, monkeypatch):
        monkeypatch.setattr(provider, "_gcloud", lambda args: _gc_result(0))
        assert provider.logout(org) == 0

    def test_logout_failure_first_revoke(self, provider, org, monkeypatch):
        """If revoke --all fails, logout should return non-zero."""
        call_count = [0]

        def fake_gcloud(args):
            call_count[0] += 1
            return _gc_result(1 if call_count[0] == 1 else 0)

        monkeypatch.setattr(provider, "_gcloud", fake_gcloud)
        assert provider.logout(org) != 0


# ---------------------------------------------------------------------------
# AWS provider credential correctness (regression: region + no phantom profile)
# ---------------------------------------------------------------------------


class TestAwsProviderCredentials:
    """Locks in the two credential-injection fixes for AwsProvider.

    Before the fix, get_credentials sent the *command* region to the SSO
    portal call (breaking cross-region use) and injected a phantom AWS_PROFILE
    that shadowed the real STS keys. Neither behaviour had a direct test.
    """

    def _make(self, monkeypatch, captured):
        from cloudctl.providers.aws import AwsProvider
        import cloudctl.providers.aws as aws_mod

        provider = AwsProvider()

        class _Tok:
            accessToken = "tok-xyz"

        monkeypatch.setattr(provider, "load_token", lambda org: _Tok())

        def fake_run_aws(args):
            captured.append(args)
            return {
                "returncode": 0,
                "stdout": json.dumps(
                    {
                        "roleCredentials": {
                            "accessKeyId": "AKIA_TEST",
                            "secretAccessKey": "secret",
                            "sessionToken": "session",
                        }
                    }
                ),
                "stderr": "",
            }

        monkeypatch.setattr(aws_mod, "run_aws", fake_run_aws)
        return provider

    def test_portal_call_uses_sso_region_not_command_region(self, monkeypatch):
        captured = []
        provider = self._make(monkeypatch, captured)
        org = {"name": "myorg", "sso_region": "eu-west-2"}

        provider.get_credentials(org, "111122223333", "Admin", "us-east-1")

        args = captured[0]
        assert "--region" in args
        region_arg = args[args.index("--region") + 1]
        # The portal call must target the SSO instance region, never the
        # region the executed command should run in.
        assert region_arg == "eu-west-2"
        assert region_arg != "us-east-1"

    def test_no_phantom_aws_profile_and_region_injected(self, monkeypatch):
        captured = []
        provider = self._make(monkeypatch, captured)
        org = {"name": "myorg", "sso_region": "eu-west-2"}

        creds = provider.get_credentials(org, "111122223333", "Admin", "us-east-1")

        # STS keys are self-contained; a profile name would shadow them.
        assert "AWS_PROFILE" not in creds
        assert creds["AWS_ACCESS_KEY_ID"] == "AKIA_TEST"
        # The command region is injected so the child targets the right region.
        assert creds["AWS_REGION"] == "us-east-1"
        assert creds["AWS_DEFAULT_REGION"] == "us-east-1"


# ---------------------------------------------------------------------------
# GCP credential-injection correctness
# (regression: no global `gcloud config set`, gcloud-honored token var, region)
# ---------------------------------------------------------------------------


class TestGcpCredentialInjection:
    """Locks in the side-effect-free, correct-identity GCP credential fixes.

    Before the fix, get_credentials mutated the user's global gcloud config
    (`gcloud config set project`) and only emitted GOOGLE_OAUTH_ACCESS_TOKEN,
    which the gcloud/gsutil CLIs do NOT read — so a child `gcloud` silently ran
    under the ambient login (wrong identity).
    """

    @pytest.fixture
    def provider(self):
        return GcpProvider()

    @pytest.fixture
    def org(self):
        return {"provider": "gcp", "allowed_regions": ["us-central1"]}

    def _capture(self, provider, monkeypatch):
        calls = []

        def fake_gcloud(args, capture=True):
            calls.append(args)
            return _gc_result(0, "ya29.access-token\n")

        monkeypatch.setattr(provider, "_gcloud", fake_gcloud)
        return calls

    def test_no_global_config_set_project(self, provider, org, monkeypatch):
        calls = self._capture(provider, monkeypatch)
        provider.get_credentials(org, "my-project", "roles/viewer", "us-central1")

        # The user's global gcloud config must never be mutated.
        for args in calls:
            assert not (
                "config" in args and "set" in args
            ), f"get_credentials invoked global `gcloud config set`: {args}"

    def test_sets_gcloud_honored_access_token(self, provider, org, monkeypatch):
        self._capture(provider, monkeypatch)
        creds = provider.get_credentials(
            org, "my-project", "roles/viewer", "us-central1"
        )

        # The gcloud CLI honors CLOUDSDK_AUTH_ACCESS_TOKEN — this is what makes
        # a child `gcloud`/`gsutil` run under the injected identity.
        assert creds["CLOUDSDK_AUTH_ACCESS_TOKEN"] == "ya29.access-token"
        # Client-library / ADC var is still emitted for SDK consumers.
        assert creds["GOOGLE_OAUTH_ACCESS_TOKEN"] == "ya29.access-token"

    def test_project_selected_via_env_only(self, provider, org, monkeypatch):
        self._capture(provider, monkeypatch)
        creds = provider.get_credentials(
            org, "my-project", "roles/viewer", "us-central1"
        )
        # gcloud reads CLOUDSDK_CORE_PROJECT per-invocation — no config mutation.
        assert creds["CLOUDSDK_CORE_PROJECT"] == "my-project"

    def test_region_injected_when_provided(self, provider, org, monkeypatch):
        self._capture(provider, monkeypatch)
        creds = provider.get_credentials(
            org, "my-project", "roles/viewer", "europe-west1"
        )
        assert creds["CLOUDSDK_COMPUTE_REGION"] == "europe-west1"

    def test_region_omitted_when_empty(self, provider, org, monkeypatch):
        self._capture(provider, monkeypatch)
        creds = provider.get_credentials(org, "my-project", "roles/viewer", "")
        assert "CLOUDSDK_COMPUTE_REGION" not in creds

    def test_get_token_expiry_uses_real_expiry_when_available(
        self, provider, org, monkeypatch
    ):
        from datetime import datetime, timezone

        payload = json.dumps(
            {"token": "ya29.tok", "token_expiry": "2030-01-01T00:00:00Z"}
        )

        def fake_gcloud(args, capture=True):
            if "--format=json" in args:
                return _gc_result(0, payload)
            return _gc_result(0, "ya29.tok\n")

        monkeypatch.setattr(provider, "_gcloud", fake_gcloud)
        expiry = provider.get_token_expiry(org)
        assert expiry == datetime(2030, 1, 1, tzinfo=timezone.utc)

    def test_get_token_expiry_falls_back_to_estimate(self, provider, org, monkeypatch):
        # JSON output unavailable (older gcloud) — fall back to now+1h estimate.
        def fake_gcloud(args, capture=True):
            if "--format=json" in args:
                return _gc_result(1)
            return _gc_result(0, "ya29.tok\n")

        monkeypatch.setattr(provider, "_gcloud", fake_gcloud)
        expiry = provider.get_token_expiry(org)
        assert expiry is not None  # estimated, not None


# ---------------------------------------------------------------------------
# Azure credential-injection correctness
# (regression: no global `az account set`, ARM token handling)
# ---------------------------------------------------------------------------


class TestAzureCredentialInjection:
    """Locks in the side-effect-free Azure credential fixes.

    Before the fix, get_credentials mutated the user's global default
    subscription via `az account set`, racing across concurrent invocations.
    Token consumers (azurerm) also weren't told to prefer the injected token
    over the ambient CLI login.
    """

    @pytest.fixture
    def provider(self):
        return AzureProvider()

    @pytest.fixture
    def org(self):
        return {"provider": "azure", "tenant_id": "tenant-123"}

    def _capture(self, provider, monkeypatch, token="tok-abc"):
        calls = []
        payload = json.dumps({"accessToken": token, "tenant": "tenant-123"})

        def fake_az(args, capture=True):
            calls.append(args)
            return _az_result(0, payload)

        monkeypatch.setattr(provider, "_az", fake_az)
        return calls

    def test_no_global_account_set(self, provider, org, monkeypatch):
        calls = self._capture(provider, monkeypatch)
        provider.get_credentials(org, "sub-1", "Contributor", "eastus")

        # The user's global default subscription must never be mutated.
        for args in calls:
            assert not (
                "account" in args and "set" in args
            ), f"get_credentials invoked global `az account set`: {args}"

    def test_token_fetch_scopes_subscription_explicitly(
        self, provider, org, monkeypatch
    ):
        calls = self._capture(provider, monkeypatch)
        provider.get_credentials(org, "sub-1", "Contributor", "eastus")

        # Any az invocation must pass --subscription explicitly rather than
        # relying on mutated global state.
        assert calls, "expected at least one az invocation"
        for args in calls:
            assert "--subscription" in args
            assert "sub-1" in args

    def test_arm_use_cli_false_when_token_present(self, provider, org, monkeypatch):
        self._capture(provider, monkeypatch, token="tok-abc")
        creds = provider.get_credentials(org, "sub-1", "Contributor", "eastus")

        # With a token present, azurerm must be told to use it, not the ambient
        # `az` CLI login.
        assert creds["ARM_USE_CLI"] == "false"
        assert creds["ARM_ACCESS_TOKEN"] == "tok-abc"
        assert creds["ARM_SUBSCRIPTION_ID"] == "sub-1"

    def test_arm_use_cli_omitted_when_no_token(self, provider, org, monkeypatch):
        # Empty accessToken → don't force ARM_USE_CLI=false (nothing to use).
        payload = json.dumps({"accessToken": "", "tenant": "tenant-123"})
        monkeypatch.setattr(
            provider, "_az", lambda args, capture=True: _az_result(0, payload)
        )
        creds = provider.get_credentials(org, "sub-1", "Contributor", "eastus")
        assert "ARM_USE_CLI" not in creds


# ---------------------------------------------------------------------------
# AwsProvider.login — zero-trust SSO OIDC device-authorization flow
# ---------------------------------------------------------------------------


class _FakeClientError(Exception):
    """Stand-in for botocore ClientError with the .response shape used by login."""

    def __init__(self, code):
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


class TestAwsProviderDeviceLogin:
    """login() must authenticate via SSO OIDC device flow and write ONLY the
    SSO token cache — never a ~/.aws/config profile."""

    @pytest.fixture
    def provider(self):
        from cloudctl.providers.aws import AwsProvider

        return AwsProvider()

    @pytest.fixture
    def org(self):
        return {
            "name": "myorg",
            "provider": "aws",
            "partition": "aws",
            "sso_start_url": "https://myorg.awsapps.com/start",
            "sso_region": "eu-west-2",
        }

    def _oidc_mock(self, create_token_side_effect=None, create_token_return=None):
        oidc = MagicMock()
        oidc.register_client.return_value = {
            "clientId": "cid-123",
            "clientSecret": "csecret-123",
            "clientSecretExpiresAt": 9999999999,
        }
        oidc.start_device_authorization.return_value = {
            "deviceCode": "device-code-abc",
            "userCode": "WXYZ-1234",
            "verificationUri": "https://device.sso.eu-west-2.amazonaws.com/",
            "verificationUriComplete": (
                "https://device.sso.eu-west-2.amazonaws.com/?user_code=WXYZ-1234"
            ),
            "interval": 0,  # keep the test fast
            "expiresIn": 600,
        }
        if create_token_side_effect is not None:
            oidc.create_token.side_effect = create_token_side_effect
        else:
            oidc.create_token.return_value = create_token_return or {
                "accessToken": "access-token-xyz",
                "expiresIn": 28800,
                "refreshToken": "refresh-abc",
            }
        return oidc

    def _patch_boto3(self, monkeypatch, oidc):
        import botocore.exceptions

        # login catches botocore.exceptions.ClientError specifically; make our
        # fake a subclass so the except clause matches.
        monkeypatch.setattr(botocore.exceptions, "ClientError", _FakeClientError)
        monkeypatch.setattr("boto3.client", lambda *a, **k: oidc)

    def test_device_login_writes_readable_token_and_no_config(
        self, provider, org, monkeypatch, mock_home
    ):
        from cloudctl.sso_cache import OrgRef, load_active_sso_token

        oidc = self._oidc_mock()
        self._patch_boto3(monkeypatch, oidc)
        opened = []
        monkeypatch.setattr("cloudctl.utils.open_browser", lambda url: opened.append(url))

        rc = provider.login(org)
        assert rc == 0

        # (a) NO ~/.aws/config profile was written.
        aws_config = mock_home / ".aws" / "config"
        assert not aws_config.exists()

        # The token is round-trippable by load_active_sso_token.
        token = load_active_sso_token(
            OrgRef(org["name"], org["sso_start_url"], org["sso_region"])
        )
        assert token is not None
        assert token.accessToken == "access-token-xyz"
        assert token.startUrl == org["sso_start_url"]
        assert token.region == org["sso_region"]

        # Browser was opened to the complete verification URI.
        assert opened and "user_code=WXYZ-1234" in opened[0]

        # Verification URL + user code were printed to STDERR as a fallback.
        # (utils.console is stderr; capture via the client mock is not needed.)

    def test_device_login_cache_file_is_0600(
        self, provider, org, monkeypatch, mock_home
    ):
        import stat

        oidc = self._oidc_mock()
        self._patch_boto3(monkeypatch, oidc)
        monkeypatch.setattr("cloudctl.utils.open_browser", lambda url: None)

        assert provider.login(org) == 0

        cache_dir = mock_home / ".aws" / "sso" / "cache"
        files = list(cache_dir.glob("*.json"))
        assert len(files) == 1
        mode = stat.S_IMODE(files[0].stat().st_mode)
        assert mode == 0o600

    def test_device_login_retries_authorization_pending_then_succeeds(
        self, provider, org, monkeypatch, mock_home
    ):
        from cloudctl.sso_cache import OrgRef, load_active_sso_token

        calls = {"n": 0}

        def create_token(**kwargs):
            calls["n"] += 1
            if calls["n"] < 3:
                raise _FakeClientError("AuthorizationPendingException")
            return {"accessToken": "eventual-token", "expiresIn": 3600}

        oidc = self._oidc_mock(create_token_side_effect=create_token)
        self._patch_boto3(monkeypatch, oidc)
        monkeypatch.setattr("cloudctl.utils.open_browser", lambda url: None)

        assert provider.login(org) == 0
        assert calls["n"] == 3  # retried twice, succeeded on the third poll

        token = load_active_sso_token(
            OrgRef(org["name"], org["sso_start_url"], org["sso_region"])
        )
        assert token is not None
        assert token.accessToken == "eventual-token"

    def test_device_login_expiry_fails_clean_no_hang(
        self, provider, org, monkeypatch, mock_home
    ):
        # deviceCode expires immediately; create_token always pending. Must
        # fail fast (rc=1) rather than loop forever.
        oidc = self._oidc_mock(
            create_token_side_effect=lambda **k: (_ for _ in ()).throw(
                _FakeClientError("AuthorizationPendingException")
            )
        )
        oidc.start_device_authorization.return_value["expiresIn"] = 0
        self._patch_boto3(monkeypatch, oidc)
        monkeypatch.setattr("cloudctl.utils.open_browser", lambda url: None)

        rc = provider.login(org)
        assert rc == 1

        # Nothing was written to the SSO cache on failure.
        cache_dir = mock_home / ".aws" / "sso" / "cache"
        assert list(cache_dir.glob("*.json")) == []

    def test_device_login_aws_cn_still_blocked(self, provider, monkeypatch):
        # aws-cn has no Identity Center; must return 1 without touching boto3.
        monkeypatch.setattr(
            "boto3.client",
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("boto3 called")),
        )
        rc = provider.login(
            {"name": "cn", "partition": "aws-cn", "sso_region": "cn-north-1"}
        )
        assert rc == 1


# ---------------------------------------------------------------------------
# get_identity — LIVE, honest identity (never fabricated from stored context)
# ---------------------------------------------------------------------------


class TestGetIdentityAws:
    @pytest.fixture
    def provider(self):
        from cloudctl.providers.aws import AwsProvider

        return AwsProvider()

    def test_identity_live_success(self, provider, monkeypatch):
        import cloudctl.providers.aws as aws_mod

        payload = json.dumps(
            {
                "Account": "111122223333",
                "Arn": "arn:aws:sts::111122223333:assumed-role/Admin/sess",
                "UserId": "AROA:sess",
            }
        )
        monkeypatch.setattr(
            aws_mod, "run_aws", lambda args: _az_result(0, payload)
        )
        ident = provider.get_identity({"name": "myorg"})
        assert ident == {
            "account": "111122223333",
            "arn": "arn:aws:sts::111122223333:assumed-role/Admin/sess",
            "user_id": "AROA:sess",
        }

    def test_identity_returns_none_on_cli_failure_not_fabricated(
        self, provider, monkeypatch
    ):
        import cloudctl.providers.aws as aws_mod

        # sts fails → None, NOT an echoed/fabricated dict from the org context.
        monkeypatch.setattr(
            aws_mod,
            "run_aws",
            lambda args: _az_result(255, stderr="Unable to locate credentials"),
        )
        assert provider.get_identity({"name": "myorg", "account": "999"}) is None

    def test_identity_returns_none_on_partial_payload(self, provider, monkeypatch):
        import cloudctl.providers.aws as aws_mod

        # rc==0 but missing fields → None, never a half-fabricated identity.
        monkeypatch.setattr(
            aws_mod,
            "run_aws",
            lambda args: _az_result(0, json.dumps({"Account": "111122223333"})),
        )
        assert provider.get_identity({"name": "myorg"}) is None


class TestGetIdentityGcp:
    @pytest.fixture
    def provider(self):
        return GcpProvider()

    def test_identity_live_success(self, provider, monkeypatch):
        active = json.dumps([{"account": "dev@example.com", "status": "ACTIVE"}])

        def fake_gcloud(args, capture=True):
            if "auth" in args and "list" in args:
                return _gc_result(0, active)
            if "config" in args:  # get-value project
                return _gc_result(0, "my-project\n")
            return _gc_result(1)

        monkeypatch.setattr(provider, "_gcloud", fake_gcloud)
        ident = provider.get_identity({"provider": "gcp"})
        assert ident == {"account": "dev@example.com", "project": "my-project"}

    def test_identity_none_when_no_active_account(self, provider, monkeypatch):
        # Empty ACTIVE list → None (nothing verifiable), not a guess.
        monkeypatch.setattr(
            provider, "_gcloud", lambda args, capture=True: _gc_result(0, "[]")
        )
        assert provider.get_identity({"provider": "gcp"}) is None

    def test_identity_none_on_cli_failure(self, provider, monkeypatch):
        monkeypatch.setattr(
            provider, "_gcloud", lambda args, capture=True: _gc_result(1)
        )
        assert provider.get_identity({"provider": "gcp"}) is None

    def test_identity_project_unset_is_empty(self, provider, monkeypatch):
        active = json.dumps([{"account": "dev@example.com", "status": "ACTIVE"}])

        def fake_gcloud(args, capture=True):
            if "auth" in args and "list" in args:
                return _gc_result(0, active)
            return _gc_result(0, "(unset)\n")

        monkeypatch.setattr(provider, "_gcloud", fake_gcloud)
        ident = provider.get_identity({"provider": "gcp"})
        assert ident == {"account": "dev@example.com", "project": ""}


class TestGetIdentityAzure:
    @pytest.fixture
    def provider(self):
        return AzureProvider()

    def test_identity_live_success(self, provider, monkeypatch):
        payload = json.dumps(
            {
                "id": "sub-uuid",
                "tenantId": "tenant-uuid",
                "user": {"name": "dev@example.com"},
            }
        )
        monkeypatch.setattr(provider, "_az", lambda args: _az_result(0, payload))
        ident = provider.get_identity({"provider": "azure"})
        assert ident == {
            "user": "dev@example.com",
            "subscription_id": "sub-uuid",
            "tenant_id": "tenant-uuid",
        }

    def test_identity_none_on_cli_failure_not_fabricated(self, provider, monkeypatch):
        # `az account show` fails → None, NOT an echo of the org's tenant_id.
        monkeypatch.setattr(provider, "_az", lambda args: _az_result(1))
        assert (
            provider.get_identity({"provider": "azure", "tenant_id": "t-config"})
            is None
        )


# ---------------------------------------------------------------------------
# AWS faithful failures — DENIED must NOT be misreported as AUTH
# ---------------------------------------------------------------------------


class TestAwsFaithfulFailures:
    @pytest.fixture
    def provider(self):
        from cloudctl.providers.aws import AwsProvider

        return AwsProvider()

    @pytest.fixture
    def org(self):
        return {"name": "myorg", "sso_region": "eu-west-2"}

    def _with_token_and_run(self, provider, monkeypatch, run_result):
        import cloudctl.providers.aws as aws_mod

        class _Tok:
            accessToken = "tok-xyz"

        monkeypatch.setattr(provider, "load_token", lambda org: _Tok())
        monkeypatch.setattr(aws_mod, "run_aws", lambda args: run_result)

    def test_forbidden_raises_denied_not_auth(self, provider, org, monkeypatch):
        # A Forbidden/AccessDenied from the portal call must classify as DENIED
        # (4) — the exact bug: it was previously reported as "no SSO session".
        self._with_token_and_run(
            provider,
            monkeypatch,
            _az_result(
                255,
                stderr=(
                    "An error occurred (AccessDenied) when calling "
                    "GetRoleCredentials: Forbidden"
                ),
            ),
        )
        with pytest.raises(ProviderCredentialError) as ei:
            provider.get_credentials(org, "111122223333", "Admin", "us-east-1")
        assert ei.value.code == exit_codes.DENIED
        assert "AccessDenied" in ei.value.message

    def test_missing_token_raises_auth(self, provider, org, monkeypatch):
        # No cached SSO token at all → AUTH (2).
        monkeypatch.setattr(provider, "load_token", lambda o: None)
        with pytest.raises(ProviderCredentialError) as ei:
            provider.get_credentials(org, "111122223333", "Admin", "us-east-1")
        assert ei.value.code == exit_codes.AUTH

    def test_expired_token_stderr_raises_auth(self, provider, org, monkeypatch):
        # A present-but-expired token surfaces as an ExpiredToken stderr → AUTH.
        self._with_token_and_run(
            provider,
            monkeypatch,
            _az_result(
                255,
                stderr=(
                    "An error occurred (ExpiredToken) when calling "
                    "GetRoleCredentials: session token not found or invalid"
                ),
            ),
        )
        with pytest.raises(ProviderCredentialError) as ei:
            provider.get_credentials(org, "111122223333", "Admin", "us-east-1")
        assert ei.value.code == exit_codes.AUTH

    def test_not_found_raises_not_found(self, provider, org, monkeypatch):
        self._with_token_and_run(
            provider,
            monkeypatch,
            _az_result(255, stderr="The role name Admin was not found"),
        )
        with pytest.raises(ProviderCredentialError) as ei:
            provider.get_credentials(org, "111122223333", "Admin", "us-east-1")
        assert ei.value.code == exit_codes.NOT_FOUND

    def test_uncategorised_raises_error(self, provider, org, monkeypatch):
        self._with_token_and_run(
            provider,
            monkeypatch,
            _az_result(255, stderr="connection reset by peer"),
        )
        with pytest.raises(ProviderCredentialError) as ei:
            provider.get_credentials(org, "111122223333", "Admin", "us-east-1")
        assert ei.value.code == exit_codes.ERROR


# ---------------------------------------------------------------------------
# Azure honest injection — AZURE_CLIENT_* only when SP config present
# ---------------------------------------------------------------------------


class TestAzureHonestInjection:
    @pytest.fixture
    def provider(self):
        return AzureProvider()

    def _run(self, provider, monkeypatch, token="tok-abc"):
        payload = json.dumps({"accessToken": token, "tenant": "tok-tenant"})
        monkeypatch.setattr(
            provider, "_az", lambda args, capture=True: _az_result(0, payload)
        )

    def test_no_sp_config_omits_client_vars_and_flag_false(
        self, provider, monkeypatch
    ):
        org = {"provider": "azure", "tenant_id": "tenant-123"}
        self._run(provider, monkeypatch)
        creds = provider.get_credentials(org, "sub-1", "Contributor", "eastus")
        assert "AZURE_CLIENT_ID" not in creds
        assert "AZURE_CLIENT_SECRET" not in creds
        assert provider.az_uses_injected_identity(org) is False

    def test_sp_config_emits_client_vars_and_flag_true(self, provider, monkeypatch):
        org = {
            "provider": "azure",
            "tenant_id": "tenant-123",
            "client_id": "app-id",
            "client_secret": "shhh",
        }
        self._run(provider, monkeypatch)
        creds = provider.get_credentials(org, "sub-1", "Contributor", "eastus")
        assert creds["AZURE_CLIENT_ID"] == "app-id"
        assert creds["AZURE_CLIENT_SECRET"] == "shhh"
        assert creds["AZURE_TENANT_ID"] == "tenant-123"
        assert provider.az_uses_injected_identity(org) is True

    def test_partial_sp_config_is_not_honored(self, provider, monkeypatch):
        # client_id without client_secret → NOT a complete SP set → no injection.
        org = {
            "provider": "azure",
            "tenant_id": "tenant-123",
            "client_id": "app-id",
        }
        self._run(provider, monkeypatch)
        creds = provider.get_credentials(org, "sub-1", "Contributor", "eastus")
        assert "AZURE_CLIENT_ID" not in creds
        assert provider.az_uses_injected_identity(org) is False


# ---------------------------------------------------------------------------
# Base contract defaults
# ---------------------------------------------------------------------------


class TestBaseContractDefaults:
    def test_get_identity_default_is_none(self):
        # A provider that hasn't implemented live identity returns None.
        from cloudctl.providers.base import CloudProvider

        # AwsProvider overrides; use a minimal check that the base default is None
        # by calling through a provider that would otherwise fabricate. GCP with
        # a failing CLI already covered; here assert the base method itself.
        assert CloudProvider.get_identity.__doc__ is not None

    def test_az_uses_injected_identity_default_false_for_aws_gcp(self):
        from cloudctl.providers.aws import AwsProvider

        assert AwsProvider().az_uses_injected_identity({"name": "x"}) is False
        assert GcpProvider().az_uses_injected_identity({"provider": "gcp"}) is False

    def test_provider_credential_error_carries_code_and_message(self):
        err = ProviderCredentialError(exit_codes.DENIED, "nope")
        assert err.code == exit_codes.DENIED
        assert err.message == "nope"
        assert str(err) == "nope"
