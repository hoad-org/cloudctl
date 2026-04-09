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

    # For AWS, skip if a valid token already exists (unless --force).
    # For Azure/GCP, always call the provider — they handle re-auth gracefully.
    from .providers import get_provider

    provider = get_provider(org)

    if not force and org.get("provider", "aws") == "aws":
        if load_active_sso_token(org):
            utils.console.print("Already authenticated.")
            return 0

    return provider.login(org)


def cmd_logout_str() -> str:
    """
    Return shell lines to unset credentials for the current session's provider.

    Falls back to AWS unset lines when no context is active so existing
    behaviour is preserved.
    """
    ctx = context_manager.load_context()
    provider_name = ctx.get("provider", "aws") if ctx else "aws"

    try:
        org_name = ctx.get("current_org") or ctx.get("org", "") if ctx else ""
        org = config.get_org(org_name) if org_name else {"provider": provider_name}
    except Exception:
        org = {"provider": provider_name}

    from .providers import get_provider

    provider = get_provider(org)

    try:
        provider.logout(org)
    except Exception:
        pass

    context_manager.clear_context()
    return provider.get_unsets()


def cmd_config_sync() -> int:
    cfg = config.load_orgs_config()
    for org in cfg.get("orgs", []):
        if org.get("provider", "aws") == "aws":
            if org.get("sso_start_url") and org.get("sso_region"):
                aws.ensure_sso_base_profile(org)
    return 0


def cmd_exec(account: str, role: str, region: str, command: List[str]) -> int:
    ctx = context_manager.load_context()
    org_name = ctx.get("current_org", "") if ctx else ""

    try:
        org = config.get_org(org_name) if org_name else {"provider": "aws"}
    except Exception:
        org = {"provider": "aws"}

    from .providers import get_provider

    provider = get_provider(org)

    try:
        creds = provider.get_credentials(org, account, role, region)
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
