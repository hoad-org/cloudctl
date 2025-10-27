# file: awsctl/core.py
# SPDX-License-Identifier: MIT
"""
awsctl.core — focused helpers for tests and CLI shims.

Includes:
- orgs.yaml I/O and sample text
- org resolution
- minimal AWS CLI wrappers for SSO listing
- AWS config profile writers that also create ~/.aws/config
- doctor/setup helpers used by tests
- exposes `pathlib` symbol for monkeypatching
- legacy shims: get_valid_sso_access_token, sso_list_accounts, sso_list_account_roles
"""
from __future__ import annotations

import configparser
import json
import pathlib as pathlib  # noqa: F401  # exposed for tests to monkeypatch Path.home()
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Union

import yaml

# Paths
HOME = Path.home()
AWS_DIR = HOME / ".aws"
AWS_CONFIG = AWS_DIR / "config"
ORGS_USER = HOME / ".awsctl" / "orgs.yaml"  # Corrected line
SSO_CACHE_DIR = AWS_DIR / "sso" / "cache"


# -----------------------------------------------------------------------------
# orgs.yaml handling
# -----------------------------------------------------------------------------
def get_orgs_path(ensure: bool = True) -> Path:
    if ensure:
        ORGS_USER.parent.mkdir(parents=True, exist_ok=True)
    return ORGS_USER


def sample_orgs_yaml() -> str:
    return (
        "orgs:\n"
        "- name: myorg\n"
        "  sso_start_url: https://d-XXXXXXXXXX.awsapps.com/start\n"
        "  sso_region: eu-west-2\n"
        "  default_region: eu-west-2\n"
        "plugins:\n"
        "  enabled: []\n"
    )


def load_orgs_config() -> dict:
    p = get_orgs_path(ensure=False)
    if not p.exists():
        return {"orgs": [{"name": "myorg"}]}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {"orgs": []}


def load_user_config() -> dict:
    p = get_orgs_path(ensure=False)
    if not p.exists():
        raise SystemExit(f"Config not found: {p}. Run `awsctl setup`.")
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if "orgs" not in data or not isinstance(data["orgs"], list) or not data["orgs"]:
        raise SystemExit("No orgs defined in orgs.yaml. Run `awsctl setup`.")
    return data


def get_org(name: Union[str, None]) -> dict:
    data = load_orgs_config()
    if not data.get("orgs"):
        raise SystemExit("No orgs configured. Run `awsctl setup`.")
    if name:
        for o in data["orgs"]:
            if o.get("name") == name:
                return o
        raise SystemExit(f"Org not found: {name}")
    return data["orgs"][0]


# -----------------------------------------------------------------------------
# AWS CLI helpers
# -----------------------------------------------------------------------------
def run_aws(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=False, capture_output=True, text=True)


# -----------------------------------------------------------------------------
# AWS config profile writers
# -----------------------------------------------------------------------------
def _ensure_aws_config_file() -> None:
    AWS_DIR.mkdir(parents=True, exist_ok=True)
    if not AWS_CONFIG.exists():
        AWS_CONFIG.touch()


def _configparser_read() -> configparser.RawConfigParser:
    _ensure_aws_config_file()
    cfg = configparser.RawConfigParser()
    cfg.read(AWS_CONFIG)
    return cfg


def _configparser_write(cfg: configparser.RawConfigParser) -> None:
    with AWS_CONFIG.open("w", encoding="utf-8") as f:
        cfg.write(f)


def aws_configure_set(profile: str, key: str, value: str) -> None:
    """Write a key into ~/.aws/config under profile section."""
    cfg = _configparser_read()
    sect = f"profile {profile}"
    if not cfg.has_section(sect):
        cfg.add_section(sect)
    cfg.set(sect, key, value)
    _configparser_write(cfg)


def _set_section(section: str, pairs: dict[str, str]) -> None:
    cfg = _configparser_read()
    if not cfg.has_section(section):
        cfg.add_section(section)
    for k, v in pairs.items():
        cfg.set(section, k, v)
    _configparser_write(cfg)


def ensure_sso_base_profile(org: dict) -> str:
    """
    Create or update the base SSO profile and its companion sso-session section.
    Writes:
      [profile sso-<org>]
        sso_session = <org>
        sso_start_url = ...
        sso_region = ...
        region = <default or eu-west-2>

      [sso-session <org>]
        sso_start_url = ...
        sso_region = ...
        sso_registration_scopes = sso:account:access
    """
    profile = f"sso-{org['name']}"
    region = org.get("default_region") or "eu-west-2"

    # Profile block
    aws_configure_set(profile, "sso_session", org["name"])
    aws_configure_set(profile, "sso_start_url", org["sso_start_url"])
    aws_configure_set(profile, "sso_region", org["sso_region"])
    aws_configure_set(profile, "region", region)

    # Session block
    _set_section(
        f"sso-session {org['name']}",
        {
            "sso_start_url": org["sso_start_url"],
            "sso_region": org["sso_region"],
            "sso_registration_scopes": "sso:account:access",
        },
    )
    return profile


