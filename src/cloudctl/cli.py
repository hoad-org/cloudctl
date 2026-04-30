"""
cloudctl.cli — main entry point and command dispatcher.

The real binary installed by Poetry is 'cloudctl' → cloudctl.cli:main.

Shell wrapper contract
----------------------
The bash/zsh/fish wrapper calls:
    command cloudctl --eval <subcommand> [args] > $tmp
    source $tmp

For env-mutating commands (switch, logout, login --account/--role/--region)
the binary must emit 'export K=V' / 'unset K' lines to stdout.
All user-facing output goes to stderr (BaseCommand.console is stderr=True).

The --check-strategy flag lets the shell wrapper ask "does this command
need EVAL?" before it decides whether to capture or stream stdout.
"""

import importlib.metadata
import os
import sys
from pathlib import Path
from typing import Any, List, Optional


from . import core, utils
from .use_exports import emit_exports  # noqa: F401 — re-exported for monkeypatch seam

# Patchable console references (tests monkeypatch these)
console = utils.console
stdout_console = utils.stdout_console

CONTEXT_FILE = Path.home() / ".cloudctl" / "context.json"


def load_context():
    """
    Load context from CONTEXT_FILE with debug logging on error.
    This wrapper uses the module-level CONTEXT_FILE so tests can patch it.
    """
    import json

    if not CONTEXT_FILE.exists():
        return {}
    try:
        return json.loads(CONTEXT_FILE.read_text())
    except Exception as e:
        utils.debug_print(f"Failed to load context: {e}")
        return {}


# ---------------------------------------------------------------------------
# Version helpers
# ---------------------------------------------------------------------------


def _resolved_version() -> str:
    try:
        return importlib.metadata.version("cloudctl")
    except Exception:
        return "1.2.3"


# ---------------------------------------------------------------------------
# Routing strategy
# ---------------------------------------------------------------------------


def determine_strategy(argv: List[str]) -> str:
    """
    Return "EVAL" if the shell wrapper must capture stdout and source it,
    or "EXEC" if it should just stream stdout to the terminal.
    """
    if not argv:
        return "EXEC"
    eval_cmds = {"switch", "use", "logout"}
    if argv[0] in eval_cmds:
        return "EVAL"
    if argv[0] == "login" and any(
        x in argv for x in ["--account", "-a", "--role", "-r", "--region", "-R"]
    ):
        return "EVAL"
    return "EXEC"


# ---------------------------------------------------------------------------
# Org / account helpers (patchable by tests)
# ---------------------------------------------------------------------------


def _get_org_ref(org_name: str) -> Any:
    from .sso_cache import OrgRef
    from .config import get_org

    try:
        org = get_org(org_name)
        return OrgRef(
            org.get("name", ""),
            org.get("sso_start_url", ""),
            org.get("sso_region", ""),
        )
    except Exception:
        return None


def _resolve_account_id(org_ref: Any, target: Optional[str]) -> Optional[str]:
    if target:
        return target
    return None


# ---------------------------------------------------------------------------
# Command handlers (one per subcommand; each returns int exit code)
# ---------------------------------------------------------------------------


def cmd_login(args: Any) -> int:
    org_name = getattr(args, "org", None) or getattr(args, "org_flag", None)
    if not org_name:
        # Try to infer from context
        ctx = load_context()
        org_name = ctx.get("current_org") if ctx else None
    if not org_name:
        # Try from config if only one org is present
        cfg = core.load_orgs_config()
        orgs = cfg.get("orgs", []) if isinstance(cfg, dict) else cfg
        if len(orgs) == 1:
            org_name = orgs[0].get("name")
    if not org_name:
        console.print(
            "[red]No org specified. Use 'cloudctl login <org>' or configure a default.[/]\n"
            "Run [bold]cloudctl accounts[/bold] to determine which org to use."
        )
        return 1
    force = getattr(args, "force", False)
    try:
        rc = core.cmd_login(org_name, force=force)
    except (ValueError, Exception) as e:
        utils.console.print(f"[red]Error:[/] {e}")
        return 1

    # Bridge to switch when account+role+region are provided (eval mode)
    if rc == 0 and getattr(args, "account", None) and getattr(args, "role", None):
        try:
            org_ref = _get_org_ref(org_name)
            _resolve_account_id(org_ref, getattr(args, "account", None))
        except Exception:
            pass
        import cloudctl.cli as _self

        return _self.cmd_switch(args)

    return rc


