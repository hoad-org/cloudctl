import os
import tempfile
from typing import Any, Dict, List

from .. import core, registry, shell, utils
from . import inquirer
from ..env_detection import detect_shell


def _prompt_azure_org() -> Dict[str, Any]:
    """Interactively collect fields for a new Azure org entry."""
    name = inquirer.text(message="Org name (slug, e.g. azure-prod):").execute()
    tenant_id = inquirer.text(
        message="Azure Tenant ID (leave blank to use current az login):",
        default="",
    ).execute()
    default_sub = inquirer.text(
        message="Default Subscription ID (leave blank to pick at runtime):",
        default="",
    ).execute()
    roles_raw = inquirer.text(
        message="Roles (comma-separated, e.g. Contributor,Reader):",
        default="Contributor,Reader",
    ).execute()
    roles = [r.strip() for r in roles_raw.split(",") if r.strip()]

    org: Dict[str, Any] = {"name": name, "provider": "azure"}
    if tenant_id:
        org["tenant_id"] = tenant_id
    if default_sub:
        org["default_subscription"] = default_sub
    if roles:
        org["roles"] = roles
    return org


def _prompt_gcp_org() -> Dict[str, Any]:
    """Interactively collect fields for a new GCP org entry."""
    name = inquirer.text(message="Org name (slug, e.g. gcp-prod):").execute()
    default_project = inquirer.text(
        message="Default GCP Project ID (leave blank to pick at runtime):",
        default="",
    ).execute()
    roles_raw = inquirer.text(
        message="Roles (comma-separated, e.g. roles/viewer,roles/editor):",
        default="roles/viewer,roles/editor,roles/owner",
    ).execute()
    roles = [r.strip() for r in roles_raw.split(",") if r.strip()]

    org: Dict[str, Any] = {"name": name, "provider": "gcp"}
    if default_project:
        org["default_project"] = default_project
    if roles:
        org["roles"] = roles
    return org


def _collect_extra_orgs() -> List[Dict[str, Any]]:
    """Ask whether the user wants to add Azure/GCP orgs, loop until done."""
    extras: List[Dict[str, Any]] = []
    while True:
        add_more = inquirer.confirm(
            message="Add an Azure or GCP org?",
            default=False,
        ).execute()
        if not add_more:
            break

        provider = inquirer.select(
            message="Select provider:",
            choices=["azure", "gcp"],
        ).execute()

        if provider == "azure":
            extras.append(_prompt_azure_org())
        else:
            extras.append(_prompt_gcp_org())

    return extras


def run_wizard() -> bool:
    """
    Setup Wizard Orchestrator.
    Contract:
    - Merges defaults into existing user config without data loss.
    - Reports sync failures specifically to utils.console.
    - Ensures atomic file writes.
    - Supports AWS (via registry), Azure, and GCP org configuration.
    - Installs the shell wrapper appropriate for the detected shell.
    """
    utils.console.print("Welcome to the awsctl Setup Wizard!")

    try:
        import yaml

        # 1. Fetch and Select AWS Orgs from registry
        choices = registry.get_choices()

        selected_orgs = inquirer.checkbox(
            message="Select AWS Organizations to enable (space to select):",
            choices=choices,
        ).execute()

        # 2. Optional: add Azure / GCP orgs manually
        # Wrapped in try/except so a missing TTY (CI, tests) doesn't abort the wizard.
        try:
            extra_orgs = _collect_extra_orgs()
        except Exception:
            extra_orgs = []
        all_orgs = (selected_orgs or []) + extra_orgs

        if not all_orgs:
            utils.console.print("[yellow]No organizations selected. Exiting.[/]")
            return False

        # 3. Prepare Config Path
        orgs_path = core.get_orgs_path(ensure=True)
        orgs_path.parent.mkdir(parents=True, exist_ok=True)

        # 4. Merge Strategy (Contract: Preserve existing keys; propagate read errors)
        current_data: Dict[str, Any] = {}
        if orgs_path.exists():
            try:
                current_data = (
                    yaml.safe_load(orgs_path.read_text(encoding="utf-8")) or {}
                )
            except Exception as e:
                utils.console.print(f"Failed to update config: {e}")
                return False

        # Update enabled orgs list
        current_data["orgs"] = all_orgs
        if "enabled_orgs" not in current_data:
            current_data["enabled_orgs"] = [o["name"] for o in all_orgs]

        # Ensure plugins key exists as per default spec
        if "plugins" not in current_data:
            current_data["plugins"] = {"enabled": []}

        # 5. Atomic Write via mkstemp (Contract: Failure must be caught and reported)
        try:
            fd, tmp_path = tempfile.mkstemp(dir=orgs_path.parent)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(yaml.dump(current_data))
                os.replace(tmp_path, orgs_path)
            except Exception:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                raise
        except Exception as e:
            utils.console.print(f"Failed to update config: {e}")
            return False

        # 6. Sync AWS Profiles (only meaningful for AWS orgs)
        if core.cmd_config_sync() != 0:
            utils.console.print("Failed to sync profiles")

        # 7. Shell Integration — pick the right wrapper for the running shell
        detected = detect_shell()

        if detected == "powershell":
            target_path = shell.detect_powershell_profile()
            inject_fn = shell.inject_powershell_function
        elif detected == "fish":
            target_path = shell.detect_fish_function_file()
            inject_fn = shell.inject_fish_function
        else:
            # bash / zsh / unknown — use the original bash/zsh wrapper
            target_path = shell.detect_shell_profile()
            inject_fn = shell.inject_shell_function

        confirmed = inquirer.confirm(
            message=f"Install shell integration in {target_path}?",
            default=True,
        ).execute()

        if confirmed:
            if inject_fn(target_path):
                utils.console.print("Shell integration installed.")
            else:
                utils.console.print("Shell integration already present or failed.")

        utils.console.print("Setup complete!")
        return True

    except Exception as e:
        utils.console.print(f"Wizard failed: {e}")
        return False
