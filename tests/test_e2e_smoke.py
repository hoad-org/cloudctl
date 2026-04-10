"""
End-to-end smoke tests for the full switch flow across all three providers.

These tests mock the provider/CLI layer but exercise the real code path:
  cmd_switch → run_interactive_use → provider.list_accounts → provider.get_credentials
              → emit_exports → print (captured by wrapper)
"""
from types import SimpleNamespace
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_args(org=None, account=None, role=None, region=None, target=None):
    return SimpleNamespace(
        org=org,
        account=account,
        role=role,
        region=region,
        target=target,
        hook_output=None,
    )


def _make_sso_token():
    tok = MagicMock()
    tok.accessToken = "fake-access-token"
    return tok


# ---------------------------------------------------------------------------
# AWS E2E
# ---------------------------------------------------------------------------


class TestAwsSwitchE2E:
    def test_full_aws_switch(self, monkeypatch, capsys):
        """Full AWS switch: org → account → role → region → export lines printed."""
        import awsctl.cli as cli
        import awsctl.interactive as interactive

        org_cfg = {
            "name": "engineering",
            "provider": "aws",
            "partition": "aws",
            "sso_start_url": "https://d-abc.awsapps.com/start",
            "sso_region": "us-east-1",
            "allowed_regions": ["us-east-1"],
        }

        monkeypatch.setattr("awsctl.config.get_org", lambda n: org_cfg)
        monkeypatch.setattr("awsctl.config.load_config", lambda: {"orgs": [org_cfg]})
        monkeypatch.setattr(
            "awsctl.interactive.load_active_sso_token", lambda org: _make_sso_token()
        )
        monkeypatch.setattr(
            interactive,
            "list_accounts",
            lambda token: [{"id": "123456789012", "name": "prod-account"}],
        )
        monkeypatch.setattr(
            interactive, "list_roles", lambda token, acct: ["AdministratorAccess"]
        )
        monkeypatch.setattr(
            interactive,
            "select_account",
            lambda accounts, org_name=None: "123456789012",
        )
        monkeypatch.setattr(
            interactive, "select_role", lambda org_data, roles: "AdministratorAccess"
        )
        monkeypatch.setattr("awsctl.context_manager.save_context", lambda *a, **k: None)

        fake_exports = (
            "export AWS_ACCESS_KEY_ID=FAKEKEYID4TESTING001\n"
            "export AWS_SECRET_ACCESS_KEY=FAKESECRET4TESTING\n"
            "export AWS_SESSION_TOKEN=tok\n"
            "export AWS_PROFILE=engineering-123456789012-AdministratorAccess"
        )
        monkeypatch.setattr(cli, "emit_exports", lambda *a, **k: fake_exports)

        args = _make_args(org="engineering")
        rc = cli.cmd_switch(args)
        assert rc == 0

        out = capsys.readouterr().out
        assert "AWS_ACCESS_KEY_ID" in out
        assert "AdministratorAccess" in out

    def test_aws_switch_no_session_triggers_autologin(self, monkeypatch, capsys):
        """When no SSO token exists, interactive.py auto-logins then continues."""
        import awsctl.interactive as interactive

        org_cfg = {
            "name": "engineering",
            "provider": "aws",
            "sso_start_url": "https://d.awsapps.com/start",
            "sso_region": "us-east-1",
            "allowed_regions": ["us-east-1"],
        }

        call_count = {"n": 0}

        def _fake_token(org):
            # First call returns None (no session); second returns a token (after login)
            call_count["n"] += 1
            return None if call_count["n"] == 1 else _make_sso_token()

        monkeypatch.setattr("awsctl.interactive.load_active_sso_token", _fake_token)
        monkeypatch.setattr("awsctl.core.cmd_login", lambda name, force=False: 0)
        monkeypatch.setattr(
            interactive, "list_accounts", lambda token: [{"id": "111", "name": "acct"}]
        )
        monkeypatch.setattr(interactive, "list_roles", lambda token, acct: ["ReadOnly"])
        monkeypatch.setattr(
            interactive, "select_account", lambda accts, org_name=None: "111"
        )
        monkeypatch.setattr(
            interactive, "select_role", lambda org_data, roles: "ReadOnly"
        )
        monkeypatch.setattr("awsctl.context_manager.save_context", lambda *a, **k: None)
        monkeypatch.setattr(
            "awsctl.use_exports.load_active_sso_token", lambda org: _make_sso_token()
        )
        monkeypatch.setattr(
            "awsctl.use_exports._aws_json",
            lambda args: {
                "roleCredentials": {
                    "accessKeyId": "AKI",
                    "secretAccessKey": "SAK",
                    "sessionToken": "ST",
                }
            },
        )

        account, role, region = interactive.run_interactive_use(
            org_cfg, None, None, "us-east-1"
        )
        assert account == "111"
        assert role == "ReadOnly"


# ---------------------------------------------------------------------------
# Azure E2E
# ---------------------------------------------------------------------------