def cmd_switch(args: Any) -> int:
    import cloudctl.interactive as _interactive
    import cloudctl.cli as _self  # for patchable emit_exports
    from .context_manager import save_context, get_previous_context
    from .config import get_org, load_config

    try:
        target = getattr(args, "target", None) or getattr(args, "org", None)

        # Handle previous context switch: "cloudctl switch -"
        if target == "-":
            prev = get_previous_context()
            if not prev:
                utils.console.print("No previous context available.")
                return 1
            org_name = prev.get("current_org") or prev.get("org")
            account = prev.get("account")
            role = prev.get("role")
            region = prev.get("region")
            if not all([org_name, account, role, region]):
                utils.console.print(
                    "[red]Previous context is incomplete (missing fields).[/]"
                )
                return 1
            try:
                org_data = get_org(org_name)
            except Exception:
                org_data = {"name": org_name, "provider": "aws"}
            export_str = _self.emit_exports(org_data, account, role, region)
            print(export_str)
            save_context(org_name, account, role, region)
            utils.console.print(
                f"[bold green]✔ Switched to {account} / {role} / {region}[/]"
            )
            return 0

        # Handle alias switch: "cloudctl switch @prod"
        if target and target.startswith("@"):
            alias_name = target[1:]
            cfg = core.load_orgs_config()
            if isinstance(cfg, dict):
                aliases = cfg.get("aliases", {})
            else:
                aliases = {}
            if alias_name not in aliases:
                utils.console.print(f"[red]Alias '@{alias_name}' not defined.[/]")
                return 1
            alias = aliases[alias_name]
            org_name = alias.get("org")
            account = alias.get("account")
            role = alias.get("role")
            region = alias.get("region")
            if not all([org_name, account, role, region]):
                utils.console.print(
                    f"[red]Alias '@{alias_name}' is missing required fields (org, account, role, region).[/]"
                )
                return 1
            try:
                org_data = get_org(org_name)
            except Exception:
                org_data = {"name": org_name, "provider": "aws"}
            export_str = _self.emit_exports(org_data, account, role, region)
            print(export_str)
            save_context(org_name, account, role, region)
            utils.console.print(
                f"[bold green]✔ Switched to {account} / {role} / {region}[/]"
            )
            return 0

        # Non-interactive / direct switch: explicit account+role+region provided
        account_arg = getattr(args, "account", None)
        role_arg = getattr(args, "role", None)
        region_arg = getattr(args, "region", None)
        org_name = getattr(args, "org", None)

        if not org_name:
            ctx = load_context()
            org_name = ctx.get("current_org") if ctx else None

        if account_arg and not role_arg:
            utils.console.print(
                "[red]--role is required when --account is specified.[/]"
            )
            return 1

        if org_name:
            try:
                org_data = get_org(org_name)
            except Exception:
                org_data = {"name": org_name, "provider": "aws"}
        else:
            cfg = load_config()
            orgs = [o["name"] for o in cfg.get("orgs", [])]
            if not orgs:
                utils.console.print(
                    "[red]No organizations configured.[/] Run [bold]cloudctl init[/bold] or [bold]cloudctl org add[/bold]."
                )
                return 1
            if len(orgs) == 1:
                org_name = orgs[0]
                try:
                    org_data = get_org(org_name)
                except Exception:
                    org_data = {"name": org_name, "provider": "aws"}
            else:
                try:
                    from InquirerPy import inquirer

                    org_name = inquirer.select(
                        message="Select Organization:", choices=orgs
                    ).execute()
                    try:
                        org_data = get_org(org_name)
                    except Exception:
                        org_data = {"name": org_name, "provider": "aws"}
                except KeyboardInterrupt:
                    raise

        # Guardrail: validate explicit region before proceeding.
        if region_arg:
            try:
                from .guardrails import validate_region

                validate_region(org_data, region_arg)
            except SystemExit:
                return 1

        account, role, region = _interactive.run_interactive_use(
            org_data,
            account_arg,
            role_arg,
            region_arg,
        )

        if not all([account, role, region]):
            return 1

        export_str = _self.emit_exports(org_data, account, role, region)
        print(export_str)
        save_context(org_name, account, role, region)
        utils.console.print(
            f"[bold green]✔ Switched to {account} / {role} / {region}[/]"
        )
        return 0
    except KeyboardInterrupt:
        utils.console.print("Operation cancelled")
        return 1
    except SystemExit:
        return 1
    except Exception as e:
        utils.console.print(f"Switch failed: {e}")
        return 1


def cmd_logout(args: Any) -> int:
    """Emits unset lines to stdout (captured by shell wrapper) then clears context."""
    output = core.cmd_logout_str()
    sys.stdout.write(output + "\n")
    return 0


def cmd_exec(args: Any) -> int:
    from .commands.exec import ExecCommand
    return ExecCommand().execute(args)


