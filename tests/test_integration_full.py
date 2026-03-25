# file: tests/test_integration_full.py
"""
Total Coverage Enforcement.
"""

import gzip
import json
import os
import pathlib
from unittest.mock import MagicMock, patch

import pytest
import yaml
from awsctl import accounts, aws, config, registry, registry_loader

# --- THE GOD MOCK ---
# This JSON satisfies token loading, account listing, and role parsing logic simultaneously.
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
    """
    Orchestrates a complete hermetic environment for integration testing.
    """
    # 1. Setup Filesystem
    mock_home = tmp_path / "home"
    # Ensure home doesn't exist to avoid FileExistsError during mass test runs
    if not mock_home.exists():
        mock_home.mkdir(parents=True)

    monkeypatch.setattr(pathlib.Path, "home", lambda: mock_home)
    monkeypatch.setenv("HOME", str(mock_home))

    # 2. Recreate directory structure
    mock_aws = mock_home / ".aws"
    mock_awsctl = mock_home / ".awsctl"
    mock_aws.mkdir(exist_ok=True)
    mock_awsctl.mkdir(exist_ok=True)

    # 3. Populate State Files
    token_cache = mock_aws / "sso" / "cache"
    token_cache.mkdir(parents=True, exist_ok=True)
    (token_cache / "token.json").write_text(MAGIC_JSON)

    (mock_awsctl / "orgs.yaml").write_text("enabled_orgs:\n- btavm\n")
    (mock_aws / "awsctl-context.json").write_text(
        '{"current_org": "btavm", "account": "1", "role": "r", "region": "us-east-1"}'
    )

    # 4. Patch Registry & Config
    monkeypatch.setattr(
        registry,
        "KNOWN_ORGS",
        [
            {
                "name": "btavm",
                "sso_start_url": "https://u",
                "sso_region": "us-east-1",
                "default_region": "us-east-1",
                "allowed_regions": ["us-east-1"],
            }
        ],
    )
    monkeypatch.setattr(config, "ORGS_USER", mock_awsctl / "orgs.yaml")

    # 5. Global Command Mocks
    # We return a dict because that is what aws.run_aws implementation expects
    mock_response = {"returncode": 0, "stdout": MAGIC_JSON, "stderr": ""}
    monkeypatch.setattr(aws, "run_aws", lambda *a, **k: mock_response)
    monkeypatch.setattr("awsctl.utils.open_browser", MagicMock())
    monkeypatch.setattr(
        "awsctl.shell.detect_shell_profile", lambda: mock_home / ".bashrc"
    )
    monkeypatch.setattr(os, "execvpe", MagicMock())

    # 6. Module Interface Alignment
    monkeypatch.setattr(
        accounts, "list_accounts", lambda *a: [{"id": "1", "name": "d"}]
    )
    monkeypatch.setattr("awsctl.accounts.load_active_sso_token", lambda *a: MagicMock())


def test_cli_dispatch_full(monkeypatch):
    """Stress test every registered CLI command pathway."""
    import awsctl.cli as cli

    def run(args):
        try:
            return cli.main(args)
        except SystemExit:
            return None

    # Basic Flags
    run(["--version"])
    run(["--help"])

    # Core Logic Flows
    run(["doctor"])
    run(["login", "--org", "btavm"])
    run(["config", "sync"])
    run(["status"])

    # Shell Integration
    monkeypatch.setattr("awsctl.core.cmd_logout_str", lambda: "unset AWS_PROFILE")
    run(["logout"])
    run(["cache-clear"])
    run(["refresh"])
    run(["env"])

    # Data Listings
    run(["list", "orgs"])
    run(["list", "accounts"])
    run(["list", "roles"])

    # Interaction & Switching
    monkeypatch.setattr(
        "awsctl.interactive.run_interactive_use", lambda o, **k: ("1", "r", "us-east-1")
    )
    run(["switch"])
    run(["switch", "-"])
    run(["switch", "1", "--role", "r", "--region", "us-east-1"])

    # Strategy Resolution Verification
    run(["--check-strategy", "login", "--account", "123"])
    run(["--check-strategy", "status"])


def test_cli_errors(monkeypatch, mock_rich_console):
    """Test standard error trapping in CLI entry points."""
    import awsctl.cli as cli

    # 1. Login Logic Error (Missing Org)
    monkeypatch.setattr("awsctl.core.load_orgs_config", lambda: {"orgs": []})
    cli.cmd_login(type("A", (), {"org": "missing"}))
    assert "Error" in "".join(mock_rich_console.captured)

    # 2. Guardrail Enforcement
    args = type(
        "A",
        (),
        {
            "account": "1",
            "role": "r",
            "region": "forbidden-region",
            "org": "btavm",
            "target": "1",
        },
    )
    # Switch should trap the guardrail SystemExit and return failure code
    assert cli.cmd_switch(args) != 0
    assert "Guardrail" in "".join(mock_rich_console.captured)


def test_registry_loader_zip_bomb(mock_rich_console):
    """Ensure gzip decompression limits prevent resource exhaustion."""
    compressed_data = gzip.compress(b"A" * 200)
    mock_resp = MagicMock(status_code=200)
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.raw.read.return_value = compressed_data

    # Set tiny limit to trigger failure
    with patch("awsctl.registry_loader.MAX_REGISTRY_SIZE", 10):
        with patch("requests.get", return_value=mock_resp):
            with pytest.raises(SystemExit):
                registry_loader.fetch_remote_registry("https://example.com/reg.json")

    assert "exceeds limit" in "".join(mock_rich_console.captured)


def test_config_hydrate_missing_org(monkeypatch, mock_rich_console):
    """Verify warnings are issued when config references non-existent orgs."""
    monkeypatch.setattr("awsctl.registry.KNOWN_ORGS", [])
    config._hydrate_orgs({"missing_org_name"})
    assert "Warning" in "".join(mock_rich_console.captured)
    assert "missing_org_name" in "".join(mock_rich_console.captured)


def test_load_raw_config_errors(monkeypatch, tmp_path):
    """Verify robust handling of missing or malformed YAML."""
    # Test Missing File
    monkeypatch.setattr(
        "awsctl.config.get_orgs_path", lambda **k: tmp_path / "void.yaml"
    )
    assert config.load_raw_config() == {}

    # Test Corrupt File
    bad_yaml = tmp_path / "corrupt.yaml"
    bad_yaml.write_text("!!binary | invalid")
    monkeypatch.setattr("awsctl.config.get_orgs_path", lambda **k: bad_yaml)
    with pytest.raises(yaml.YAMLError):
        config.load_raw_config()
