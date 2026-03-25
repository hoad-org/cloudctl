from typing import Any, Dict

import inquirer
import yaml

import awsctl.config as config
import awsctl.core as core
import awsctl.registry_loader as registry
import awsctl.shell as shell
import awsctl.utils as utils


def run_wizard() -> bool:
    """
    Setup Wizard Orchestrator.
    Contract:
    - Merges defaults into existing user config without data loss.
    - Reports sync failures specifically to utils.console.
    - Ensures atomic file writes.
    """
    utils.console.print("Welcome to the awsctl Setup Wizard!")

    try:
        # 1. Fetch and Select Orgs
        registry_data = registry.fetch_registry()
        choices = registry.get_choices(registry_data)

        questions = [
            inquirer.Checkbox(
                "orgs",
                message="Select AWS Organizations to enable",
                choices=choices,
            )
        ]
        answers = inquirer.prompt(questions)
        if not answers:
            return False

        selected_orgs = answers["orgs"]

        # 2. Prepare Config Path
        orgs_path = config.get_orgs_path(ensure=True)

        # 3. Merge Strategy (Contract: Preserve existing keys)
        current_data: Dict[str, Any] = {}
        if orgs_path.exists():
            try:
                current_data = (
                    yaml.safe_load(orgs_path.read_text(encoding="utf-8")) or {}
                )
            except Exception:
                current_data = {}

        # Update enabled orgs list
        current_data["orgs"] = selected_orgs
        if "enabled_orgs" not in current_data:
            current_data["enabled_orgs"] = [o["name"] for o in selected_orgs]

        # Ensure plugins key exists as per default spec
        if "plugins" not in current_data:
            current_data["plugins"] = {"enabled": []}

        # 4. Atomic Write (Contract: Failure must be caught and reported)
        try:
            orgs_path.write_text(yaml.dump(current_data), encoding="utf-8")
        except Exception as e:
            utils.console.print(f"Failed to update config: {e}")
            return False

        # 5. Sync Profiles (Contract: Call core sync and check return code)
        if core.cmd_config_sync() != 0:
            utils.console.print("Failed to sync profiles")

        # 6. Shell Integration
        profile_path = shell.detect_shell_profile()
        confirm = [
            inquirer.Confirm(
                "shell",
                message=f"Install shell integration in {profile_path}?",
                default=True,
            )
        ]
        answers_confirm = inquirer.prompt(confirm)
        if answers_confirm and answers_confirm.get("shell"):
            if shell.inject_shell_function(profile_path):
                utils.console.print("Shell integration installed.")
            else:
                utils.console.print("Shell integration already present or failed.")

        utils.console.print("Setup complete!")
        return True

    except Exception as e:
        utils.console.print(f"Wizard failed: {e}")
        return False