def cmd_status(args: Any) -> int:
    from .context_manager import print_status

    print_status()
    return 0


def cmd_accounts(args: Any) -> int:
    from .commands.accounts import AccountsCommand

    return AccountsCommand().execute(args)


def cmd_doctor(args: Any) -> int:
    from . import doctor

    return doctor.run_diagnostics(fix_path=getattr(args, "fix_path", False))


def cmd_init(args: Any) -> int:
    from .commands.init import InitCommand

    return InitCommand().execute(args)


def cmd_org(args: Any) -> int:
    from .commands.org import OrgAddCommand, OrgListCommand, OrgRemoveCommand

    sub = getattr(args, "org_command", None)
    if sub == "add":
        return OrgAddCommand().execute(args)
    elif sub == "list":
        return OrgListCommand().execute(args)
    elif sub == "remove":
        return OrgRemoveCommand().execute(args)
    else:
        console.print("Usage: cloudctl org <add|list|remove>")
        return 1


def cmd_gcp(args: Any) -> int:
    """Handle GCP-specific operations."""
    from .commands.gcp_iam import GcpIamCommand
    from .commands.gcp_login import GcpLoginCommand

    sub = getattr(args, "gcp_command", None)
    if sub == "login":
        cmd = GcpLoginCommand()
        cmd.set_args(args)
        return cmd.execute()
    elif sub == "grant-iam-roles":
        cmd = GcpIamCommand()
        cmd.set_args(args)
        return cmd.execute()
    else:
        console.print("Usage:")
        console.print("  cloudctl gcp login [--account EMAIL]")
        console.print("  cloudctl gcp grant-iam-roles <org-id> <member> <role1> [role2] ...")
        return 1


def cmd_whoami(args: Any = None) -> int:
    """Show the active identity for the current provider context.

    Falls back to AWS STS when no context exists (backward-compat with
    tests and scripts that call whoami without a prior switch).
    """
    ctx = load_context()
    provider = ctx.get("provider", "aws") if ctx else "aws"
    org_name = ctx.get("current_org", "") if ctx else ""
    account = ctx.get("account", "") if ctx else ""
    role = ctx.get("role", "") if ctx else ""
    region = ctx.get("region", "") if ctx else ""

    if provider == "aws":
        from . import aws

        try:
            result = aws.run_aws(["sts", "get-caller-identity"])
            if result.get("returncode") != 0:
                utils.console.print(
                    f"Failed to get identity: {result.get('stderr', '')}"
                )
                return 1
            utils.console.print(result.get("stdout", ""))
        except Exception as e:
            utils.console.print(str(e))
            return 1
    elif provider == "azure":
        utils.console.print(
            f"[bold]Azure[/bold]  org={org_name}  "
            f"subscription={account}  role={role}  region={region}"
        )
    elif provider == "gcp":
        utils.console.print(
            f"[bold]GCP[/bold]  org={org_name}  "
            f"project={account}  role={role}  region={region}"
        )
    else:
        utils.console.print(
            f"[bold]{provider}[/bold]  org={org_name}  "
            f"account={account}  role={role}  region={region}"
        )
    return 0


def cmd_open(args: Any = None) -> int:
    """Open the cloud console for the active org and provider."""
    try:
        ctx = load_context()
        org_name = ctx.get("current_org") if ctx else None
        if not org_name:
            utils.console.print("[red]Error: No active context.[/]")
            return 1
        org = core.get_org(org_name)  # propagates to outer except → returns 1
        provider = org.get("provider", "aws")
        if provider == "aws":
            from .schema import AWS_PARTITIONS

            partition = org.get("partition", "aws")
            console_url = AWS_PARTITIONS.get(partition, AWS_PARTITIONS["aws"])[
                "console"
            ]
        elif provider == "azure":
            console_url = "https://portal.azure.com/"
        elif provider == "gcp":
            project = (ctx.get("account") if ctx else None) or org.get(
                "default_project", ""
            )
            console_url = (
                f"https://console.cloud.google.com/home/dashboard?project={project}"
                if project
                else "https://console.cloud.google.com/"
            )
        else:
            console_url = "https://console.aws.amazon.com/"

        import webbrowser

        webbrowser.open(console_url)
        return 0
    except Exception as e:
        utils.console.print(f"[red]Error: {e}[/]")
        return 1


