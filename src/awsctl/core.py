import os
from typing import List

from . import aws, config, context_manager, utils
from .sso_cache import load_active_sso_token

# Re-exports: Contract defined by tests patching these names in core.py.
load_active_sso_token = load_active_sso_token
load_orgs_config = config.load_raw_config
get_org = config.get_org
get_orgs_path = config.get_orgs_path
AWS_DIR = aws.AWS_DIR
SSO_CACHE_DIR = aws.SSO_CACHE_DIR


def cmd_login(org_name: str, force: bool = False) -> int:
    org = config.get_org(org_name)
    if not force and load_active_sso_token(org):
        utils.console.print("Already authenticated.")
        return 0
    try:
        aws.ensure_sso_base_profile(org)
        utils.run(["aws", "sso", "login", "--sso-session", org_name])
        return 0
    except Exception as e:
        utils.console.print(f"Login failed: {e}")
        return 1


def cmd_logout_str() -> str:
    utils.run(["aws", "sso", "logout"], check=False)
    context_manager.clear_context()
    vars_list = [
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_PROFILE",
    ]
    return "\n".join([f"unset {v};" for v in vars_list])


def cmd_config_sync() -> int:
    cfg = config.load_orgs_config()
    for org in cfg.get("orgs", []):
        if org.get("sso_start_url") and org.get("sso_region"):
            aws.ensure_sso_base_profile(org)
    return 0


def cmd_exec(account: str, role: str, region: str, command: List[str]) -> int:
    from .use_exports import get_credentials

    try:
        creds = get_credentials(account, role, region)
        env = os.environ.copy()
        env.update(creds)
        import subprocess

        res = subprocess.run(command, env=env)
        return res.returncode
    except SystemExit as e:
        if "ExpiredToken" in str(e):
            utils.console.print("Session expired.")
        return 1
    except Exception as e:
        utils.console.print(f"Execution failure: {e}")
        return 1


def cmd_setup() -> int:
    from .wizard import run_wizard

    return 0 if run_wizard() else 1
