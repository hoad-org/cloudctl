# file: src/awsctl/core.py
# SPDX-License-Identifier: MIT
"""
awsctl.core — Orchestrator module.
"""

from __future__ import annotations

import os
import pathlib as pathlib  # noqa: F401
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Union

import yaml
from rich.panel import Panel

from awsctl import aws, config, doctor, plugins, shell
from awsctl.sso_cache import OrgRef, load_active_sso_token
from awsctl.use_exports import emit_unset
from awsctl.utils import console, debug_print

# Re-exports
HOME = config.HOME
ORGS_USER = config.ORGS_USER
AWS_DIR = aws.AWS_DIR
AWS_CONFIG = aws.AWS_CONFIG
SSO_CACHE_DIR = aws.SSO_CACHE_DIR

get_orgs_path = config.get_orgs_path
sample_orgs_yaml = config.sample_orgs_yaml
load_orgs_config = config.load_orgs_config
load_user_config = config.load_user_config
get_org = config.get_org

run_aws = aws.run_aws
ensure_sso_base_profile = aws.ensure_sso_base_profile
aws_configure_set = aws.aws_configure_set
get_valid_sso_access_token = aws.get_valid_sso_access_token
sso_list_accounts = aws.sso_list_accounts
sso_list_account_roles = aws.sso_list_account_roles


def cmd_login(org: Union[str, None], force: bool = False) -> int:
    try:
        o: Dict[str, Any] = config.get_org(org)
    except (SystemExit, ValueError) as e:
        console.print(f"[error]{e}[/]")
        return 1

    cfg = config.load_orgs_config()
    registry_plugins = o.get("plugins", [])
    user_plugins = cfg.get("plugins", {}).get("enabled", [])
    all_plugins = list(dict.fromkeys(registry_plugins + user_plugins))

    if all_plugins:
        with console.status("[bold blue]Running security plugins...[/]"):
            mods = plugins.load_plugins(all_plugins)
            plugins.call_hook(mods, "pre_login", org=o)

    ref = OrgRef(o["name"], o["sso_start_url"], o["sso_region"])

    if not force:
        existing_token = load_active_sso_token(ref, raise_error=False)
        if existing_token:
            expiry_str = existing_token.expires_at.strftime("%H:%M UTC")
            console.print(
                Panel(
                    f"[bold green]✔ Already logged in[/]\n\n" f"Organization: [bold white]{o['name']}[/]\n" f"Valid until:  [dim]{expiry_str}[/]",
                    title="SSO Session Valid",
                    border_style="green",
                    expand=False,
                )
            )
            return 0

    profile = aws.ensure_sso_base_profile(o)

    console.print(
        Panel(
            f"authenticating to [bold cyan]{o['name']}[/]\n" f"URL: [underline]{o['sso_start_url']}[/]",
            title="AWS SSO Login",
            border_style="blue",
        )
    )

    from awsctl.utils import run

    try:
        run(
            ["aws", "sso", "login", "--profile", profile],
            timeout=None,
            capture=False,
            check=True,
        )
    except Exception as e:
        console.print(f"[error]Login failed: {e}[/]")
        return 1

    if not load_active_sso_token(ref, raise_error=False):
        console.print("[error]Login reported success but no token found in cache.[/]")
        return 1

    console.print(
        Panel(
            "[bold green]✔ Login Successful[/]\n\n" "You can now run:\n" "  [bold white on black] awsctl switch [/]",
            title="Ready",
            border_style="green",
            expand=False,
        )
    )
    return 0


def cmd_logout() -> int:
    from .context_manager import save_context_update

    with console.status("[bold red]Clearing SSO sessions...[/]"):
        try:
            subprocess.run(["aws", "sso", "logout"], check=False)
        except Exception as e:
            debug_print(f"Logout subprocess error: {e}")

        if SSO_CACHE_DIR.exists():
            for f in SSO_CACHE_DIR.glob("*.json"):
                try:
                    f.unlink()
                except OSError:
                    pass

        try:
            save_context_update(account="", role="", region="")
        except Exception as e:
            debug_print(f"Failed to clear context on logout: {e}")

    return 0


def cmd_logout_str() -> str:
    cmd_logout()
    return str(emit_unset())


def cmd_cache_clear() -> int:
    cache_dir = AWS_DIR / "cli" / "cache"

    # [FIX] Mypy: Add type annotations to inner function
    def on_rm_error(func: Any, path: str, exc_info: Any) -> None:
        debug_print(f"Ignored error clearing {path}: {exc_info[1]}")

    if cache_dir.exists():
        with console.status("[bold yellow]Flushing AWS CLI cache...[/]"):
            try:
                items = list(cache_dir.iterdir())
            except FileNotFoundError:
                items = []

            for item in items:
                try:
                    if not item.exists():
                        continue
                    if item.is_symlink():
                        item.unlink()
                        continue

                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item, onerror=on_rm_error)
                except Exception as e:
                    debug_print(f"Failed to remove {item}: {e}")

    console.print("[success]✔ Cache cleared.[/]")
    return 0