def _remove_cloudctl_blocks(lines: list, markers: list) -> list:
    """
    Remove cloudctl-injected blocks from a list of shell profile lines.

    Two block types are handled:

    1. Multi-line function block:
       # AWSCTL SHELL INTEGRATION
       cloudctl() {
           ...
       }        ← standalone '}' terminates the block

    2. Single-line command:
       # cloudctl completion
       eval "$(register-python-argcomplete cloudctl)"

    Uses an index-based pass so it can look ahead without fragile state machines.
    """
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if any(m in line for m in markers):
            # Marker line — skip it and determine block extent
            i += 1
            if i >= len(lines):
                break
            next_stripped = lines[i].rstrip("\n").strip()
            if next_stripped.startswith("cloudctl()") or next_stripped.startswith("function cloudctl"):
                # Multi-line function: skip until standalone closing brace
                while i < len(lines):
                    if lines[i].rstrip("\n").rstrip() == "}":
                        i += 1  # skip the closing brace too
                        break
                    i += 1
            elif next_stripped.startswith("eval") or next_stripped.startswith("register-python"):
                # Single-line command — skip just that one line
                i += 1
            # else: marker with no recognised follow-on — just removed the marker
        else:
            result.append(line)
            i += 1
    return result


def cmd_completion(args: Any = None) -> int:
    """Print shell completion activation instructions (or install them)."""
    import os

    shell = getattr(args, "shell", None)
    install = getattr(args, "install", False)

    # Auto-detect shell from $SHELL
    if not shell:
        shell_bin = os.environ.get("SHELL", "")
        if "zsh" in shell_bin:
            shell = "zsh"
        elif "fish" in shell_bin:
            shell = "fish"
        else:
            shell = "bash"

    snippets = {
        "bash": (
            'eval "$(register-python-argcomplete cloudctl)"',
            "~/.bashrc",
        ),
        "zsh": (
            'eval "$(register-python-argcomplete cloudctl)"',
            "~/.zshrc",
        ),
        "fish": (
            "register-python-argcomplete --shell fish cloudctl | source",
            "~/.config/fish/config.fish",
        ),
    }

    line, profile = snippets[shell]

    if install:
        profile_path = os.path.expanduser(profile)
        try:
            with open(profile_path, "r") as f:
                content = f.read()
        except FileNotFoundError:
            content = ""

        marker = "# cloudctl completion"
        if marker in content:
            console.print(f"[yellow]Completion already installed in {profile}[/]")
            return 0

        with open(profile_path, "a") as f:
            f.write(f"\n{marker}\n{line}\n")
        console.print(f"[green]✔ Completion installed in {profile}[/]")
        console.print(f"  Restart your shell or run: [bold]source {profile}[/bold]")
        return 0

    console.print(
        f"\n[bold]cloudctl tab completion — {shell}[/bold]\n\n"
        f"Add this line to [bold]{profile}[/bold]:\n\n"
        f"  [cyan]{line}[/cyan]\n\n"
        f"Or run [bold]cloudctl completion --install[/bold] to add it automatically.\n"
        f"\nThen restart your shell or run [bold]source {profile}[/bold].\n"
    )
    return 0


def cmd_uninstall(args: Any = None) -> int:
    """Remove cloudctl shell integration and optionally uninstall the package."""
    import os
    import shutil

    dry_run = getattr(args, "dry_run", False)
    keep_config = getattr(args, "keep_config", False)
    package_only = getattr(args, "package_only", False)

    if not dry_run:
        try:
            from InquirerPy import inquirer
            confirmed = inquirer.confirm(
                message="This will remove cloudctl shell integration. Continue?",
                default=False,
            ).execute()
        except Exception:
            confirmed = True  # non-interactive mode
        if not confirmed:
            console.print("[yellow]Uninstall cancelled.[/]")
            return 0

    removed = []
    skipped = []

    # ── 1. Remove shell integration lines ───────────────────────────────────
    if not package_only:
        shell_profiles = [
            os.path.expanduser("~/.bashrc"),
            os.path.expanduser("~/.zshrc"),
            os.path.expanduser("~/.config/fish/config.fish"),
        ]
        markers = [
            "# AWSCTL SHELL INTEGRATION",
            "# cloudctl completion",
        ]
        for profile in shell_profiles:
            if not os.path.exists(profile):
                continue
            try:
                with open(profile) as f:
                    lines = f.readlines()
                new_lines = _remove_cloudctl_blocks(lines, markers)
                if new_lines != lines:
                    if not dry_run:
                        with open(profile, "w") as f:
                            f.writelines(new_lines)
                    removed.append(profile)
            except Exception as e:
                skipped.append(f"{profile} ({e})")

    # ── 2. Remove config directory ───────────────────────────────────────────
    if not keep_config and not package_only:
        config_dir = os.path.expanduser("~/.config/cloudctl")
        if os.path.isdir(config_dir):
            if not dry_run:
                shutil.rmtree(config_dir)
            removed.append(config_dir)

    # ── 3. Uninstall the package ─────────────────────────────────────────────
    import subprocess

    uninstall_cmd = None
    if utils.which("pipx"):
        probe = subprocess.run(
            ["pipx", "list", "--short"], capture_output=True, text=True
        )
        if "cloudctl" in probe.stdout:
            uninstall_cmd = ["pipx", "uninstall", "cloudctl"]
    if not uninstall_cmd:
        uninstall_cmd = [sys.executable, "-m", "pip", "uninstall", "cloudctl", "-y"]

    if not dry_run:
        result = subprocess.run(uninstall_cmd)
        if result.returncode == 0:
            removed.append("cloudctl package")
        else:
            skipped.append("package uninstall (check output above)")
    else:
        console.print(f"[dim][dry-run] Would run: {' '.join(uninstall_cmd)}[/dim]")

    # ── 4. Summary ───────────────────────────────────────────────────────────
    prefix = "[dim][dry-run][/dim] " if dry_run else ""
    if removed:
        console.print(f"\n{prefix}[green]Removed:[/green]")
        for item in removed:
            console.print(f"  {prefix}✔ {item}")
    if skipped:
        console.print(f"\n{prefix}[yellow]Skipped:[/yellow]")
        for item in skipped:
            console.print(f"  {prefix}  {item}")
    if not dry_run:
        console.print("\n[bold]cloudctl has been uninstalled.[/bold]")
        console.print("Open a new shell to clear the cloudctl function from memory.")
    return 0


