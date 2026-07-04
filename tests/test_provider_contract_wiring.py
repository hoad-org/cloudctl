# file: tests/test_provider_contract_wiring.py
# SPDX-License-Identifier: MIT
"""
Tests for wiring the CLI layer to the honest provider contract and the
intuitiveness fixes an adversarial review found.

Covers:
  1. FAITHFUL ERRORS — ProviderCredentialError.code/.message propagate through
     exec (run), accounts, and roles with the real exit code (a Forbidden exits
     4/DENIED, an expired session 2/AUTH — never flattened to "no SSO session").
  3. `roles` provider dispatch — GCP/Azure orgs skip the AWS-SSO token gate.
  4. Azure bare-`az` safety — warn + inject --subscription when no SP identity.
  5. `--role` provider-aware — AWS requires it; GCP/Azure do not.
  6. `--` footgun + exit-code collision — child `--version` never fires
     cloudctl's version; usage/parse errors exit 5 (USAGE), not argparse's 2.
  8. `doctor` single-format — never both table and JSON.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from cloudctl import cli, exit_codes
from cloudctl.commands.accounts import AccountsCommand
from cloudctl.commands.exec import ExecCommand
from cloudctl.commands.list_roles import ListRolesCommand
from cloudctl.providers.base import ProviderCredentialError


# ---------------------------------------------------------------------------
# 1. FAITHFUL ERRORS in `run`/exec
# ---------------------------------------------------------------------------

_ORG = {"name": "myorg", "provider": "aws"}


def _exec_args(**kw):
    base = dict(
        exec_org="myorg",
        exec_account="123456789012",
        exec_role="Admin",
        exec_region="us-east-1",
        json_errors=False,
        cmd=["aws", "sts", "get-caller-identity"],
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _run_exec(provider, args, ctx=None):
    ec = ExecCommand()
    ec.console = MagicMock()
    with patch("cloudctl.commands.exec.load_context", return_value=ctx or {}):
        with patch("cloudctl.commands.exec.get_org", return_value=_ORG):
            with patch("cloudctl.providers.get_provider", return_value=provider):
                return ec.execute(args)


def test_exec_forbidden_exits_denied_not_auth():
    """A DENIED (Forbidden) from get_credentials exits 4, NOT flattened to 2."""
    provider = MagicMock()
    provider.az_uses_injected_identity.return_value = False
    provider.get_credentials.side_effect = ProviderCredentialError(
        exit_codes.DENIED, "User is not authorized to perform sso:GetRoleCredentials"
    )
    rc = _run_exec(provider, _exec_args())
    assert rc == exit_codes.DENIED  # 4, not 2


def test_exec_expired_exits_auth():
    """An AUTH (expired token) from get_credentials exits 2."""
    provider = MagicMock()
    provider.az_uses_injected_identity.return_value = False
    provider.get_credentials.side_effect = ProviderCredentialError(
        exit_codes.AUTH, "Authentication required: run 'cloudctl login <org>'."
    )
    rc = _run_exec(provider, _exec_args())
    assert rc == exit_codes.AUTH


def test_exec_faithful_message_is_json_aware():
    """--json-errors emits {"error","code"} carrying the real reason + code."""
    provider = MagicMock()
    provider.az_uses_injected_identity.return_value = False
    provider.get_credentials.side_effect = ProviderCredentialError(
        exit_codes.DENIED, "Forbidden: role not assigned"
    )
    ec = ExecCommand()
    ec.console = MagicMock()
    import io
    import contextlib

    buf = io.StringIO()
    with patch("cloudctl.commands.exec.load_context", return_value={}):
        with patch("cloudctl.commands.exec.get_org", return_value=_ORG):
            with patch("cloudctl.providers.get_provider", return_value=provider):
                with contextlib.redirect_stderr(buf):
                    rc = ec.execute(_exec_args(json_errors=True))
    assert rc == exit_codes.DENIED
    payload = json.loads(buf.getvalue().strip().splitlines()[-1])
    assert payload["code"] == exit_codes.DENIED
    assert payload["error"] == "Forbidden: role not assigned"


# ---------------------------------------------------------------------------
# 5. `--role` provider-aware (exec/run)
# ---------------------------------------------------------------------------


def test_exec_aws_missing_role_teaches_and_is_usage():
    """AWS with no --role must fail USAGE with a teaching message; never run."""
    provider = MagicMock()
    ec = ExecCommand()
    ec.console = MagicMock()
    args = _exec_args(exec_role="")
    with patch("cloudctl.commands.exec.load_context", return_value={}):
        with patch("cloudctl.commands.exec.get_org", return_value=_ORG):
            with patch("cloudctl.providers.get_provider", return_value=provider):
                rc = ec.execute(args)
    assert rc == exit_codes.USAGE
    # Never reached credential vending.
    provider.get_credentials.assert_not_called()
    # Message teaches: mention --role and the `roles` command.
    printed = " ".join(str(c) for c in ec.console.print.call_args_list)
    assert "--role" in printed and "roles" in printed


def test_exec_gcp_missing_role_does_not_block():
    """GCP with no --role must NOT block — role is a no-op there."""
    gcp_org = {"name": "gcp-x", "provider": "gcp"}
    provider = MagicMock()
    provider.az_uses_injected_identity.return_value = False
    provider.get_credentials.return_value = {"GOOGLE_CLOUD_PROJECT": "p"}
    ec = ExecCommand()
    ec.console = MagicMock()
    args = _exec_args(exec_role="", exec_account="proj-1", cmd=["gcloud", "info"])
    with patch("cloudctl.commands.exec.load_context", return_value={}):
        with patch("cloudctl.commands.exec.get_org", return_value=gcp_org):
            with patch("cloudctl.providers.get_provider", return_value=provider):
                with patch("subprocess.run", return_value=SimpleNamespace(returncode=0)):
                    rc = ec.execute(args)
    assert rc == 0
    provider.get_credentials.assert_called_once()


# ---------------------------------------------------------------------------
# 4. Azure bare-`az` safety
# ---------------------------------------------------------------------------


def test_exec_azure_bare_az_warns_and_pins_subscription(capsys):
    """A bare `az` under an Azure org with NO SP identity warns to stderr and
    injects --subscription <account> to pin the target."""
    az_org = {"name": "az-x", "provider": "azure"}
    provider = MagicMock()
    provider.az_uses_injected_identity.return_value = False
    provider.get_credentials.return_value = {"ARM_SUBSCRIPTION_ID": "sub-123"}
    ec = ExecCommand()
    ec.console = MagicMock()
    captured_cmd = {}

    def _fake_run(cmd, env=None):
        captured_cmd["cmd"] = cmd
        return SimpleNamespace(returncode=0)

    args = _exec_args(exec_role="", exec_account="sub-123", cmd=["az", "account", "show"])
    with patch("cloudctl.commands.exec.load_context", return_value={}):
        with patch("cloudctl.commands.exec.get_org", return_value=az_org):
            with patch("cloudctl.providers.get_provider", return_value=provider):
                with patch("subprocess.run", side_effect=_fake_run):
                    rc = ec.execute(args)
    assert rc == 0
    err = capsys.readouterr().err
    assert "WARNING" in err and "ambient" in err.lower()
    # --subscription was injected right after `az`.
    assert captured_cmd["cmd"][:3] == ["az", "--subscription", "sub-123"]


def test_exec_azure_sp_identity_no_warning(capsys):
    """When SP creds ARE present (az_uses_injected_identity True) — no warning,
    no --subscription injection: the injected AZURE_CLIENT_* does the work."""
    az_org = {"name": "az-x", "provider": "azure"}
    provider = MagicMock()
    provider.az_uses_injected_identity.return_value = True
    provider.get_credentials.return_value = {"AZURE_CLIENT_ID": "c"}
    ec = ExecCommand()
    ec.console = MagicMock()
    captured_cmd = {}

    def _fake_run(cmd, env=None):
        captured_cmd["cmd"] = cmd
        return SimpleNamespace(returncode=0)

    args = _exec_args(exec_role="", exec_account="sub-123", cmd=["az", "account", "show"])
    with patch("cloudctl.commands.exec.load_context", return_value={}):
        with patch("cloudctl.commands.exec.get_org", return_value=az_org):
            with patch("cloudctl.providers.get_provider", return_value=provider):
                with patch("subprocess.run", side_effect=_fake_run):
                    rc = ec.execute(args)
    assert rc == 0
    err = capsys.readouterr().err
    assert "WARNING" not in err
    assert captured_cmd["cmd"] == ["az", "account", "show"]  # untouched


# ---------------------------------------------------------------------------
# 1 + 3. accounts / roles map ProviderCredentialError to exit code
# ---------------------------------------------------------------------------


def test_accounts_provider_error_maps_code_json(capsys):
    """accounts surfaces a raised ProviderCredentialError with its real code."""
    ac = AccountsCommand()
    ac.console = MagicMock()
    args = SimpleNamespace(org="gcp-x", org_flag=None, sync=False, format="json")
    with patch("cloudctl.commands.accounts.get_org", return_value={"provider": "gcp"}):
        with patch(
            "cloudctl.commands.accounts.get_account_list",
            side_effect=ProviderCredentialError(exit_codes.AUTH, "reauth required"),
        ):
            rc = ac.execute(args)
    assert rc == exit_codes.AUTH
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["code"] == exit_codes.AUTH
    assert payload["error"] == "reauth required"


def test_roles_non_aws_skips_sso_token_gate():
    """A GCP org must NOT hit the AWS-SSO token gate — it reaches list_roles.

    Before the fix, roles_by_account called load_active_sso_token
    unconditionally, so every GCP/Azure org got a bogus "No active SSO session"
    error and never reached provider.list_roles.
    """
    lrc = ListRolesCommand()
    lrc.console = MagicMock()
    gcp_org = {"name": "gcp-x", "provider": "gcp", "roles": ["roles/viewer"]}
    provider = MagicMock()
    provider.list_roles.return_value = ["roles/viewer", "roles/editor"]

    sso_called = {"n": 0}

    def _sso(_ref):
        sso_called["n"] += 1
        return None  # would raise "No active SSO session" if the gate ran

    with patch("cloudctl.config.get_org", return_value=gcp_org):
        with patch("cloudctl.providers.get_provider", return_value=provider):
            with patch("cloudctl.sso_cache.load_active_sso_token", side_effect=_sso):
                data = lrc.roles_by_account("gcp-x", account="proj-1")
    # The SSO-token gate was skipped entirely for the non-AWS provider.
    assert sso_called["n"] == 0
    # list_roles was called with token=None (mirrors accounts dispatch).
    provider.list_roles.assert_called_once()
    assert provider.list_roles.call_args.args[1] is None
    assert data["proj-1"]["roles"] == ["roles/viewer", "roles/editor"]


def test_roles_provider_error_maps_code(capsys):
    """roles maps a raised ProviderCredentialError to its code (json-aware)."""
    lrc = ListRolesCommand()
    lrc.console = MagicMock()
    args = SimpleNamespace(org="gcp-x", org_flag=None, account="proj-1", format="json")
    with patch.object(
        ListRolesCommand,
        "roles_by_account",
        side_effect=ProviderCredentialError(exit_codes.DENIED, "no access"),
    ):
        with patch.object(ListRolesCommand, "_resolve_org", return_value="gcp-x"):
            rc = lrc.execute(args)
    assert rc == exit_codes.DENIED
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["code"] == exit_codes.DENIED
    assert payload["error"] == "no access"


# ---------------------------------------------------------------------------
# 6. `--` footgun + exit-code collision
# ---------------------------------------------------------------------------


def test_child_version_without_dashdash_never_fires_cloudctl_version(capsys):
    """`run ... aws --version` (no `--`) must NEVER print cloudctl's version.

    The `--version` there belongs to the child `aws`; cloudctl must not
    short-circuit to its own version action.
    """
    rc = cli.main(
        [
            "run",
            "--org",
            "myorg",
            "--account",
            "A",
            "--role",
            "R",
            "--region",
            "G",
            "aws",
            "--version",
        ]
    )
    out = capsys.readouterr().out
    # cloudctl's version string was NOT emitted.
    assert cli._resolved_version() not in out
    # It is NOT a version short-circuit (which returns 0); it's a usage error.
    assert rc == exit_codes.USAGE


def test_version_only_fires_as_first_token(capsys):
    """A genuine top-level `--version` (first token) still prints + exits 0."""
    rc = cli.main(["--version"])
    assert rc == 0
    assert cli._resolved_version() in capsys.readouterr().out


def test_unknown_subcommand_exits_usage_five(capsys):
    """An unknown subcommand exits 5 (USAGE), never argparse's default 2 (AUTH)."""
    rc = cli.main(["definitely-not-a-subcommand"])
    assert rc == exit_codes.USAGE
    assert rc != exit_codes.AUTH


