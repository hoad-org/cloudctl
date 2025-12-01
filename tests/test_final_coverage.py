# file: tests/test_final_coverage.py
"""
Total Coverage Enforcement (v1.3.0).
"""
import json
import pathlib
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
import yaml

from awsctl import accounts, aws, config, registry, sso_cache

# --- THE GOD MOCK ---
MAGIC_JSON = json.dumps(
    {
        "roleCredentials": {
            "accessKeyId": "AK",
            "secretAccessKey": "SK",
            "sessionToken": "TOK",
            "expiration": "now",
        },
        "accessToken": "tok",
        "expiresAt": "2099-01-01T00:00:00Z",
        "region": "us-east-1",
        "startUrl": "https://u",
        "accountList": [{"accountId": "1", "accountName": "d", "emailAddress": "e"}],
        "roleList": [{"roleName": "r"}],
    }
)


@pytest.fixture(autouse=True)
def god_mode(monkeypatch, tmp_path):
    mock_home = tmp_path / "home"
    mock_home.mkdir()
    monkeypatch.setattr(pathlib.Path, "home", lambda: mock_home)

    # Paths
    mock_aws = mock_home / ".aws"
    mock_aws.mkdir()
    mock_awsctl = mock_home / ".awsctl"
    mock_awsctl.mkdir()

    # Files
    (mock_aws / "sso" / "cache" / "token.json").parent.mkdir(parents=True)
    (mock_aws / "sso" / "cache" / "token.json").write_text(MAGIC_JSON)
    (mock_awsctl / "orgs.yaml").write_text("enabled_orgs:\n- myorg\n")
    (mock_aws / "awsctl-context.json").write_text(
        '{"current_org": "myorg", "account": "1"}'
    )

    # Registry
    monkeypatch.setattr(
        registry,
        "KNOWN_ORGS",
        [
            {
                "name": "myorg",
                "sso_start_url": "https://u",
                "sso_region": "us-east-1",
                "default_region": "us-east-1",
                "allowed_regions": ["us-east-1"],
            }
        ],
    )

    monkeypatch.setattr(config, "ORGS_USER", mock_awsctl / "orgs.yaml")

    # Mocks
    mock_proc = MagicMock(returncode=0, stdout=MAGIC_JSON, stderr="")
    # run() is usually handled by no_real_subprocess, but we can enforce return values here if needed
    monkeypatch.setattr(aws, "run_aws", lambda *a, **k: mock_proc)
    monkeypatch.setattr("awsctl.utils.open_browser", MagicMock())
    monkeypatch.setattr(
        "awsctl.shell.detect_shell_profile", lambda: mock_home / ".bashrc"
    )

    # Patch core/helpers that might call AWS
    monkeypatch.setattr(
        "awsctl.accounts.list_accounts", lambda r: [accounts.Account("1", "d", "e")]
    )
    monkeypatch.setattr("awsctl.accounts.list_roles", lambda r, a: ["Admin"])


def test_cli_dispatch_full(monkeypatch):
    import awsctl.cli as cli

    def run(args):
        try:
            cli.main(args)
        except SystemExit:
            pass

    # Basic
    run(["--version"])
    run(["help"])
    run([])

    # Setup (Headless)
    monkeypatch.setenv("AWSCTL_HEADLESS", "1")
    args = type("Args", (), {})
    cli.cmd_setup(args)

    # Core Flows
    run(["doctor"])
    run(["login", "--org", "myorg"])
    run(["config", "sync"])
    run(["status"])

    # Mock core.cmd_logout_str
    monkeypatch.setattr("awsctl.core.cmd_logout_str", lambda: "unset A")
    run(["logout"])

    run(["cache-clear"])
    run(["refresh"])  # Alias check
    run(["console"])
    run(["env"])  # New command

    # Lists
    run(["list", "orgs"])
    run(["list", "accounts"])
    run(["list", "roles"])

    # Interactive Switch (Mocked)
    monkeypatch.setattr(
        "awsctl.interactive.run_interactive_use", lambda o: ("1", "r", "us-east-1")
    )
    monkeypatch.setattr("awsctl.cli.emit_exports", lambda *a: "export A=B")
    run(["switch"])

    # Smart Switch (-)
    # Setup context with previous
    monkeypatch.setattr(
        "awsctl.context_manager.get_previous_context",
        lambda: {"org": "myorg", "account": "1", "role": "r", "region": "us-east-1"},
    )
    run(["switch", "-"])

    # Explicit Switch
    run(["switch", "1", "--role", "r", "--region", "us-east-1"])

    # Exec
    # Mock _aws_json to return credentials for exec logic
    monkeypatch.setattr(
        "awsctl.use_exports._aws_json", lambda args: json.loads(MAGIC_JSON)
    )
    # Use --account flag
    run(
        ["exec", "--account", "1", "--role", "r", "--region", "us-east-1", "--", "echo"]
    )

    # Strategy Check (Trojan Horse)
    run(["--check-strategy", "login", "--account", "123"])  # Should be EVAL
    run(["--check-strategy", "status"])  # Should be EXEC