def cmd_prompt(args: Any = None) -> int:
    from .commands.prompt import PromptCommand
    return PromptCommand().execute(args)


def cmd_watch(args: Any = None) -> int:
    from .commands.watch import WatchCommand
    return WatchCommand().execute(args)


def cmd_upgrade(args: Any = None) -> int:
    """Upgrade cloudctl — prefers Artifactory pip, falls back to GitHub Releases."""
    import subprocess

    # Resolve index URL: flag > env var > None (GitHub fallback)
    index_url = (
        getattr(args, "index_url", None)
        or os.environ.get("AWSCTL_INDEX_URL", "")
    )

    if index_url:
        return _upgrade_via_pip(index_url)
    return _upgrade_via_github(args)


def _upgrade_via_pip(index_url: str) -> int:
    """Upgrade cloudctl from an Artifactory (or any PyPI-compatible) index."""
    import subprocess

    console.print(f"[bold]Upgrading cloudctl from:[/] {index_url}")

    # Prefer pipx if available (it manages the isolated venv).
    # Use 'pipx runpip cloudctl install --upgrade' which directly invokes pip
    # inside the pipx-managed venv — this correctly accepts --index-url.
    if utils.which("pipx"):
        console.print("  Using pipx...")
        result = subprocess.run(
            [
                "pipx", "runpip", "cloudctl", "install", "--upgrade", "cloudctl",
                "--index-url", index_url,
                "--extra-index-url", "https://pypi.org/simple/",
            ],
        )
    else:
        pip_args = [
            sys.executable, "-m", "pip", "install", "--upgrade",
            "--user", "cloudctl",
            "--index-url", index_url,
            "--extra-index-url", "https://pypi.org/simple/",
        ]
        # PEP 668: add --break-system-packages if supported
        probe = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--help"],
            capture_output=True, text=True,
        )
        if "break-system-packages" in probe.stdout:
            pip_args.insert(pip_args.index("--user") + 1, "--break-system-packages")

        result = subprocess.run(pip_args)

    if result.returncode == 0:
        console.print("[green]✅ cloudctl upgraded successfully.[/]")
        console.print("Restart your shell to pick up the new version.")
    else:
        console.print("[red]Upgrade failed.[/] Check output above.")
    return result.returncode


