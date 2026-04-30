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
        monkeypatch.setattr(provider, "_az", lambda args: _az_result(0))
        assert provider.login(org) == 0

    def test_login_passes_tenant(self, provider, org, monkeypatch):
        calls = []
        monkeypatch.setattr(
            provider, "_az", lambda args: (calls.append(args), _az_result(0))[1]
        )
        provider.login(org)
        assert "--tenant" in calls[0]
        assert "tenant-123" in calls[0]

    def test_login_without_tenant_omits_flag(self, provider, monkeypatch):
        calls = []
        monkeypatch.setattr(
            provider, "_az", lambda args: (calls.append(args), _az_result(0))[1]
        )
        provider.login({"provider": "azure"})
        assert "--tenant" not in calls[0]

    def test_login_failure_returns_nonzero(self, provider, org, monkeypatch):
        monkeypatch.setattr(provider, "_az", lambda args: _az_result(1))
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

        def fake_az(args):
            if "set" in args:
                return _az_result(0)
            return _az_result(0, token_payload)

        monkeypatch.setattr(provider, "_az", fake_az)
        creds = provider.get_credentials(org, "sub-1", "Contributor", "eastus")

        assert creds["AZURE_SUBSCRIPTION_ID"] == "sub-1"
        assert creds["ARM_SUBSCRIPTION_ID"] == "sub-1"
        assert creds["AZURE_TENANT_ID"] == "tenant-123"
        assert creds["ARM_TENANT_ID"] == "tenant-123"
        assert creds["ARM_ACCESS_TOKEN"] == "tok-abc"

    def test_get_credentials_set_fails_exits(self, provider, org, monkeypatch):
        def fake_az(args):
            if "set" in args:
                return _az_result(1)
            return _az_result(0, "{}")

        monkeypatch.setattr(provider, "_az", fake_az)
        with pytest.raises(SystemExit):
            provider.get_credentials(org, "sub-1", "Contributor", "eastus")

    def test_get_credentials_token_fails_exits(self, provider, org, monkeypatch):
        def fake_az(args):
            if "set" in args:
                return _az_result(0)
            return _az_result(1)

        monkeypatch.setattr(provider, "_az", fake_az)
        with pytest.raises(SystemExit):
            provider.get_credentials(org, "sub-1", "Contributor", "eastus")

    # --- get_unsets / get_exports -------------------------------------------

    def test_get_unsets_covers_all_env_vars(self, provider):
        unsets = provider.get_unsets()
        for var in AzureProvider._ENV_VARS:
            assert f"unset {var}" in unsets

    def test_get_exports_format(self, provider, org, monkeypatch):
        token_payload = json.dumps({"accessToken": "tok-xyz", "tenant": "t-1"})

        def fake_az(args):
            if "set" in args:
                return _az_result(0)
            return _az_result(0, token_payload)

        monkeypatch.setattr(provider, "_az", fake_az)
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
        monkeypatch.setattr(provider, "_gcloud", lambda args: _gc_result(0))
        assert provider.login(org) == 0

    def test_login_calls_both_auth_flows(self, provider, org, monkeypatch):
        calls = []
        monkeypatch.setattr(
            provider,
            "_gcloud",
            lambda args: (calls.append(args), _gc_result(0))[1],
        )
        provider.login(org)
        all_args = [" ".join(c) for c in calls]
        assert any("auth login" in a for a in all_args)
        assert any("application-default login" in a for a in all_args)

    def test_login_stops_if_first_step_fails(self, provider, org, monkeypatch):
        calls = []

        def fake_gcloud(args):
            calls.append(args)
            # auth list succeeds (empty result), but auth login fails
            if "login" in args:
                return _gc_result(1)  # auth login fails
            return _gc_result(0)  # auth list succeeds

        monkeypatch.setattr(provider, "_gcloud", fake_gcloud)
        rc = provider.login(org)
        assert rc == 1
        # Should have called: auth list, then auth login (and failed)
        # Should NOT have called application-default login
        assert len(calls) == 2
        assert calls[0] == ["auth", "list", "--format=json"]
        assert calls[1] == ["auth", "login", "--no-launch-browser"]

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
        calls = []

        def fake_gcloud(args):
            calls.append(args)
            if "set" in args:
                return _gc_result(0)
            return _gc_result(0, "ya29.access-token\n")

        monkeypatch.setattr(provider, "_gcloud", fake_gcloud)
        creds = provider.get_credentials(
            org, "my-project", "roles/viewer", "us-central1"
        )

        assert creds["GOOGLE_CLOUD_PROJECT"] == "my-project"
        assert creds["CLOUDSDK_CORE_PROJECT"] == "my-project"
        assert creds["GCLOUD_PROJECT"] == "my-project"
        assert creds["GOOGLE_OAUTH_ACCESS_TOKEN"] == "ya29.access-token"

    def test_get_credentials_set_project_fails_exits(self, provider, org, monkeypatch):
        monkeypatch.setattr(provider, "_gcloud", lambda args: _gc_result(1))
        with pytest.raises(SystemExit):
            provider.get_credentials(org, "my-project", "roles/viewer", "us-central1")

    def test_get_credentials_token_fetch_fails_exits(self, provider, org, monkeypatch):
        call_count = [0]

        def fake_gcloud(args):
            call_count[0] += 1
            if "set" in args:
                return _gc_result(0)
            return _gc_result(1)  # token fetch fails

        monkeypatch.setattr(provider, "_gcloud", fake_gcloud)
        with pytest.raises(SystemExit):
            provider.get_credentials(org, "my-project", "roles/viewer", "us-central1")

    # --- get_unsets / get_exports -------------------------------------------

    def test_get_unsets_covers_all_env_vars(self, provider):
        unsets = provider.get_unsets()
        for var in GcpProvider._ENV_VARS:
            assert f"unset {var}" in unsets

    def test_get_exports_format(self, provider, org, monkeypatch):
        def fake_gcloud(args):
            if "set" in args:
                return _gc_result(0)
            return _gc_result(0, "ya29.tok\n")

        monkeypatch.setattr(provider, "_gcloud", fake_gcloud)
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