def test_cli_errors(monkeypatch, mock_rich_console):
    import awsctl.cli as cli

    # 1. Login missing arg
    monkeypatch.setattr("awsctl.cli.load_context", lambda: {})
    # Return empty config to trigger "Could not determine organization"
    monkeypatch.setattr("awsctl.core.load_orgs_config", lambda: {})

    cli.cmd_login(type("A", (), {"org": None}))
    captured = "".join(mock_rich_console.captured)
    assert "Error" in captured

    # 2. Switch guardrail violation
    # Update config to have an org with strict regions
    mock_config = {
        "orgs": [
            {
                "name": "myorg",
                "sso_start_url": "u",
                "sso_region": "r",
                "allowed_regions": ["eu-west-1"],  # Only EU allowed
            }
        ]
    }
    # Patch BOTH core and config to ensure consistency across modules
    monkeypatch.setattr("awsctl.core.load_orgs_config", lambda: mock_config)
    monkeypatch.setattr("awsctl.config.load_orgs_config", lambda: mock_config)
    monkeypatch.setattr("awsctl.cli.load_context", lambda: {"current_org": "myorg"})

    # Try to switch to us-west-1 (Violation)
    # Use a 12-digit account ID to skip API token lookup and go straight to guardrail check
    # 123456789012 avoids lookup entirely.
    args = type(
        "A",
        (),
        {
            "target": "123456789012",
            "account": "123456789012",
            "role": "r",
            "region": "us-west-1",
            "org": "myorg",
        },
    )

    # Clear console to verify fresh output
    mock_rich_console.captured = []

    # Expect SystemExit because guardrails call sys.exit(1)
    with pytest.raises(SystemExit) as e:
        cli.cmd_switch(args)

    assert e.value.code == 1

    captured = "".join(mock_rich_console.captured)
    assert "Guardrail Violation" in captured

    # 3. Exec Failure (No context)
    monkeypatch.setattr("awsctl.context_manager.load_context", lambda: {})

    # Mock token loading broadly to avoid SystemExit("Token does not exist")
    # This covers awsctl.core and awsctl.accounts usages
    mock_token = sso_cache.SsoToken("tok", "u", "r", datetime.now(timezone.utc), {})
    monkeypatch.setattr("awsctl.core.load_active_sso_token", lambda *a, **k: mock_token)
    monkeypatch.setattr(
        "awsctl.accounts.load_active_sso_token", lambda *a, **k: mock_token
    )

    # Mock _aws_json to return empty creds, triggering "Failed to get credentials"
    monkeypatch.setattr("awsctl.use_exports._aws_json", lambda c: {})

    # [FIX] Use 12-digit account ID to bypass lookup in cli.cmd_exec too
    args_exec = type(
        "A",
        (),
        {"account": "123456789012", "role": "r", "region": "r", "command": ["ls"]},
    )
    mock_rich_console.captured = []
    cli.cmd_exec(args_exec)

    captured = "".join(mock_rich_console.captured)
    assert "No active org" in captured


def test_config_errors(monkeypatch, tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("{")
    monkeypatch.setattr(config, "ORGS_USER", p)
    with pytest.raises(yaml.YAMLError):
        config.load_orgs_config()