def _upgrade_via_github(args: Any) -> int:
    """Legacy upgrade path: download wheel from GitHub Releases."""
    import json
    import subprocess
    import tempfile
    import urllib.error
    import urllib.request

    github_org = "BT-IT-Infrastructure-CloudOps"
    github_repo = "aws-terraform-infra-cloudops-cloudctl"
    api_url = f"https://api.github.com/repos/{github_org}/{github_repo}/releases/latest"

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        console.print(
            "[yellow]No AWSCTL_INDEX_URL set and GITHUB_TOKEN not set.[/]\n\n"
            "To upgrade via Artifactory:\n"
            "  export AWSCTL_INDEX_URL=https://your-org.jfrog.io/artifactory/api/pypi/pypi-local/simple\n"
            "  cloudctl upgrade\n\n"
            "To upgrade via GitHub Releases (legacy):\n"
            "  export GITHUB_TOKEN=<your-PAT>  # read:contents scope required\n"
            "  cloudctl upgrade"
        )
        return 1

    console.print("[bold]Checking for latest release...[/]")
    try:
        req = urllib.request.Request(
            api_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json",
            },
        )
        with urllib.request.urlopen(
            req
        ) as resp:  # nosec B310 — hardcoded HTTPS GitHub API URL
            release = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        console.print(
            f"[red]GitHub API error {exc.code}:[/] {exc.reason}\n"
            "Check that GITHUB_TOKEN has [bold]read:contents[/bold] scope."
        )
        return 1
    except Exception as exc:
        console.print(f"[red]Failed to query GitHub API:[/] {exc}")
        return 1

    tag = release.get("tag_name", "unknown")
    console.print(f"  Latest release: [bold]{tag}[/]")

    # Find the wheel asset in the release
    wheel_asset = next(
        (a for a in release.get("assets", []) if a["name"].endswith(".whl")),
        None,
    )
    if not wheel_asset:
        console.print(
            f"[red]No .whl asset found in release {tag}.[/]\n"
            "The release may not have been built yet — check GitHub Actions."
        )
        return 1

    # Download wheel to a temp file, then install
    wheel_name = wheel_asset["name"]
    asset_api_url = wheel_asset["url"]  # API URL, requires Accept: octet-stream

    console.print(f"  Downloading [bold]{wheel_name}[/]...")
    tmp_path: Optional[str] = None
    try:
        req = urllib.request.Request(
            asset_api_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/octet-stream",
            },
        )
        with urllib.request.urlopen(
            req
        ) as resp:  # nosec B310 — hardcoded HTTPS GitHub download URL
            wheel_data = resp.read()

        with tempfile.NamedTemporaryFile(suffix=".whl", delete=False) as f:
            f.write(wheel_data)
            tmp_path = f.name

        console.print("  Installing...")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--upgrade",
                tmp_path,
                "--extra-index-url",
                "https://pypi.org/simple/",
            ],
            timeout=300,
        )
    except Exception as exc:
        console.print(f"[red]Download failed:[/] {exc}")
        return 1
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    if result.returncode == 0:
        console.print(f"[green]✅ cloudctl upgraded to {tag} successfully.[/]")
        console.print("Restart your shell to pick up the new version.")
    else:
        console.print("[red]Upgrade failed.[/] Check pip output above.")
    return result.returncode


def cmd_setup(args: Any = None) -> int:
    """Run the setup wizard / merge defaults."""
    return core.cmd_setup()


def cmd_orgs(args: Any = None) -> int:
    """Alias for cmd_org."""
    return cmd_org(args)


