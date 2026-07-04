# file: tests/test_providers.py
"""Unit tests for the Azure and GCP cloud providers."""

import json

import pytest

from cloudctl.providers import get_provider
from cloudctl.providers.azure import AzureProvider
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

    def test_list_accounts_cli_error(self, provider, org, monkeypatch):
        monkeypatch.setattr(provider, "_az", lambda args: _az_result(1))
        assert provider.list_accounts(org, token=None) == []

    def test_list_accounts_corrupt_json(self, provider, org, monkeypatch):
        monkeypatch.setattr(provider, "_az", lambda args: _az_result(0, "bad"))
        assert provider.list_accounts(org, token=None) == []

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
        monkeypatch.setattr(
            provider, "_az", lambda args: _az_result(0, token_payload)
        )
        creds = provider.get_credentials(org, "sub-1", "Contributor", "eastus")

        assert creds["AZURE_SUBSCRIPTION_ID"] == "sub-1"
        assert creds["ARM_SUBSCRIPTION_ID"] == "sub-1"
        assert creds["AZURE_TENANT_ID"] == "tenant-123"
        assert creds["ARM_TENANT_ID"] == "tenant-123"
        assert creds["ARM_ACCESS_TOKEN"] == "tok-abc"

    def test_get_credentials_malformed_token_exits(self, provider, org, monkeypatch):
        # No global `az account set` is performed anymore; a token response
        # missing accessToken must still exit cleanly.
        monkeypatch.setattr(provider, "_az", lambda args: _az_result(0, "{}"))
        with pytest.raises(SystemExit):
            provider.get_credentials(org, "sub-1", "Contributor", "eastus")

    def test_get_credentials_token_fails_exits(self, provider, org, monkeypatch):
        # The only `_az` invocation is the read-only token fetch; if it fails
        # get_credentials exits.
        monkeypatch.setattr(provider, "_az", lambda args: _az_result(1))
        with pytest.raises(SystemExit):
            provider.get_credentials(org, "sub-1", "Contributor", "eastus")

    # --- get_unsets / get_exports -------------------------------------------

    def test_get_unsets_covers_all_env_vars(self, provider):
        unsets = provider.get_unsets()
        for var in AzureProvider._ENV_VARS:
            assert f"unset {var}" in unsets

    def test_get_exports_format(self, provider, org, monkeypatch):
        token_payload = json.dumps({"accessToken": "tok-xyz", "tenant": "t-1"})
        monkeypatch.setattr(
            provider, "_az", lambda args: _az_result(0, token_payload)
        )
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

    def test_list_accounts_cli_error(self, provider, org, monkeypatch):
        monkeypatch.setattr(provider, "_gcloud", lambda args: _gc_result(1))
        assert provider.list_accounts(org, token=None) == []

    def test_list_accounts_corrupt_json(self, provider, org, monkeypatch):
        monkeypatch.setattr(provider, "_gcloud", lambda args: _gc_result(0, "bad"))
        assert provider.list_accounts(org, token=None) == []

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

    def test_get_credentials_token_fetch_fails_exits(self, provider, org, monkeypatch):
        # The only `_gcloud` call is the read-only token fetch (no global
        # `gcloud config set project` anymore); if it fails, exit.
        monkeypatch.setattr(provider, "_gcloud", lambda args: _gc_result(1))
        with pytest.raises(SystemExit):
            provider.get_credentials(org, "my-project", "roles/viewer", "us-central1")

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
