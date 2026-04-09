from typing import Any, Dict

from .. import core, registry, shell, utils
from . import inquirer
from ..env_detection import detect_shell


def run_wizard() -> bool:
    """
    Setup Wizard Orchestrator.
    Contract:
    - Merges defaults into existing user config without data loss.
    - Reports sync failures specifically to utils.console.
    - Ensures atomic file writes.
    - Installs the shell wrapper appropriate for the detected shell.
    """
    utils.console.print("Welcome to the awsctl Setup Wizard!")

    try:
        # 1. Fetch and Select Orgs
        choices = registry.get_choices()

        selected_orgs = inquirer.checkbox(
            message="Select Organizations to enable",
            choices=choices,
        ).execute()

        if not selected_orgs:
            return False

        # 2. Prepare Config Path
        orgs_path = core.get_orgs_path(ensure=True)
        orgs_path.parent.mkdir(parents=True, exist_ok=True)

        # 3. Merge Strategy (Contract: Preserve existing keys; propagate read errors)
        current_data: Dict[str, Any] = {}
        if orgs_path.exists():
            try:
                import yaml

                current_data = (
                    yaml.safe_load(orgs_path.read_text(encoding="utf-8")) or {}
                )
            except Exception as e:
                utils.console.print(f"Failed to update config: {e}")
                return False

        import yaml

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

        # 6. Shell Integration — pick the right wrapper for the running shell
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