def cmd_list(args: Any = None) -> int:
    """Dispatch 'list <resource>' subcommands."""
    resource = getattr(args, "resource", None)
    if resource == "orgs":
        return cmd_orgs(args)
    console.print(f"Unknown resource: {resource}")
    return 1


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _build_parser():
    import argparse

    p = argparse.ArgumentParser(
        prog="cloudctl",
        description="Enterprise Cloud Identity & Context Manager",
    )
    p.add_argument("--version", action="store_true", help="Print version and exit")
    p.add_argument("--eval", action="store_true", help="Shell wrapper mode (internal)")
    p.add_argument(
        "--check-strategy",
        metavar="CMD",
        help="Print EVAL or EXEC for CMD and exit",
    )

    sub = p.add_subparsers(dest="command")

    # login
    lp = sub.add_parser("login", help="Authenticate with a cloud provider")
    lp.add_argument("org", nargs="?", help="Organization name")
    lp.add_argument("--org", dest="org_flag", help="Organization name (flag form)")
    lp.add_argument("--force", action="store_true", help="Force re-authentication")
    lp.add_argument("--account", "-a", help="Account ID (triggers EVAL mode)")
    lp.add_argument("--role", "-r", help="Role name (triggers EVAL mode)")
    lp.add_argument("--region", "-R", help="Region (triggers EVAL mode)")

    # switch / use (alias)
    for name in ("switch", "use"):
        sp = sub.add_parser(name, help="Switch cloud context interactively")
        sp.add_argument("org", nargs="?", help="Organization name")
        sp.add_argument("--account", help="Account ID")
        sp.add_argument("--role", help="Role name")
        sp.add_argument("--region", help="Region")

    # logout
    sub.add_parser("logout", help="Log out and clear context")

    # exec
    ep = sub.add_parser(
        "exec", help="Run a command with credentials (without changing shell context)"
    )
    ep.add_argument("--org", dest="exec_org", help="Organisation name")
    ep.add_argument("--account", dest="exec_account", help="Account/project ID")
    ep.add_argument("--role", dest="exec_role", help="Role/permission-set")
    ep.add_argument("--region", dest="exec_region", help="Region")
    ep.add_argument("cmd", nargs="+", metavar="CMD")

    # status / env (alias)
    sub.add_parser("status", help="Show active context")
    sub.add_parser("env", help="Show active context (alias for status)")

    # accounts
    ap = sub.add_parser("accounts", help="List accessible accounts")
    ap.add_argument("org", help="Organization name")
    ap.add_argument("--sync", action="store_true",
                    help="Refresh account list from the provider before displaying")

    # doctor
    dp = sub.add_parser("doctor", help="Validate system configuration")
    dp.add_argument("--fix-path", action="store_true",
                    help="Attempt to add missing bin directories to PATH")

    # init
    ip = sub.add_parser("init", help="Initialize configuration wizard")
    ip.add_argument(
        "--shell-only",
        action="store_true",
        dest="shell_only",
        help="Install shell integration only (no wizard)",
    )

    # prompt
    pp = sub.add_parser(
        "prompt",
        help="Emit cloud context for shell prompt (PS1/Starship/p10k)",
        description=(
            "Print the current cloud context as a compact string for use in PS1, "
            "Starship, or Powerlevel10k. Outputs nothing when no context is active "
            "(keeps prompt clean). Use --starship or --p10k to print a ready-to-paste "
            "config snippet."
        ),
    )
    ppg = pp.add_mutually_exclusive_group()
    ppg.add_argument("--short", action="store_true",
                     help="Short form: icon + org name only (e.g. ☁ bt-avm)")
    ppg.add_argument("--json", action="store_true",
                     help="Output full context as JSON for custom tooling")
    ppg.add_argument("--starship", action="store_true",
                     help="Print a ready-to-paste ~/.config/starship.toml snippet and exit")
    ppg.add_argument("--p10k", action="store_true",
                     help="Print a ready-to-paste ~/.p10k.zsh segment snippet and exit")
    pp.add_argument("--format", choices=["plain", "ps1"], default="plain",
                    help="Output format: plain (default) or ps1 (bash/zsh escape sequences)")
    pp.add_argument("--no-icon", action="store_true",
                    help="Omit the provider icon (☁/⬡/◆)")
    pp.add_argument("--warn-expiry", type=int, default=15, metavar="MINUTES",
                    help="Show ⚠ warning when credentials expire within N minutes (default: 15)")

    # watch
    wp = sub.add_parser(
        "watch",
        help="Auto-refresh credentials before they expire",
        description=(
            "Run a background loop that checks token expiry every --interval seconds "
            "and re-authenticates when less than --threshold seconds remain. "
            "Run in a dedicated terminal pane or tmux window alongside long-running "
            "Terraform operations. Press Ctrl+C to stop."
        ),
    )
    wp.add_argument("org", nargs="?",
                    help="Organisation to watch (defaults to active context)")
    wp.add_argument("--interval", type=int, default=60, metavar="SECS",
                    help="How often to check token expiry in seconds (default: 60)")
    wp.add_argument("--threshold", type=int, default=900, metavar="SECS",
                    help="Refresh when this many seconds remain on the token (default: 900 = 15m)")
    wp.add_argument("--once", action="store_true",
                    help="Check once and exit (useful for scripts and CI health checks)")

    # upgrade
    up = sub.add_parser("upgrade", help="Upgrade cloudctl (Artifactory or GitHub)")
    up.add_argument(
        "--index-url", dest="index_url", metavar="URL",
        help="Artifactory PyPI index URL (or set AWSCTL_INDEX_URL env var)",
    )

    # org
    op = sub.add_parser("org", help="Manage cloud organizations")
    org_sub = op.add_subparsers(dest="org_command")
    add_p = org_sub.add_parser("add", help="Add a new organization")
    add_p.add_argument(
        "--provider", choices=["aws", "azure", "gcp"], help="Cloud provider"
    )
    add_p.add_argument("--name", help="Org slug name")
    org_sub.add_parser("list", help="List configured organizations")
    rm_p = org_sub.add_parser("remove", help="Remove an organization")
    rm_p.add_argument("name", help="Org name to remove")

    # gcp — GCP-specific operations
    gcp_p = sub.add_parser("gcp", help="GCP-specific operations")
    gcp_sub = gcp_p.add_subparsers(dest="gcp_command")

    # gcp login
    login_p = gcp_sub.add_parser(
        "login",
        help="Authenticate with GCP (opens browser automatically)"
    )
    login_p.add_argument(
        "--account", "-a",
        help="GCP email to authenticate as (optional)"
    )

    # gcp grant-iam-roles
    grant_p = gcp_sub.add_parser(
        "grant-iam-roles",
        help="Grant organization-level IAM roles"
    )
    grant_p.add_argument("org_id", help="GCP Organization ID")
    grant_p.add_argument("member", help="Member email (e.g., admin@craighoad.com)")
    grant_p.add_argument(
        "roles",
        nargs="+",
        help="Roles to grant (e.g., projectCreator folderCreator)"
    )

    # uninstall
    un_p = sub.add_parser("uninstall", help="Remove cloudctl shell integration and package")
    un_p.add_argument("--dry-run", action="store_true", help="Show what would be removed without doing it")
    un_p.add_argument("--keep-config", action="store_true", help="Keep ~/.config/cloudctl/ intact")
    un_p.add_argument("--package-only", action="store_true", help="Uninstall package only (leave shell integration)")

    # completion
    comp_p = sub.add_parser("completion", help="Print shell completion setup instructions")
    comp_p.add_argument(
        "--shell", choices=["bash", "zsh", "fish"], default=None,
        help="Target shell (auto-detected if omitted)",
    )
    comp_p.add_argument(
        "--install", action="store_true",
        help="Write the activation line to your shell profile",
    )

    # Register argcomplete — must come after all subparsers are added.
    # This is a no-op when argcomplete is not installed or stdout is not a terminal.
    try:
        import argcomplete
        argcomplete.autocomplete(p)
    except ImportError:
        pass

    return p


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