def cmd_exec(account: str, role: str, region: str, command: List[str]) -> int:
    from .context_manager import load_context
    from .use_exports import _aws_json

    ctx = load_context()

    target_account = str(account or ctx.get("account") or "")
    target_role = str(role or ctx.get("role") or "")
    target_region = str(region or ctx.get("region") or "")
    org_name = ctx.get("current_org")

    if not org_name:
        console.print("[error]No active org. Run `awsctl login` first.[/]")
        return 1

    try:
        org_conf = config.get_org(org_name)
        ref = OrgRef(org_conf["name"], org_conf["sso_start_url"], org_conf["sso_region"])

        tok = load_active_sso_token(ref)

        # [FIX] PYBH-0029: Catch potential token expiry race condition here
        # _aws_json may raise SystemExit if the AWS CLI call fails (e.g. ExpiredToken)
        try:
            data = _aws_json(
                [
                    "aws",
                    "sso",
                    "get-role-credentials",
                    "--region",
                    tok.region,
                    "--access-token",
                    tok.access_token,
                    "--account-id",
                    target_account,
                    "--role-name",
                    target_role,
                ]
            )
        except SystemExit as e:
            err_msg = str(e)
            if "UnauthorizedException" in err_msg or "ExpiredToken" in err_msg:
                console.print("\n[bold red]Session expired.[/] The token expired while processing.")
                console.print("Please run [bold white]awsctl login[/] to refresh.")
                return 1
            # Re-raise other errors
            raise

        creds = data.get("roleCredentials") or {}

        if not creds:
            console.print("[error]Failed to get credentials.[/]")
            return 1

        env = os.environ.copy()
        env["AWS_ACCESS_KEY_ID"] = creds["accessKeyId"]
        env["AWS_SECRET_ACCESS_KEY"] = creds["secretAccessKey"]
        env["AWS_SESSION_TOKEN"] = creds["sessionToken"]

        if target_region:
            env["AWS_REGION"] = target_region
            env["AWS_DEFAULT_REGION"] = target_region

        keys_to_unset = [
            "AWS_SECURITY_TOKEN",
            # [FIX] PYBH-0070: Allow users to override AWS_CONFIG_FILE in child proc
            # "AWS_CONFIG_FILE",
            "AWS_SHARED_CREDENTIALS_FILE",
            "AWS_WEB_IDENTITY_TOKEN_FILE",
            "AWS_ROLE_ARN",
            "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
            "AWS_CONTAINER_CREDENTIALS_FULL_URI",
            "AWS_EC2_METADATA_DISABLED",
            # [FIX] PYBH-0040: Prevent AWS_PROFILE from polluting exec context
            "AWS_PROFILE",
        ]

        for k in keys_to_unset:
            env.pop(k, None)

        debug_print(f"Context: {target_account} / {target_role} / {target_region}")

        try:
            sys.stdout.flush()
            sys.stderr.flush()
            # [FIX] Bandit B606: nosec must be on the line of the call
            os.execvpe(command[0], command, env)  # nosec B606
        except FileNotFoundError:
            console.print(f"[error]Command not found: {command[0]}[/]")
            return 127
        except PermissionError:
            console.print(f"[error]Permission denied: {command[0]}[/]")
            return 126

    except Exception as e:
        console.print(f"[error]Exec failed: {e}[/]")
        return 1


def cmd_env(safe_output: bool = True) -> str:
    from .context_manager import load_context

    ctx = load_context()
    if not all(k in ctx for k in ("current_org", "account", "role", "region")):
        return "# No active context"

    try:
        org_conf = config.get_org(ctx["current_org"])
        ref = OrgRef(org_conf["name"], org_conf["sso_start_url"], org_conf["sso_region"])
        from .use_exports import emit_exports

        return emit_exports(
            ref,
            str(ctx["account"]),
            str(ctx["role"]),
            str(ctx["region"]),
            safe_output=safe_output,
        )
    except Exception as e:
        return f"# Error generating env: {e}"


def cmd_config_sync() -> int:
    with console.status("[bold green]Synchronizing AWS Profiles...[/]"):
        data = config.load_orgs_config()
        orgs = data.get("orgs", [])
        for o in orgs:
            if {"name", "sso_start_url", "sso_region"} <= set(o):
                aws.ensure_sso_base_profile(o)

    console.print(f"[success]✔ Synchronized {len(orgs)} org(s) into {aws.AWS_CONFIG}[/]")
    return 0


def cmd_setup() -> int:
    p = config.get_orgs_path(ensure=True)

    present: Dict[str, Any] = {}
    if p.exists():
        try:
            present = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] Existing config at {p} is invalid: {e}")
            console.print("Please fix or remove the file manually.")
            return 1

    needs_defaults = not p.exists() or not present.get("enabled_orgs")

    if needs_defaults:
        try:
            defaults = yaml.safe_load(config.sample_orgs_yaml())
            present["enabled_orgs"] = defaults["enabled_orgs"]
            if "plugins" not in present:
                present["plugins"] = {"enabled": []}

            fd, tmp_path = tempfile.mkstemp(dir=p.parent, text=True)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    yaml.dump(present, f, default_flow_style=False)
                os.chmod(tmp_path, 0o600)
                shutil.move(tmp_path, p)
            except Exception:
                os.remove(tmp_path)
                raise

        except Exception as e:
            console.print(f"[error]Failed to merge defaults: {e}[/]")
            return 1

    cmd_config_sync()

    rc_file = shell.detect_shell_profile()
    try:
        if shell.inject_shell_function(rc_file):
            console.print(f"[success]✅ Shell wrapper appended to {rc_file}[/]")
        else:
            console.print(f"✓ Shell wrapper already present in {rc_file}")
    except Exception as e:
        console.print(f"[warning]Could not inject shell wrapper: {e}[/]")

    return 0


def cmd_doctor(args: Union[object, None]) -> int:
    return int(doctor.run_diagnostics(getattr(args, "fix_path", False)))