def test_bad_flag_exits_usage_five(capsys):
    """A bad flag on a real subcommand exits 5 (USAGE), not 2 (AUTH)."""
    rc = cli.main(["whoami", "--nonsense-flag"])
    assert rc == exit_codes.USAGE
    assert rc != exit_codes.AUTH


# ---------------------------------------------------------------------------
# 8. doctor single-format (never both)
# ---------------------------------------------------------------------------


def test_doctor_json_emits_no_table(capsys, monkeypatch):
    """doctor --format json emits ONLY JSON on stdout — no Rich table anywhere."""
    from cloudctl import doctor

    rc = doctor.run_diagnostics(fmt="json")
    captured = capsys.readouterr()
    # stdout is a single valid JSON object.
    payload = json.loads(captured.out.strip())
    assert "checks" in payload and "ok" in payload
    # The human table header must NOT appear on EITHER stream.
    assert "System Health Check" not in captured.out
    assert "System Health Check" not in captured.err
    assert rc in (0, 1)


def test_doctor_table_emits_no_json(capsys, monkeypatch):
    """doctor --format table emits ONLY the table — no JSON blob on stdout."""
    from cloudctl import doctor

    doctor.run_diagnostics(fmt="table")
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "System Health Check" in combined
    # No JSON summary object leaked out.
    assert '"issue_count"' not in combined


def test_doctor_no_shell_integration_is_not_a_failure(monkeypatch):
    """A fresh install with no shell wrapper installed must NOT exit nonzero —
    shell integration is advisory, not a hard issue."""
    from cloudctl import doctor

    # Everything healthy except shell integration (absent, as on first run).
    monkeypatch.setattr(doctor, "check_aws_version", lambda: (True, "ok"))
    monkeypatch.setattr(
        doctor, "check_shell_integration", lambda: (False, "not installed")
    )
    monkeypatch.setattr(doctor, "check_permissions", lambda: (True, "ok"))
    monkeypatch.setattr(doctor, "check_network_ssl", lambda: (True, "ok"))
    monkeypatch.setattr(doctor, "check_time_sync", lambda: (True, "ok"))
    monkeypatch.setattr(doctor, "is_wsl", lambda: False)
    monkeypatch.setattr(
        "cloudctl.config.load_raw_config", lambda: {"organizations": {}}
    )
    monkeypatch.setattr("cloudctl.schema.validate_orgs_config", lambda raw: [])

    rc = doctor.run_diagnostics(fmt="json")
    assert rc == 0  # first run is healthy despite no shell wrapper