_DISPATCH = {
    "login": "cmd_login",
    "switch": "cmd_switch",
    "use": "cmd_switch",
    "logout": "cmd_logout",
    "exec": "cmd_exec",
    "status": "cmd_status",
    "env": "cmd_status",
    "accounts": "cmd_accounts",
    "doctor": "cmd_doctor",
    "init": "cmd_init",
    "org": "cmd_org",
    "orgs": "cmd_orgs",
    "list": "cmd_list",
    "setup": "cmd_setup",
    "whoami": "cmd_whoami",
    "open": "cmd_open",
    "upgrade": "cmd_upgrade",
    "prompt": "cmd_prompt",
    "watch": "cmd_watch",
    "completion": "cmd_completion",
    "uninstall": "cmd_uninstall",
    "gcp": "cmd_gcp",
}


def main(argv: Optional[List[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    # Fast paths that don't need full argparse.
    # --check-strategy MUST be checked before --version: the shell wrapper calls
    # `_cloudctl_bin --check-strategy --version` to probe the flag, and if --version
    # were checked first it would print the version string instead of EXEC/EVAL.
    if "--check-strategy" in argv:
        idx = argv.index("--check-strategy")
        cmd_arg = argv[idx + 1] if idx + 1 < len(argv) else ""
        sys.stdout.write(determine_strategy([cmd_arg]) + "\n")
        return 0

    if "--version" in argv:
        stdout_console.print(_resolved_version())
        return 0

    if "--help" in argv or "-h" in argv:
        stdout_console.print(
            "[bold]cloudctl[/bold] — Enterprise Cloud Identity & Context Manager\n\n"
            "Commands: login, switch, logout, exec, status, env, accounts, doctor, init,\n"
            "          org, prompt, watch, upgrade, completion, uninstall, gcp\n"
            "Options:  --version, --help, --check-strategy <cmd>"
        )
        return 0

    # TTY guard — warn when --eval is used without the shell wrapper context.
    # The shell wrapper sets AWSCTL_WRAPPER_ACTIVE=1 before calling us.
    # Direct invocation with --eval risks exposing credentials in shell history
    # or redirecting them to a file.
    eval_mode = "--eval" in argv
    argv = [a for a in argv if a != "--eval"]
    if eval_mode and not os.environ.get("AWSCTL_WRAPPER_ACTIVE"):
        sys.stderr.write(
            "cloudctl: WARNING — --eval used outside shell wrapper context.\n"
            "  Credentials will be printed to stdout and may leak into shell\n"
            "  history or redirected files. Run 'cloudctl init' to install the\n"
            "  shell wrapper, or set AWSCTL_WRAPPER_ACTIVE=1 to suppress.\n"
        )

    parser = _build_parser()

    if not argv:
        parser.print_help(sys.stderr)
        return 0

    args = parser.parse_args(argv)
    handler_name = _DISPATCH.get(args.command)
    if handler_name is None:
        parser.print_help(sys.stderr)
        return 0

    # Look up the handler by name at call time so monkeypatching works.
    import cloudctl.cli as _self

    handler = getattr(_self, handler_name)
    return handler(args)
