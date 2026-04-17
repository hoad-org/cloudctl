import configparser
import contextlib
import json
import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from .utils import run

AWS_DIR = Path.home() / ".aws"
AWS_CONFIG = AWS_DIR / "config"
SSO_CACHE_DIR = AWS_DIR / "sso" / "cache"


def _resolve_aws_cli() -> str:
    """Return the path to the aws CLI binary, raising if not found."""
    path = shutil.which("aws")
    if not path:
        raise RuntimeError("AWS CLI not found in PATH")
    return path


def run_aws(args: List[str]) -> Dict[str, Any]:
    return run(["aws"] + args, check=False)


def get_clean_env() -> Dict[str, str]:
    env = os.environ.copy()
    keys = [
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_SECURITY_TOKEN",
    ]
    for k in keys:
        env.pop(k, None)
    return env


def _parse_iso8601(ts: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _configparser_write(config: configparser.RawConfigParser, path: Path) -> None:
    temp = path.with_suffix(".tmp")
    try:
        if path.exists():
            shutil.copy2(path, path.with_suffix(".bak"))
    except OSError:
        pass
    with open(temp, "w", encoding="utf-8") as f:
        config.write(f)
    os.replace(temp, path)


def _set_section(
    config: configparser.RawConfigParser, section: str, data: Dict[str, str]
) -> None:
    if section not in config:
        config.add_section(section)
    for k, v in data.items():
        if "\n" in str(v):
            raise ValueError("Injection detected")
        config.set(section, k, str(v))


@contextlib.contextmanager
def _config_file_lock(timeout: float = 10.0) -> Generator[None, None, None]:
    lock_path = AWS_CONFIG.with_suffix(".lock")
    if lock_path.exists():
        if time.time() - lock_path.stat().st_mtime > 3600:
            lock_path.unlink(missing_ok=True)

    start = time.time()
    while lock_path.exists():
        if time.time() - start > timeout:
            import builtins

            raise builtins.TimeoutError("Lock timeout")
        time.sleep(0.1)

    lock_path.touch()
    try:
        yield
    finally:
        if lock_path.exists():
            lock_path.unlink()


def _check_unsafe_config(path: Optional[Path] = None) -> None:
    p = path or AWS_CONFIG
    if p.exists():
        if "include" in p.read_text(encoding="utf-8").lower():
            raise RuntimeError("contains 'include' directives")


def sso_list_accounts(token: Any) -> List[Dict[str, str]]:
    tk = token.accessToken if hasattr(token, "accessToken") else token
    region = token.region if hasattr(token, "region") else "us-east-1"
    accounts = []
    next_token = None
    while True:
        args = ["sso", "list-accounts", "--access-token", tk, "--region", region]
        if next_token:
            args.extend(["--next-token", next_token])
        res = run_aws(args)
        if res.get("returncode") != 0:
            raise RuntimeError(f"AWS Error: {res.get('stderr')}")
        data = json.loads(res.get("stdout", "{}"))
        accounts.extend(data.get("accountList", []))
        next_token = data.get("nextToken")
        if not next_token:
            break
    return accounts


def sso_list_account_roles(token: Any, account_id: str) -> List[Dict[str, str]]:
    tk = token.accessToken if hasattr(token, "accessToken") else token
    region = token.region if hasattr(token, "region") else "us-east-1"
    roles = []
    next_token = None
    while True:
        args = [
            "sso",
            "list-account-roles",
            "--access-token",
            tk,
            "--account-id",
            account_id,
            "--region",
            region,
        ]
        if next_token:
            args.extend(["--next-token", next_token])
        res = run_aws(args)
        if res.get("returncode") != 0:
            raise RuntimeError(f"AWS Error: {res.get('stderr')}")
        data = json.loads(res.get("stdout", "{}"))
        roles.extend(data.get("roleList", []))
        next_token = data.get("nextToken")
        if not next_token:
            break
    return roles


def ensure_sso_base_profile(org: Dict[str, Any]) -> str:
    name = org.get("name", "base")
    with _config_file_lock():
        cfg = configparser.RawConfigParser()
        if AWS_CONFIG.exists():
            cfg.read(AWS_CONFIG)
        section = f"sso-session {name}"
        _set_section(
            cfg,
            section,
            {
                "sso_start_url": org.get("sso_start_url", ""),
                "sso_region": org.get("sso_region", ""),
            },
        )
        _configparser_write(cfg, AWS_CONFIG)
    return name


def write_target_profile(
    org_data: Dict[str, Any], account: str, role: str, region: str
) -> str:
    name = f"{org_data.get('name')}-{account}-{role}"
    with _config_file_lock():
        cfg = configparser.RawConfigParser()
        if AWS_CONFIG.exists():
            cfg.read(AWS_CONFIG)
        section = f"profile {name}"
        _set_section(
            cfg,
            section,
            {"sso_account_id": account, "sso_role_name": role, "region": region},
        )
        _configparser_write(cfg, AWS_CONFIG)
    return name
