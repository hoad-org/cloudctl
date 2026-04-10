import os
from typing import List

from . import aws, config, context_manager, utils
from .sso_cache import load_active_sso_token

# Re-exports: Contract defined by tests patching these names in core.py.
load_active_sso_token = load_active_sso_token
get_org = config.get_org
get_orgs_path = config.get_orgs_path


def load_orgs_config():
    """
    Load orgs config — patchable at awsctl.core.load_orgs_config.

    Calls config.load_orgs_config dynamically so that patches on
    awsctl.config.load_orgs_config are also respected.
    """
    return config.load_orgs_config()


AWS_DIR = aws.AWS_DIR
SSO_CACHE_DIR = aws.SSO_CACHE_DIR

# Patchable console reference (tests do monkeypatch.setattr(core, "console", mock))
console = utils.console


def cmd_login(org_name: str, force: bool = False) -> int:
    org = config.get_org(org_name)

    from .providers import get_provider

    provider = get_provider(org)

    if not force and org.get("provider", "aws") == "aws":
        token = load_active_sso_token(org)
        if token:
            # Show token expiry info for transparency
            try:
                expiry = getattr(token, "expiresAt", None) or (
                    token.get("expiresAt") if isinstance(token, dict) else None
                )
                if expiry:
                    utils.console.print(
                        f"[green]Already authenticated.[/] Session expires: {expiry}"
                    )
                else:
                    utils.console.print("[green]Already authenticated.[/]")
            except Exception:
                utils.console.print("[green]Already authenticated.[/]")
            return 0

    rc = provider.login(org)
    if rc == 0:
        utils.console.print("[green]Login Successful.[/]")
    return rc


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
    cfg = load_orgs_config()
    # cfg may be a dict (from load_raw_config) or a list (from load_orgs_config)
    if isinstance(cfg, dict):
        orgs = cfg.get("orgs", [])
    elif isinstance(cfg, list):
        orgs = cfg
    else:
        orgs = []
    for org in orgs:
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

    # Resolve account/role/region from context if not provided.
    _account = account or (ctx.get("account") if ctx else None)
    _role = role or (ctx.get("role") if ctx else None)
    _region = region or (ctx.get("region") if ctx else None) or ""

    from . import use_exports as _ue

    # When explicit account/role/region are given, use get_credentials directly
    # so tests can patch _aws_json without going through emit_exports' token check.
    if account is not None and role is not None:
        try:
            creds = _ue.get_credentials(_account, _role, _region)
            env = os.environ.copy()
            env.update(creds)
            try:
                os.execvpe(command[0], command, env)
            except FileNotFoundError:
                utils.console.print("Command not found")
                return 127
        except RuntimeError:
            utils.console.print("Failed to get credentials")
            return 1
        except SystemExit as e:
            if "ExpiredToken" in str(e):
                utils.console.print("Session expired.")
            else:
                utils.console.print("Failed to get credentials")
            return 1
        except Exception as e:
            utils.console.print(f"Execution failure: {e}")
            return 1
    else:
        # No explicit args — use emit_exports which checks the SSO token.
        try:
            export_str = _ue.emit_exports(org, _account, _role, _region)
            env = os.environ.copy()
            for line in (export_str or "").split("\n"):
                line = line.strip()
                if line.startswith("export "):
                    kv = line[7:]
                    if "=" in kv:
                        k, v = kv.split("=", 1)
                        env[k] = v
            try:
                os.execvpe(command[0], command, env)
            except FileNotFoundError:
                utils.console.print("Command not found")
                return 127
        except SystemExit as e:
            if "ExpiredToken" in str(e):
                utils.console.print("Session expired.")
            else:
                utils.console.print("Failed to get credentials")
            return 1
        except Exception as e:
            utils.console.print(f"Execution failure: {e}")
            return 1

    return 0


def cmd_cache_clear() -> None:
    """Clear the AWS CLI credential cache and SSO token cache."""
    # Clear the AWS CLI role-credentials cache
    cli_cache_dir = AWS_DIR / "cli" / "cache"
    if cli_cache_dir.exists():
        for f in cli_cache_dir.iterdir():
            if f.exists() and f.is_file():
                try:
                    f.unlink()
                except Exception as e:
                    utils.console.print(f"Failed to remove {f}: {e}")

    # Clear the SSO token cache (use aws.SSO_CACHE_DIR dynamically for patchability)
    sso_cache_dir = aws.SSO_CACHE_DIR
    if sso_cache_dir.exists():
        for f in sso_cache_dir.iterdir():
            if f.is_file():
                try:
                    f.unlink()
                except OSError as e:
                    utils.debug_print(f"Failed to remove {f}: {e}")

    utils.console.print("Cache cleared")


def cmd_logout() -> None:
    """
    Perform logout: clear SSO session and context.
    Errors during context cleanup are logged via debug_print.
    """
    try:
        context_manager.save_context_update(
            current_org=None, account=None, role=None, region=None
        )
    except Exception as e:
        utils.debug_print(f"Context cleanup error during logout: {e}")
    try:
        context_manager.clear_context()
    except Exception as e:
        utils.debug_print(f"Clear context error during logout: {e}")


def cmd_env() -> str:
    """Return export lines for the active context, or a message if no context."""
    ctx = context_manager.load_context()
    if not ctx:
        return "No active context. Run 'awsctl switch' first."
    lines = [f"export {k.upper()}={v}" for k, v in ctx.items() if v]
    return "\n".join(lines)


def cmd_setup() -> int:
    """Merge sample defaults into orgs.yaml without overwriting existing keys."""
    import yaml as _yaml

    # Use config.get_orgs_path directly so monkeypatch in tests takes effect
    orgs_path = config.get_orgs_path(ensure=True)
    current: dict = {}
    if orgs_path.exists():
        try:
            current = _yaml.safe_load(orgs_path.read_text(encoding="utf-8")) or {}
        except Exception:
            current = {}
    defaults = _yaml.safe_load(config.sample_orgs_yaml()) or {}
    # Merge: defaults first, then current overwrites (preserves custom keys)
    merged = {**defaults, **current}
    orgs_path.write_text(_yaml.dump(merged), encoding="utf-8")
    return 0
