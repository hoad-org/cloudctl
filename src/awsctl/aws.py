# file: src/awsctl/aws.py
# SPDX-License-Identifier: MIT
from __future__ import annotations

import configparser
import contextlib
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Generator, Optional, Union

from awsctl.sso_cache import _normalize_start_url
from awsctl.utils import run

# Paths
HOME = Path.home()
AWS_DIR = HOME / ".aws"
SSO_CACHE_DIR = AWS_DIR / "sso" / "cache"

if os.environ.get("AWS_CONFIG_FILE"):
    AWS_CONFIG = Path(os.environ["AWS_CONFIG_FILE"])
else:
    AWS_CONFIG = AWS_DIR / "config"


def _resolve_aws_cli() -> str:
    """
    Resolve the full path to the AWS CLI binary.
    Required for Windows where subprocess.Popen(shell=False) does not
    automatically resolve .bat/.cmd extensions.
    """
    path = shutil.which("aws")
    return path if path else "aws"


@contextlib.contextmanager
def _config_file_lock(timeout: float = 5.0) -> Generator[None, None, None]:
    """
    Cross-platform spinlock using atomic file creation.
    """
    lock_path = AWS_CONFIG.with_suffix(".lock")
    start = time.time()
    locked = False

    if not AWS_CONFIG.parent.exists():
        AWS_CONFIG.parent.mkdir(parents=True, exist_ok=True)

    while (time.time() - start) < timeout:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
            os.close(fd)
            locked = True
            break
        except FileExistsError:
            try:
                if lock_path.stat().st_mtime < (time.time() - 30):
                    try:
                        os.remove(lock_path)
                        continue
                    except OSError:
                        pass
            except OSError:
                pass
            time.sleep(0.1)
        except OSError:
            time.sleep(0.1)

    if not locked:
        raise TimeoutError(f"Could not acquire lock on {AWS_CONFIG} after {timeout}s")

    try:
        yield
    finally:
        if locked:
            try:
                os.remove(lock_path)
            except OSError:
                pass


def _clean_env() -> Dict[str, str]:
    """
    🛡️ SECURITY: Return environment free of AWS identity variables.
    """
    env = os.environ.copy()
    keys = [
        "AWS_PROFILE",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_REGION",
        "AWS_DEFAULT_REGION",
        "AWS_SHARED_CREDENTIALS_FILE",
        "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
        "AWS_CONTAINER_CREDENTIALS_FULL_URI",
        "AWS_EC2_METADATA_DISABLED",
        "AWS_WEB_IDENTITY_TOKEN_FILE",
        "AWS_ROLE_ARN",
    ]
    for k in keys:
        env.pop(k, None)
    return env


def run_aws(
    args: list[str], timeout: Optional[float] = 60.0
) -> subprocess.CompletedProcess[str]:
    return run(args, check=False, timeout=timeout, env=_clean_env())


def _ensure_aws_config_file() -> None:
    try:
        AWS_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        if not AWS_CONFIG.exists():
            AWS_CONFIG.touch()
    except OSError:
        pass


def _check_unsafe_config() -> None:
    if not AWS_CONFIG.exists():
        return
    try:
        raw = AWS_CONFIG.read_text(encoding="utf-8")
        if re.search(r"^(?![ \t]*[#;])\s*include\s*=", raw, re.MULTILINE):
            raise RuntimeError(
                "Fatal: ~/.aws/config contains 'include' directives.\n"
                "awsctl cannot modify this file safely without causing corruption."
            )
    except OSError:
        pass


def _configparser_read() -> configparser.RawConfigParser:
    _ensure_aws_config_file()
    cfg = configparser.RawConfigParser()
    cfg.read(AWS_CONFIG)
    return cfg


