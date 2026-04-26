"""
cloudctl.wizard — interactive setup wizard for first-time configuration.

Guides the user through configuring AWS, Azure, and/or GCP organisations,
writes orgs.yaml atomically, and installs shell integration.

Entry point:  run_wizard() → bool
Also called by:  cloudctl org add  (provider-specific paths only)
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from typing import Any, Dict, List, Optional, Tuple

import yaml

from .. import core, schema, shell, utils
from ..env_detection import detect_shell
from . import inquirer

# ---------------------------------------------------------------------------
# Output helpers  (all write to utils.console so tests can capture them)
# ---------------------------------------------------------------------------


def _section(title: str) -> None:
    utils.console.print(f"\n[bold cyan]── {title} ──[/bold cyan]")


def _ok(msg: str) -> None:
    utils.console.print(f"[green]  ✓[/green]  {msg}")


def _warn(msg: str) -> None:
    utils.console.print(f"[yellow]  ⚠[/yellow]  {msg}")


def _err(msg: str) -> None:
    utils.console.print(f"[red]  ✗[/red]  {msg}")


def _info(msg: str) -> None:
    utils.console.print(f"[dim]     {msg}[/dim]")


# ---------------------------------------------------------------------------
# Welcome screen
# ---------------------------------------------------------------------------


def _show_welcome() -> None:
    try:
        from importlib.metadata import version as _ver
        ver = _ver("cloudctl")
    except Exception:
        ver = "?"

    try:
        from rich.panel import Panel
        from rich.align import Align

        utils.console.print()
        utils.console.print(
            Panel(
                Align.center(
                    f"[bold cyan]cloudctl v{ver}[/bold cyan]\n"
                    "[dim]Enterprise Cloud Identity & Context Manager[/dim]\n\n"
                    "[bold white]AWS[/bold white]  ·  "
                    "[bold blue]Azure[/bold blue]  ·  "
                    "[bold yellow]GCP[/bold yellow]"
                ),
                title="[bold]Setup Wizard[/bold]",
                border_style="cyan",
                padding=(1, 4),
            )
        )
    except Exception:
        utils.console.print(f"\n[bold cyan]cloudctl v{ver} — Setup Wizard[/bold cyan]\n")

    utils.console.print()
    utils.console.print(
        "  This wizard will help you configure your cloud organisations\n"
        "  and install shell integration.\n"
    )
    utils.console.print(
        "  [dim]Add more organisations any time with: cloudctl org add[/dim]"
    )


# ---------------------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------------------


def _select_providers() -> List[str]:
    """Ask which cloud providers to configure. Returns list of provider strings."""
    _section("Select Cloud Providers")
    utils.console.print(
        "  Which cloud providers do you need to configure?\n"
        "  [dim](space to select / deselect, enter to confirm)[/dim]\n"
    )
    selected = inquirer.checkbox(
        message="Providers:",
        choices=[
            {"name": "AWS   — Amazon Web Services (Commercial & GovCloud)", "value": "aws", "enabled": True},
            {"name": "Azure — Microsoft Azure", "value": "azure", "enabled": False},
            {"name": "GCP   — Google Cloud Platform", "value": "gcp", "enabled": False},
        ],
    ).execute()
    return selected or []


# ---------------------------------------------------------------------------
# AWS — registry + manual
# ---------------------------------------------------------------------------


def _load_registry_choices() -> List[Dict[str, Any]]:
    """Return InquirerPy choices from the org registry, filtered of placeholders."""
    try:
        from .. import registry as _reg
        choices = _reg.get_choices()
        return [
            c for c in choices
            if c.get("value", {}).get("name") != "manual-setup-required"
        ]
    except Exception:
        return []


def _add_aws_orgs() -> List[Dict[str, Any]]:
    """Collect one or more AWS org definitions."""
    _section("AWS Configuration")
    orgs: List[Dict[str, Any]] = []

    # Registry picker — only shown when real entries exist
    registry_choices = _load_registry_choices()
    if registry_choices:
        utils.console.print(
            "  Your organisation's registry has pre-configured AWS orgs.\n"
            "  [dim](space to select / deselect, enter to confirm)[/dim]\n"
        )
        selected = inquirer.checkbox(
            message="Select AWS organisations from registry:",
            choices=registry_choices,
        ).execute()
        if selected:
            orgs.extend(selected)
            _ok(f"Selected {len(selected)} org(s) from registry.")

    # Manual entry — always offered; default=True if registry produced nothing
    want_manual = inquirer.confirm(
        message="Add an AWS org manually?",
        default=(len(orgs) == 0),
    ).execute()

    while want_manual:
        org = _prompt_aws_manual()
        if org:
            orgs.append(org)
            _ok(f"Added AWS org '{org['name']}'.")

        want_manual = inquirer.confirm(
            message="Add another AWS org?",
            default=False,
        ).execute()

    return orgs


def _prompt_aws_manual() -> Optional[Dict[str, Any]]:
    """Interactively collect all fields for one AWS org."""
    org: Dict[str, Any] = {"provider": "aws"}

    # Name
    while True:
        name = inquirer.text(
            message="Org name (slug, e.g. bt-avm, company-prod):",
        ).execute().strip()
        if name:
            org["name"] = name
            break
        _err("Org name cannot be empty.")

    # SSO Start URL
    _info("Where to find this → AWS Console : IAM Identity Center → Settings → Instance ARN")
    _info("It looks like: https://d-xxxxxxxxxx.awsapps.com/start")
    _info("GovCloud:      https://d-xxxxxxxxxx.awsapps-us-gov.com/start")
    while True:
        sso_url = inquirer.text(
            message="SSO Start URL:",
            default=org.get("sso_start_url", ""),
        ).execute().strip()
        if sso_url.startswith("https://"):
            org["sso_start_url"] = sso_url
            break
        if not sso_url:
            _err("SSO Start URL is required.")
        else:
            _err("URL must start with https://")

    # Partition — inferred from URL; confirmed or overridden
    inferred = schema.partition_from_sso_url(org["sso_start_url"])
    partition_display = schema.AWS_PARTITIONS.get(inferred, {}).get("display", inferred)

    if inferred != "aws":
        _ok(f"Detected partition: {partition_display}")
        org["partition"] = inferred
    else:
        chosen = inquirer.select(
            message="AWS Partition:",
            choices=[
                {
                    "name": "Commercial  (aws)         — standard AWS regions",
                    "value": "aws",
                },
                {
                    "name": "GovCloud US (aws-us-gov)  — FedRAMP / ITAR workloads",
                    "value": "aws-us-gov",
                },
                {
                    "name": "China       (aws-cn)      — IAM long-term keys (no SSO)",
                    "value": "aws-cn",
                },
            ],
        ).execute()
        org["partition"] = chosen

    partition = org["partition"]

    _info("Where to find SSO region → same IAM Identity Center Settings page")
    _info("This is the region IC is deployed in — often different from your workload region")
    # SSO Region — sensible default per partition
    default_sso_region = {
        "aws": "us-east-1",
        "aws-us-gov": "us-gov-east-1",
        "aws-cn": "cn-north-1",
    }.get(partition, "us-east-1")

    org["sso_region"] = inquirer.text(
        message="SSO Region:",
        default=org.get("sso_region", default_sso_region),
    ).execute().strip() or default_sso_region

    # Default region for CLI operations
    org["default_region"] = inquirer.text(
        message="Default region for CLI operations:",
        default=org.get("default_region", org["sso_region"]),
    ).execute().strip() or org["sso_region"]

    return org


# ---------------------------------------------------------------------------
# Azure — live discovery via az CLI, with manual fallback
# ---------------------------------------------------------------------------


def _add_azure_orgs() -> List[Dict[str, Any]]:
    """Collect one or more Azure org definitions."""
    _section("Azure Configuration")
    orgs: List[Dict[str, Any]] = []

    az_ok = bool(shutil.which("az"))
    if not az_ok:
        _warn("Azure CLI ('az') not found on PATH.")
        _info("Install (macOS):  brew install azure-cli")
        _info("Install (Linux):  curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash")
        _info("You can still add Azure orgs manually using your Tenant ID.")
    else:
        _ok("Azure CLI detected.")

    add_org = inquirer.confirm(
        message="Add an Azure organisation?",
        default=True,
    ).execute()

    while add_org:
        org = _collect_one_azure_org(az_ok)
        if org:
            orgs.append(org)
            _ok(f"Added Azure org '{org['name']}'.")

        add_org = inquirer.confirm(
            message="Add another Azure organisation?",
            default=False,
        ).execute()

    return orgs


def _collect_one_azure_org(az_available: bool) -> Optional[Dict[str, Any]]:
    org: Dict[str, Any] = {"provider": "azure"}

    # Name
    while True:
        name = inquirer.text(
            message="Org name (slug, e.g. bt-azure, contoso-prod):",
        ).execute().strip()
        if name:
            org["name"] = name
            break
        _err("Org name cannot be empty.")

    if az_available:
        return _discover_azure_live(org)
    return _prompt_azure_manual(org)


def _discover_azure_live(org: Dict[str, Any]) -> Dict[str, Any]:
    """Run az login, discover subscriptions, let user pick default."""
    utils.console.print("\n  [dim]Running 'az login'...[/dim]")
    result = subprocess.run(["az", "login"], check=False)

    if result.returncode != 0:
        _warn("az login did not complete successfully. Falling back to manual entry.")
        return _prompt_azure_manual(org)

    utils.console.print("  [dim]Fetching subscriptions...[/dim]")
    subs, err = _run_json(["az", "account", "list", "--output", "json"])

    if err or not subs:
        _warn("Could not list subscriptions. Falling back to manual entry.")
        return _prompt_azure_manual(org)

    _ok(f"Found {len(subs)} subscription(s).")

    if len(subs) == 1:
        chosen = subs[0]
        _info(f"Auto-selecting: {chosen.get('name')} ({chosen.get('id', '')[:8]}...)")
    else:
        choices = [
            {
                "name": f"{s.get('name', '?')}  [dim]({s.get('id', '?')[:8]}...)[/dim]",
                "value": s,
            }
            for s in subs
        ]
        chosen = inquirer.select(
            message="Select default subscription:",
            choices=choices,
        ).execute()

    org["tenant_id"] = chosen.get("tenantId", "")
    org["default_subscription"] = chosen.get("id", "")

    # Confirm or override tenant ID
    org["tenant_id"] = inquirer.text(
        message="Tenant ID:",
        default=org["tenant_id"],
    ).execute().strip() or org["tenant_id"]

    return org


def _prompt_azure_manual(org: Dict[str, Any]) -> Dict[str, Any]:
    """Collect Azure fields without CLI discovery."""
    _info("Where to find Tenant ID → Azure Portal : Azure Active Directory → Overview → Tenant ID")
    _info("Format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
    while True:
        tenant_id = inquirer.text(
            message="Azure Tenant ID:",
            default=org.get("tenant_id", ""),
        ).execute().strip()
        if tenant_id:
            org["tenant_id"] = tenant_id
            break
        _err("Tenant ID is required.")

    sub_id = inquirer.text(
        message="Default Subscription ID (leave blank to select at runtime):",
        default=org.get("default_subscription", ""),
    ).execute().strip()
    if sub_id:
        org["default_subscription"] = sub_id

    return org


# ---------------------------------------------------------------------------
# GCP — live discovery via gcloud CLI, with manual fallback
# ---------------------------------------------------------------------------


def _add_gcp_orgs() -> List[Dict[str, Any]]:
    """Collect one or more GCP org definitions."""
    _section("GCP Configuration")
    orgs: List[Dict[str, Any]] = []

    gcloud_ok = bool(shutil.which("gcloud"))
    if not gcloud_ok:
        _warn("Google Cloud SDK ('gcloud') not found on PATH.")
        _info("Install (macOS):  brew install --cask google-cloud-sdk")
        _info(
            "Install (Linux):  curl https://sdk.cloud.google.com | bash && exec -l $SHELL"
        )
        _info("You can still add GCP orgs manually using your Project ID.")
    else:
        _ok("Google Cloud SDK detected.")

    add_org = inquirer.confirm(
        message="Add a GCP organisation?",
        default=True,
    ).execute()

    while add_org:
        org = _collect_one_gcp_org(gcloud_ok)
        if org:
            orgs.append(org)
            _ok(f"Added GCP org '{org['name']}'.")

        add_org = inquirer.confirm(
            message="Add another GCP organisation?",
            default=False,
        ).execute()

    return orgs


def _collect_one_gcp_org(gcloud_available: bool) -> Optional[Dict[str, Any]]:
    org: Dict[str, Any] = {"provider": "gcp"}

    while True:
        name = inquirer.text(
            message="Org name (slug, e.g. bt-gcp, company-prod):",
        ).execute().strip()
        if name:
            org["name"] = name
            break
        _err("Org name cannot be empty.")

    if gcloud_available:
        return _discover_gcp_live(org)
    return _prompt_gcp_manual(org)


def _discover_gcp_live(org: Dict[str, Any]) -> Dict[str, Any]:
    """Run gcloud auth login, discover projects, let user pick default."""
    utils.console.print("\n  [dim]Running 'gcloud auth login'...[/dim]")
    r = subprocess.run(["gcloud", "auth", "login"], check=False)

    if r.returncode != 0:
        _warn("gcloud auth login did not complete. Falling back to manual entry.")
        return _prompt_gcp_manual(org)

    utils.console.print(
        "  [dim]Running 'gcloud auth application-default login'[/dim]\n"
        "  [dim](required for Terraform and SDKs)...[/dim]"
    )
    subprocess.run(["gcloud", "auth", "application-default", "login"], check=False)

    utils.console.print("  [dim]Fetching projects...[/dim]")
    projects, err = _run_json(
        ["gcloud", "projects", "list", "--format=json"], timeout=30
    )

    if err or not projects:
        _warn("Could not list projects. Falling back to manual entry.")
        return _prompt_gcp_manual(org)

    _ok(f"Found {len(projects)} project(s).")

    if len(projects) == 1:
        chosen = projects[0]
        _info(f"Auto-selecting: {chosen.get('name')} ({chosen.get('projectId')})")
    else:
        choices = [
            {
                "name": f"{p.get('name', '?')}  [dim]({p.get('projectId', '?')})[/dim]",
                "value": p,
            }
            for p in projects
        ]
        chosen = inquirer.select(
            message="Select default project:",
            choices=choices,
        ).execute()

    org["default_project"] = chosen.get("projectId", "")

    region = inquirer.text(
        message="Default region (e.g. us-central1 — leave blank to set later):",
        default="",
    ).execute().strip()
    if region:
        org["region"] = region

    return org


def _prompt_gcp_manual(org: Dict[str, Any]) -> Dict[str, Any]:
    """Collect GCP fields without CLI discovery."""
    _info("Where to find Project ID → GCP Console : click the project selector dropdown")
    _info("Use the ID (e.g. my-project-123), not the display name")
    while True:
        project_id = inquirer.text(
            message="GCP Project ID:",
            default=org.get("default_project", ""),
        ).execute().strip()
        if project_id:
            org["default_project"] = project_id
            break
        _err("Project ID is required.")

    region = inquirer.text(
        message="Default region (e.g. us-central1 — leave blank to set later):",
        default="",
    ).execute().strip()
    if region:
        org["region"] = region

    return org


# ---------------------------------------------------------------------------
# Summary + confirmation
# ---------------------------------------------------------------------------


def _show_summary(orgs: List[Dict[str, Any]]) -> None:
    _section("Summary")
    utils.console.print(
        f"\n  [bold]{len(orgs)}[/bold] organisation(s) will be written to your config:\n"
    )

    for org in orgs:
        provider = org.get("provider", "aws").upper()
        name = org.get("name", "?")

        if provider == "AWS":
            partition = org.get("partition", "aws")
            display = schema.AWS_PARTITIONS.get(partition, {}).get("display", partition)
            detail = f"{display} · SSO: {org.get('sso_start_url', '?')}"
        elif provider == "AZURE":
            tenant = org.get("tenant_id", "?")
            sub = org.get("default_subscription", "(select at runtime)")
            detail = f"Tenant: {tenant} · Sub: {sub}"
        elif provider == "GCP":
            detail = f"Project: {org.get('default_project', '?')}"
        else:
            detail = ""

        utils.console.print(f"  [bold]{name}[/bold]  [{provider}]")
        if detail:
            utils.console.print(f"  [dim]     {detail}[/dim]")

    utils.console.print()


# ---------------------------------------------------------------------------
# Config write (atomic, merge-safe)
# ---------------------------------------------------------------------------


def _write_config(orgs: List[Dict[str, Any]]) -> bool:
    _section("Writing Configuration")

    try:
        orgs_path = core.get_orgs_path(ensure=True)
        orgs_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing config; preserve keys we don't own (aliases, plugins, etc.)
        current: Dict[str, Any] = {}
        if orgs_path.exists():
            try:
                current = yaml.safe_load(orgs_path.read_text(encoding="utf-8")) or {}
            except Exception as exc:
                _err(f"Could not read existing config: {exc}")
                return False

        # Merge: new orgs replace same-named existing entries, others are preserved
        existing_by_name: Dict[str, Dict[str, Any]] = {
            o["name"]: o
            for o in current.get("orgs", [])
            if isinstance(o, dict) and o.get("name")
        }
        for org in orgs:
            existing_by_name[org["name"]] = org

        current["orgs"] = list(existing_by_name.values())

        # Update enabled_orgs — add new names, leave existing ones untouched
        enabled: List[str] = current.get("enabled_orgs", [])
        for org in orgs:
            if org["name"] not in enabled:
                enabled.append(org["name"])
        current["enabled_orgs"] = enabled

        if "plugins" not in current:
            current["plugins"] = {"enabled": []}

        # Atomic write
        fd, tmp_path = tempfile.mkstemp(dir=orgs_path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(yaml.dump(current, default_flow_style=False, sort_keys=False))
            os.replace(tmp_path, orgs_path)
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

        _ok(f"Config saved → {orgs_path}")

        # Sync AWS ~/.aws/config profiles (non-fatal if it fails)
        if any(o.get("provider", "aws") == "aws" for o in orgs):
            if core.cmd_config_sync() != 0:
                _warn("AWS profile sync had issues — run 'cloudctl doctor' to diagnose.")

        return True

    except Exception as exc:
        _err(f"Failed to write config: {exc}")
        return False


# ---------------------------------------------------------------------------
# Shell integration
# ---------------------------------------------------------------------------


def _install_shell_integration() -> None:
    _section("Shell Integration")

    detected = detect_shell()

    if detected == "powershell":
        target = shell.detect_powershell_profile()
        inject_fn = shell.inject_powershell_function
    elif detected == "fish":
        target = shell.detect_fish_function_file()
        inject_fn = shell.inject_fish_function
    else:
        target = shell.detect_shell_profile()
        inject_fn = shell.inject_shell_function

    utils.console.print(f"  Detected shell: [cyan]{detected or 'bash/zsh'}[/cyan]")
    utils.console.print(f"  Profile path:   [cyan]{target}[/cyan]\n")

    confirmed = inquirer.confirm(
        message=f"Install shell integration into {target}?",
        default=True,
    ).execute()

    if confirmed:
        if inject_fn(target):
            _ok("Shell integration installed.")
            _info(f"Restart your terminal, or run:  source {target}")
        else:
            _ok("Shell integration already present — nothing to do.")
    else:
        _warn(
            "Skipped. Install manually later with:  cloudctl init --shell-only"
        )


# ---------------------------------------------------------------------------
# Next-steps guidance
# ---------------------------------------------------------------------------


def _show_next_steps(orgs: List[Dict[str, Any]]) -> None:
    _section("You're all set!")
    utils.console.print()

    utils.console.print("  [bold]1. Restart your terminal[/bold] (or reload your profile)")
    utils.console.print()
    utils.console.print("  [bold]2. Log in to each org:[/bold]")
    for org in orgs:
        utils.console.print(f"       cloudctl login [bold]{org['name']}[/bold]")
    utils.console.print()
    utils.console.print("  [bold]3. Switch context and verify:[/bold]")
    first = orgs[0]["name"] if orgs else "<org>"
    utils.console.print(f"       cloudctl switch [bold]{first}[/bold]")
    utils.console.print(f"       cloudctl env")
    utils.console.print()
    utils.console.print(
        "  [dim]cloudctl doctor[/dim]          — run health checks at any time\n"
        "  [dim]cloudctl org add[/dim]         — add more organisations\n"
        "  [dim]cloudctl org list[/dim]        — list configured organisations\n"
        "  [dim]cloudctl --help[/dim]          — full command reference\n"
    )


# ---------------------------------------------------------------------------
# Shared utility
# ---------------------------------------------------------------------------


def _run_json(
    cmd: List[str], timeout: int = 30
) -> Tuple[Optional[List[Any]], Optional[str]]:
    """Run a CLI command and parse its stdout as JSON.

    Returns (parsed_list, None) on success, (None, error_message) on failure.
    """
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        if result.returncode != 0:
            return None, result.stderr.strip()
        data = json.loads(result.stdout.strip())
        if not isinstance(data, list):
            return None, "unexpected response format"
        return data, None
    except subprocess.TimeoutExpired:
        return None, "timed out"
    except json.JSONDecodeError as exc:
        return None, f"JSON parse error: {exc}"
    except Exception as exc:
        return None, str(exc)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def run_wizard() -> bool:
    """
    Run the full interactive setup wizard.

    Returns True on success (config written), False on cancellation or error.
    Ctrl+C is caught gracefully — no partial writes occur.
    """
    try:
        _show_welcome()

        # 1 — Provider selection
        providers = _select_providers()
        if not providers:
            _warn("No providers selected. Nothing to configure.")
            return False

        # 2 — Per-provider org collection
        all_orgs: List[Dict[str, Any]] = []

        if "aws" in providers:
            all_orgs.extend(_add_aws_orgs())

        if "azure" in providers:
            all_orgs.extend(_add_azure_orgs())

        if "gcp" in providers:
            all_orgs.extend(_add_gcp_orgs())

        if not all_orgs:
            _warn("No organisations configured. Nothing to write.")
            return False

        # 3 — Review + confirm
        _show_summary(all_orgs)

        if not inquirer.confirm(
            message="Save this configuration?",
            default=True,
        ).execute():
            _warn("Cancelled — no changes written.")
            return False

        # 4 — Write config
        if not _write_config(all_orgs):
            return False

        # 5 — Shell integration
        _install_shell_integration()

        # 6 — Guidance
        _show_next_steps(all_orgs)

        utils.console.print("[bold green]Setup complete ✓[/bold green]\n")
        return True

    except KeyboardInterrupt:
        utils.console.print(
            "\n\n[yellow]  Wizard cancelled — no changes written.[/yellow]\n"
        )
        return False
    except Exception as exc:
        utils.console.print(f"\n[red]  Wizard failed: {exc}[/red]\n")
        if os.environ.get("AWSCTL_DEBUG") == "1":
            import traceback
            traceback.print_exc()
        return False
