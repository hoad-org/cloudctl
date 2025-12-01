# file: src/awsctl/aws.py
# SPDX-License-Identifier: MIT
"""
awsctl.aws
----------
AWS CLI wrappers, profile management, and SSO token shims.
"""
from __future__ import annotations

import configparser
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Union, cast

from awsctl.utils import run

# Paths
HOME = Path.home()
AWS_DIR = HOME / ".aws"
AWS_CONFIG = AWS_DIR / "config"
SSO_CACHE_DIR = AWS_DIR / "sso" / "cache"


# -----------------------------------------------------------------------------
# AWS CLI Wrapper
# -----------------------------------------------------------------------------
def run_aws(
    args: list[str], timeout: Optional[float] = 10.0
) -> subprocess.CompletedProcess[str]:
    """
    Run an AWS CLI command and return the completed process.
    Accepts timeout to allow long-running commands (like login) to override the default.
    """
    # [FIX] Explicit cast for MyPy strict mode to prevent "Returning Any"
    return cast(
        subprocess.CompletedProcess[str], run(args, check=False, timeout=timeout)
    )


# -----------------------------------------------------------------------------
# Profile Management (~/.aws/config)
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


def _set_section(section: str, pairs: Dict[str, str]) -> None:
    cfg = _configparser_read()
    if not cfg.has_section(section):
        cfg.add_section(section)
    for k, v in pairs.items():
        cfg.set(section, k, v)
    _configparser_write(cfg)


def ensure_sso_base_profile(org: Dict[str, Any]) -> str:
    """Create or update the base SSO profile and sso-session."""
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


def write_target_profile(
    org: Dict[str, Any],
    account_id: str,
    role_name: str,
    region: str,
) -> str:
    """Create a specific profile target for a given role context."""
    base = ensure_sso_base_profile(org)
    profile = f"{base}-{account_id}-{role_name}-{region}"
    aws_configure_set(profile, "sso_start_url", org["sso_start_url"])
    aws_configure_set(profile, "sso_region", org["sso_region"])
    aws_configure_set(profile, "region", region)
    aws_configure_set(profile, "sso_account_id", account_id)
    aws_configure_set(profile, "sso_role_name", role_name)
    return profile


# -----------------------------------------------------------------------------
# Legacy Shims (SSO Token & Listing)
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
    """Minimal reader for AWS SSO cached token."""
    if not SSO_CACHE_DIR.exists():
        return None

    for p in SSO_CACHE_DIR.glob("*.json"):
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        # Catch specific file/parsing errors
        except (json.JSONDecodeError, UnicodeDecodeError, FileNotFoundError):
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
    start_url: str,  # noqa: ARG001
    region: str,
    profile: Union[str, None] = None,
) -> list[Dict[str, Any]]:
    """Legacy helper: list accounts via CLI."""
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
    """Legacy helper: list roles via CLI."""
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
    return [
        r.get("roleName", "") for r in data.get("roleList", []) if r.get("roleName")
    ]