class TestAzureSwitchE2E:
    def test_full_azure_switch(self, monkeypatch, capsys):
        """Full Azure switch: emit AZURE_* environment variables."""
        import awsctl.cli as cli
        import awsctl.interactive as interactive

        org_cfg = {
            "name": "azure-prod",
            "provider": "azure",
            "tenant_id": "abc-tenant",
            "default_subscription": "sub-123",
            "allowed_regions": ["eastus"],
        }

        monkeypatch.setattr("awsctl.config.get_org", lambda n: org_cfg)
        monkeypatch.setattr("awsctl.config.load_config", lambda: {"orgs": [org_cfg]})
        monkeypatch.setattr(
            "awsctl.interactive.load_active_sso_token",
            lambda org: {"token": "az-token"},
        )
        monkeypatch.setattr(
            interactive,
            "list_accounts",
            lambda token: [{"id": "sub-123", "name": "my-subscription"}],
        )
        monkeypatch.setattr(
            interactive, "list_roles", lambda token, acct: ["Contributor"]
        )
        monkeypatch.setattr(
            interactive, "select_account", lambda accounts, org_name=None: "sub-123"
        )
        monkeypatch.setattr(
            interactive, "select_role", lambda org_data, roles: "Contributor"
        )
        monkeypatch.setattr("awsctl.context_manager.save_context", lambda *a, **k: None)

        fake_exports = (
            "export AZURE_SUBSCRIPTION_ID=sub-123\n"
            "export AZURE_TENANT_ID=abc-tenant\n"
            "export ARM_ACCESS_TOKEN=fake-tok"
        )
        monkeypatch.setattr(cli, "emit_exports", lambda *a, **k: fake_exports)

        args = _make_args(org="azure-prod")
        rc = cli.cmd_switch(args)
        assert rc == 0

        out = capsys.readouterr().out
        assert "AZURE_SUBSCRIPTION_ID" in out
        assert "ARM_ACCESS_TOKEN" in out


# ---------------------------------------------------------------------------
# GCP E2E
# ---------------------------------------------------------------------------


class TestGcpSwitchE2E:
    def test_full_gcp_switch(self, monkeypatch, capsys):
        """Full GCP switch: emit GOOGLE_* environment variables."""
        import awsctl.cli as cli
        import awsctl.interactive as interactive

        org_cfg = {
            "name": "gcp-prod",
            "provider": "gcp",
            "default_project": "my-gcp-project",
            "allowed_regions": ["us-central1"],
        }

        monkeypatch.setattr("awsctl.config.get_org", lambda n: org_cfg)
        monkeypatch.setattr("awsctl.config.load_config", lambda: {"orgs": [org_cfg]})
        monkeypatch.setattr(
            "awsctl.interactive.load_active_sso_token", lambda org: "ya29.gcp-token"
        )
        monkeypatch.setattr(
            interactive,
            "list_accounts",
            lambda token: [{"id": "my-gcp-project", "name": "My GCP Project"}],
        )
        monkeypatch.setattr(
            interactive, "list_roles", lambda token, acct: ["roles/viewer"]
        )
        monkeypatch.setattr(
            interactive,
            "select_account",
            lambda accounts, org_name=None: "my-gcp-project",
        )
        monkeypatch.setattr(
            interactive, "select_role", lambda org_data, roles: "roles/viewer"
        )
        monkeypatch.setattr("awsctl.context_manager.save_context", lambda *a, **k: None)

        fake_exports = (
            "export GOOGLE_CLOUD_PROJECT=my-gcp-project\n"
            "export CLOUDSDK_CORE_PROJECT=my-gcp-project\n"
            "export GOOGLE_OAUTH_ACCESS_TOKEN=ya29.gcp-token"
        )
        monkeypatch.setattr(cli, "emit_exports", lambda *a, **k: fake_exports)

        args = _make_args(org="gcp-prod")
        rc = cli.cmd_switch(args)
        assert rc == 0

        out = capsys.readouterr().out
        assert "GOOGLE_CLOUD_PROJECT" in out
        assert "GOOGLE_OAUTH_ACCESS_TOKEN" in out


# ---------------------------------------------------------------------------
# Doctor schema check
# ---------------------------------------------------------------------------


class TestDoctorSchemaCheck:
    def test_doctor_warns_on_invalid_config(self, monkeypatch):
        """doctor.run_diagnostics reports schema errors in the config section."""
        import awsctl.doctor as doctor

        # Bad config: org with unknown provider
        bad_config = {
            "orgs": [{"name": "test", "provider": "k8s"}],
            "enabled_orgs": [],
        }
        monkeypatch.setattr("awsctl.config.load_orgs_config", lambda: [])
        monkeypatch.setattr("awsctl.config.load_raw_config", lambda: bad_config)
        monkeypatch.setattr(doctor, "is_wsl", lambda: False)
        monkeypatch.setattr(doctor, "check_aws_version", lambda: (True, "aws/2.15.0"))
        monkeypatch.setattr(
            doctor, "check_shell_integration", lambda: (True, "Present")
        )
        monkeypatch.setattr(doctor, "check_permissions", lambda: (True, "User owned"))
        monkeypatch.setattr(doctor, "check_network_ssl", lambda: (True, "Reachable"))
        monkeypatch.setattr(doctor, "check_time_sync", lambda: (True, "Synced"))

        rc = doctor.run_diagnostics()
        # Should fail because of schema error
        assert rc == 1
