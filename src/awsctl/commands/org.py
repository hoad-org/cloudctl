# src/awsctl/commands/org.py
"""
awsctl org — manage cloud organization entries.

  awsctl org add    — auth-first wizard: login, discover accounts/projects, save
  awsctl org list   — list configured orgs with provider and key identifier
  awsctl org remove — remove an org entry from config
"""
from __future__ import annotations

import json
import subprocess
from typing import Any, Dict, List, Optional

import yaml

from awsctl.commands.base import BaseCommand
from awsctl import core, utils


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _load_orgs_yaml() -> Dict[str, Any]:
    from awsctl import config as _cfg

    path = _cfg.ORGS_USER
    if path.exists():
        try:
            return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            pass
    return {}


def _save_orgs_yaml(data: Dict[str, Any]) -> None:
    from awsctl import config as _cfg

    path = _cfg.ORGS_USER
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(data), encoding="utf-8")


def _run(cmd: List[str], timeout: int = 30) -> Optional[str]:
    """Run a CLI command and return stdout, or None on failure."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Provider-specific discovery helpers
# ---------------------------------------------------------------------------


def _discover_aws(org: Dict[str, Any]) -> Dict[str, Any]:
    """Prompt for AWS SSO fields (no live discovery needed — SSO handles it)."""
    from awsctl.wizard import inquirer

    utils.console.print("[bold]AWS org configuration[/bold]")
    org["sso_start_url"] = inquirer.text(
        message="SSO Start URL (e.g. https://d-xxxx.awsapps.com/start):",
        default=org.get("sso_start_url", ""),
    ).execute()
    org["sso_region"] = inquirer.text(
        message="SSO Region (e.g. us-east-1):",
        default=org.get("sso_region", "us-east-1"),
    ).execute()
    org["default_region"] = inquirer.text(
        message="Default region for CLI calls:",
        default=org.get("default_region", org.get("sso_region", "us-east-1")),
    ).execute()
    return org


def _discover_azure(org: Dict[str, Any]) -> Dict[str, Any]:
    """Run az login then discover subscriptions."""
    utils.console.print("[bold]Azure — running 'az login'...[/bold]")
    subprocess.run(["az", "login"], check=False)

    subs_json = _run(["az", "account", "list", "--output", "json"])
    if subs_json:
        try:
            subs = json.loads(subs_json)
            if subs:
                utils.console.print(
                    f"[green]Found {len(subs)} subscription(s).[/green]"
                )
                # Pick default subscription
                choices = [f"{s.get('name', '?')} ({s.get('id', '?')})" for s in subs]
                from awsctl.wizard import inquirer

                chosen = inquirer.select(
                    message="Select default subscription:",
                    choices=choices,
                ).execute()
                idx = choices.index(chosen)
                org["default_subscription"] = subs[idx]["id"]
                org["tenant_id"] = subs[idx].get("tenantId", "")
        except (json.JSONDecodeError, IndexError, KeyError):
            pass
    return org


def _discover_gcp(org: Dict[str, Any]) -> Dict[str, Any]:
    """Run gcloud auth login then discover projects."""
    utils.console.print("[bold]GCP — running 'gcloud auth login'...[/bold]")
    subprocess.run(["gcloud", "auth", "login"], check=False)
    subprocess.run(["gcloud", "auth", "application-default", "login"], check=False)

    projects_json = _run(["gcloud", "projects", "list", "--format=json"], timeout=30)
    if projects_json:
        try:
            projects = json.loads(projects_json)
            if projects:
                utils.console.print(f"[green]Found {len(projects)} project(s).[/green]")
                choices = [
                    f"{p.get('name', '?')} ({p.get('projectId', '?')})"
                    for p in projects
                ]
                from awsctl.wizard import inquirer

                chosen = inquirer.select(
                    message="Select default project:",
                    choices=choices,
                ).execute()
                idx = choices.index(chosen)
                org["default_project"] = projects[idx]["projectId"]
        except (json.JSONDecodeError, IndexError, KeyError):
            pass
    return org


# ---------------------------------------------------------------------------
# OrgAddCommand
# ---------------------------------------------------------------------------


class OrgAddCommand(BaseCommand):
    """Interactively add a new org (auth-first flow for Azure/GCP)."""

    def configure_parser(self, subparsers):
        p = subparsers.add_parser("add", help="Add a new organization")
        p.add_argument(
            "--provider", choices=["aws", "azure", "gcp"], help="Cloud provider"
        )
        p.add_argument("--name", help="Org slug name")

    def execute(self, args) -> int:
        from awsctl.wizard import inquirer

        provider = (
            getattr(args, "provider", None)
            or inquirer.select(
                message="Cloud provider:",
                choices=["aws", "azure", "gcp"],
            ).execute()
        )

        name = (
            getattr(args, "name", None)
            or inquirer.text(
                message=f"Org name/slug (e.g. {provider}-prod):",
            ).execute()
        )

        if not name:
            utils.console.print("[red]Org name is required.[/red]")
            return 1

        org: Dict[str, Any] = {"name": name, "provider": provider}

        try:
            if provider == "aws":
                org = _discover_aws(org)
            elif provider == "azure":
                org = _discover_azure(org)
            elif provider == "gcp":
                org = _discover_gcp(org)
        except Exception as e:
            utils.console.print(f"[red]Discovery failed: {e}[/red]")
            return 1

        # Save to orgs.yaml
        data = _load_orgs_yaml()
        orgs: List[Dict[str, Any]] = data.get("orgs", [])

        # Replace existing entry with same name, or append
        replaced = False
        for i, existing in enumerate(orgs):
            if existing.get("name") == name:
                orgs[i] = org
                replaced = True
                break
        if not replaced:
            orgs.append(org)

        data["orgs"] = orgs
        if "enabled_orgs" not in data:
            data["enabled_orgs"] = [o["name"] for o in orgs]
        elif name not in data["enabled_orgs"]:
            data["enabled_orgs"].append(name)

        if "plugins" not in data:
            data["plugins"] = {"enabled": []}

        _save_orgs_yaml(data)

        # Sync AWS profiles if applicable
        if provider == "aws":
            core.cmd_config_sync()

        action = "Updated" if replaced else "Added"
        utils.console.print(
            f"[green]{action} org '[bold]{name}[/bold]' ({provider}).[/green]"
        )
        return 0


# ---------------------------------------------------------------------------
# OrgListCommand
# ---------------------------------------------------------------------------


class OrgListCommand(BaseCommand):
    """List configured orgs."""

    def configure_parser(self, subparsers):
        subparsers.add_parser("list", help="List configured organizations")

    def execute(self, args) -> int:
        data = _load_orgs_yaml()
        orgs: List[Dict[str, Any]] = data.get("orgs", [])
        enabled: List[str] = data.get("enabled_orgs", [o.get("name", "") for o in orgs])

        if not orgs:
            utils.console.print(
                "No organizations configured. Run [bold]awsctl org add[/bold] or [bold]awsctl init[/bold]."
            )
            return 0

        utils.console.print(f"\n[bold]Configured Organizations[/bold] ({len(orgs)})\n")
        for org in orgs:
            name = org.get("name", "?")
            provider = org.get("provider", "aws").upper()
            is_enabled = name in enabled
            status = "[green]enabled[/green]" if is_enabled else "[dim]disabled[/dim]"

            # Key identifier per provider
            if org.get("provider", "aws") == "aws":
                key = org.get("sso_start_url", "(no SSO URL)")
            elif org.get("provider") == "azure":
                key = (
                    org.get("tenant_id")
                    or org.get("default_subscription")
                    or "(no tenant)"
                )
            elif org.get("provider") == "gcp":
                key = org.get("default_project", "(no project)")
            else:
                key = ""

            utils.console.print(
                f"  [bold]{name}[/bold]  [{provider}]  {status}"
                + (f"\n    {key}" if key else "")
            )

        return 0


# ---------------------------------------------------------------------------
# OrgRemoveCommand
# ---------------------------------------------------------------------------


class OrgRemoveCommand(BaseCommand):
    """Remove an org from the configuration."""

    def configure_parser(self, subparsers):
        p = subparsers.add_parser("remove", help="Remove an organization")
        p.add_argument("name", help="Org name to remove")

    def execute(self, args) -> int:
        name = args.name
        data = _load_orgs_yaml()
        orgs = data.get("orgs", [])
        before = len(orgs)
        data["orgs"] = [o for o in orgs if o.get("name") != name]
        if "enabled_orgs" in data:
            data["enabled_orgs"] = [n for n in data["enabled_orgs"] if n != name]

        if len(data["orgs"]) == before:
            utils.console.print(f"[yellow]Org '{name}' not found.[/yellow]")
            return 1

        _save_orgs_yaml(data)
        utils.console.print(f"[green]Removed org '[bold]{name}[/bold]'.[/green]")
        return 0