def _configparser_write(cfg: configparser.RawConfigParser) -> None:
    if AWS_CONFIG.exists():
        backup = AWS_CONFIG.with_suffix(".config.bak")
        try:
            shutil.copy2(AWS_CONFIG, backup)
        except OSError:
            pass

    target_dir = AWS_CONFIG.parent
    fd, tmp_path = tempfile.mkstemp(dir=target_dir, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            cfg.write(f)

        dest_path = AWS_CONFIG
        if dest_path.is_symlink():
            dest_path = dest_path.resolve()

        shutil.move(tmp_path, dest_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def aws_configure_set(profile: str, key: str, value: str) -> None:
    if "\n" in value or "\r" in value:
        raise ValueError("Configuration values cannot contain newlines.")

    with _config_file_lock():
        _check_unsafe_config()
        cfg = _configparser_read()
        sect = f"profile {profile}"
        if not cfg.has_section(sect):
            cfg.add_section(sect)
        cfg.set(sect, key, value)
        _configparser_write(cfg)


def _set_section(
    cfg: configparser.RawConfigParser, section: str, pairs: Dict[str, str]
) -> None:
    if not cfg.has_section(section):
        cfg.add_section(section)
    for k, v in pairs.items():
        if "\n" in v or "\r" in v:
            raise ValueError(f"Invalid config value for {k}: {v}")
        cfg.set(section, k, v)


def ensure_sso_base_profile(org: Dict[str, Any]) -> str:
    with _config_file_lock():
        _check_unsafe_config()

        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", org["name"])
        org_hash = hashlib.sha256(org["name"].encode()).hexdigest()[:6]

        profile = f"sso-{safe_name}-{org_hash}"
        region = org.get("default_region") or "eu-west-2"

        cfg = _configparser_read()
        _set_section(
            cfg,
            f"profile {profile}",
            {
                "sso_session": safe_name,
                "sso_start_url": org["sso_start_url"],
                "sso_region": org["sso_region"],
                "region": region,
            },
        )
        _set_section(
            cfg,
            f"sso-session {safe_name}",
            {
                "sso_start_url": org["sso_start_url"],
                "sso_region": org["sso_region"],
                "sso_registration_scopes": "sso:account:access",
            },
        )
        _configparser_write(cfg)
        return profile


def write_target_profile(
    org: Dict[str, Any], account_id: str, role_name: str, region: str
) -> str:
    with _config_file_lock():
        pass

    base_profile = ensure_sso_base_profile(org)

    with _config_file_lock():
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", org["name"])
        sso_session_name = safe_name

        safe_role = re.sub(r"[^a-zA-Z0-9_-]", "-", role_name)
        role_hash = hashlib.sha256(role_name.encode()).hexdigest()[:6]

        target_profile = f"{base_profile}-{account_id}-{safe_role}-{role_hash}-{region}"

        _check_unsafe_config()
        cfg = _configparser_read()

        _set_section(
            cfg,
            f"profile {target_profile}",
            {
                "sso_session": sso_session_name,
                "sso_account_id": account_id,
                "sso_role_name": role_name,
                "region": region,
            },
        )
        _configparser_write(cfg)
        return target_profile


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
    if not SSO_CACHE_DIR.exists():
        return None

    want_url = _normalize_start_url(start_url)

    for p in SSO_CACHE_DIR.glob("*.json"):
        try:
            if p.stat().st_size > 1024 * 1024:
                continue
            doc = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, FileNotFoundError, OSError):
            continue

        cached_url = _normalize_start_url(str(doc.get("startUrl", "")))
        if cached_url != want_url:
            continue

        if doc.get("region") not in (sso_region, None):
            continue

        exp_raw = doc.get("expiresAt", "")
        if not isinstance(exp_raw, str):
            continue

        exp = _parse_iso8601(exp_raw)
        if not exp or exp <= (_now_utc() + timedelta(seconds=15)):
            continue

        tok = doc.get("accessToken")
        if isinstance(tok, str) and tok:
            return tok

    return None


def sso_list_accounts(
    start_url: str,
    region: str,
    profile: Union[str, None] = None,
    access_token: Union[str, None] = None,
) -> list[Dict[str, Any]]:
    results: list[Dict[str, Any]] = []
    next_token = None
    page_count = 0

    # [FIX] Resolve binary for Windows compatibility
    aws_bin = _resolve_aws_cli()

    while True:
        if page_count > 100:
            raise RuntimeError("AWS SSO pagination limit exceeded.")
        page_count += 1

        args = [aws_bin, "sso", "list-accounts", "--output", "json", "--region", region]
        if profile:
            args += ["--profile", profile]
        if access_token:
            args += ["--access-token", access_token]
        if next_token:
            args += ["--next-token", next_token]

        proc = run_aws(args)

        if proc.returncode != 0:
            raise RuntimeError(f"Failed to list accounts: {proc.stderr}")

        try:
            data = json.loads(proc.stdout)
            page = data.get("accountList", []) or []
            results.extend(page)
            next_token = data.get("nextToken")
            if not next_token:
                break
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON from AWS CLI: {proc.stdout}") from e

    return results


def sso_list_account_roles(
    start_url: str,
    account_id: str,
    region: str,
    profile: Union[str, None] = None,
    access_token: Union[str, None] = None,
) -> list[str]:
    results = []
    next_token = None
    page_count = 0

    # [FIX] Resolve binary for Windows compatibility
    aws_bin = _resolve_aws_cli()

    while True:
        if page_count > 100:
            raise RuntimeError("AWS SSO pagination limit exceeded.")
        page_count += 1

        args = [
            aws_bin,
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
        if access_token:
            args += ["--access-token", access_token]
        if next_token:
            args += ["--next-token", next_token]

        proc = run_aws(args)
        if proc.returncode != 0:
            raise RuntimeError(f"Failed to list roles: {proc.stderr}")

        try:
            data = json.loads(proc.stdout)
            page = [
                r.get("roleName", "")
                for r in data.get("roleList", [])
                if r.get("roleName")
            ]
            results.extend(page)
            next_token = data.get("nextToken")
            if not next_token:
                break
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON from AWS CLI: {proc.stdout}") from e

    return results