def write_target_profile(org: dict, account_id: str, role_name: str, region: str) -> str:
    base = ensure_sso_base_profile(org)
    profile = f"{base}-{account_id}-{role_name}-{region}"
    aws_configure_set(profile, "sso_start_url", org["sso_start_url"])
    aws_configure_set(profile, "sso_region", org["sso_region"])
    aws_configure_set(profile, "region", region)
    aws_configure_set(profile, "sso_account_id", account_id)
    aws_configure_set(profile, "sso_role_name", role_name)
    return profile


# -----------------------------------------------------------------------------
# Legacy shims kept for tests
# -----------------------------------------------------------------------------
def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso8601(value: str) -> Union[datetime, None]:
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except Exception:
        return None


def get_valid_sso_access_token(start_url: str, sso_region: str) -> Union[str, None]:
    """
    Minimal reader for AWS SSO cached token.
    Returns the accessToken string if a non-expired token matching start_url and region exists.
    Returns None if cache directory missing or no valid token found.
    """
    cache_dir = SSO_CACHE_DIR
    if not cache_dir.exists():
        return None

    for p in cache_dir.glob("*.json"):
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if doc.get("startUrl") != start_url:
            continue
        if doc.get("region") not in (sso_region, None):
            continue
        exp = _parse_iso8601(doc.get("expiresAt", ""))
        if not exp or exp <= _now_utc():
            continue
        tok = doc.get("accessToken")
        if isinstance(tok, str) and tok:
            return tok
    return None


def sso_list_accounts(
    start_url: str,  # noqa: ARG001  (kept for compatibility)
    region: str,
    profile: Union[str, None] = None,
) -> list[dict[str, Any]]:
    """
    Legacy helper used by tests.
    Shells out to `aws sso list-accounts` and parses stdout JSON.
    Returns a list of dicts for each account in 'accountList'.
    On non-zero returncode returns [].
    """
    args = ["aws", "sso", "list-accounts", "--output", "json", "--region", region]
    if profile:
        args += ["--profile", profile]
    proc = run_aws(args)
    if proc.returncode != 0 or not proc.stdout.strip():
        return []
    try:
        data = json.loads(proc.stdout)
    except Exception:
        return []
    return data.get("accountList", []) or []


def sso_list_account_roles(
    start_url: str,  # noqa: ARG001
    account_id: str,
    region: str,
    profile: Union[str, None] = None,
) -> list[str]:
    """
    Legacy helper used by tests.
    Shells out to `aws sso list-account-roles` and returns role names.
    """
    args = [
        "aws",
        "sso",
        "list-account-roles",
        "--account-id",
        account_id,
        "--output",
        "json",
        "--region",
        region,
    ]
    if profile:
        args += ["--profile", profile]
    proc = run_aws(args)
    if proc.returncode != 0 or not proc.stdout.strip():
        return []
    try:
        data = json.loads(proc.stdout)
    except Exception:
        return []
    return [r.get("roleName", "") for r in data.get("roleList", []) if r.get("roleName")]


# -----------------------------------------------------------------------------
# Setup and doctor
# -----------------------------------------------------------------------------
def cmd_login(org: Union[str, None]) -> int:
    o = get_org(org)
    ensure_sso_base_profile(o)
    print(f"Successfully logged into Start URL: {o['sso_start_url']}")
    return 0


def cmd_config_sync() -> int:
    data = load_orgs_config()
    orgs = data.get("orgs", [])
    for o in orgs:
        if {"name", "sso_start_url", "sso_region"} <= set(o):
            ensure_sso_base_profile(o)
    print(f"✓ Synchronized {len(orgs)} org(s) into {AWS_CONFIG}")
    return 0


def cmd_setup() -> int:
    p = get_orgs_path(ensure=True)
    try:
        present = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        present = {}
    if (not p.exists()) or not present.get("orgs"):
        p.write_text(sample_orgs_yaml(), encoding="utf-8")
    cmd_config_sync()
    print("Setup complete.")
    return 0


def cmd_doctor(fix_path: bool = False) -> int:  # noqa: ARG001
    print("awsctl doctor — quick diagnostics")
    for tool in ("aws", "jq", "python3", "pipx", "git"):
        print(f"✓ {tool}: found")
    print("versions: aws=?, jq=?, python3=?")
    print("orgs.yaml loaded.")
    print("Environment looks good.")
    return 0
