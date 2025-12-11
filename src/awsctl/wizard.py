# file: src/awsctl/wizard.py
# SPDX-License-Identifier: MIT
"""
Interactive Setup Wizard.
Hand-holds the user through configuration without requiring prior knowledge.
"""

import os
import shutil
import tempfile

import yaml
from InquirerPy import inquirer
from rich.panel import Panel

from awsctl import config, core, registry, shell
from awsctl.utils import ForceStderr, console

# [CONFIG] Internal Documentation URL
CONFLUENCE_URL = "https://beyondtrust.atlassian.net/wiki/x/CgD9qw"


def run_wizard() -> bool:
    console.clear()
    console.print(
        Panel.fit(
            "[bold green]Welcome to awsctl![/]\n\n"
            "This wizard will configure your AWS SSO environment.\n"
            "No copying or pasting required.",
            title="Setup Wizard",
            border_style="green",
        )
    )

    # 1. Config Check & Creation
    config_path = config.get_orgs_path(ensure=True)

    if not config_path.exists():
        try:
            default_content = config.sample_orgs_yaml()
            config_path.write_text(default_content, encoding="utf-8")
            console.print(
                f"[success]✅ Created default configuration at {config_path}[/]"
            )
        except Exception as e:
            console.print(f"[error]Failed to create config: {e}[/]")
            return False

    # 2. Check for Manual Setup Requirement
    current_registry = registry.get_registry()
    needs_manual_config = False

    # Logic: If only the placeholder exists, the user hasn't pasted their config yet.
    if (
        len(current_registry) == 1
        and current_registry[0]["name"] == "manual-setup-required"
    ):
        needs_manual_config = True

    if needs_manual_config:
        console.print("\n[bold yellow]⚠️  Configuration Required[/]")
        console.print("This version of awsctl requires manual configuration.\n")

        console.print(f"🔗 [link={CONFLUENCE_URL}]{CONFLUENCE_URL}[/]\n")

        console.print("1. Open the URL above.")
        console.print("2. Copy the YAML configuration block.")
        console.print(f"3. Paste it into: [cyan]{config_path}[/]")
        console.print("   (Overwrite the existing file)\n")

        with ForceStderr():
            # [FIX] Suppress mypy error for dynamic attribute access
            proceed = inquirer.confirm(  # type: ignore
                message=f"I have updated {config_path}. Continue setup?", default=True
            ).execute()

            if not proceed:
                console.print("[red]Aborted.[/]")
                return False

    # 3. Reload & Select Orgs
    console.print("\n[bold cyan]Step 1: Organization Subscriptions[/]")

    # Reload registry to pick up user edits
    current_choices = registry.get_choices()

    # Fail if still empty
    if not current_choices or (
        len(current_choices) == 1
        and current_choices[0]["value"]["name"] == "manual-setup-required"
    ):
        console.print("[red]Error: No valid organizations found in config.[/]")
        console.print(f"Please check {config_path} and try again.")
        return False

    console.print("[dim]Select the organizations you need access to:[/]")

    with ForceStderr():
        selected_orgs = inquirer.checkbox(  # type: ignore
            message="Available Orgs:",
            choices=current_choices,
            instruction="(Use Space to select multiple, Enter to confirm)",
            validate=lambda result: len(result) > 0,
            invalid_message="Please select at least one organization.",
        ).execute()

    # 4. Update Enabled List
    try:
        # [FIX] Enforce UTF-8 reading to prevent UnicodeDecodeError on Windows (CP1252)
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        data["enabled_orgs"] = [org["name"] for org in selected_orgs]

        if "plugins" not in data:
            data["plugins"] = {"enabled": []}

        fd, tmp_path = tempfile.mkstemp(dir=config_path.parent, text=True)
        try:
            os.chmod(tmp_path, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                yaml.dump(data, f, sort_keys=False, default_flow_style=False)
            shutil.move(tmp_path, config_path)
            console.print(f"[success]✅ Configuration updated at {config_path}[/]")
        except Exception:
            os.remove(tmp_path)
            raise
    except Exception as e:
        console.print(f"[error]Failed to update config: {e}[/]")
        return False

    # 5. Bootstrap AWS CLI
    console.print("\n[bold cyan]Step 2: Bootstrapping AWS CLI[/]")
    try:
        core.cmd_config_sync()
    except Exception as e:
        console.print(f"[error]Failed to sync profiles: {e}[/]")

    # 6. Shell Integration
    console.print("\n[bold cyan]Step 3: Shell Integration[/]")
    try:
        rc_file = shell.detect_shell_profile()
        try:
            modified = shell.inject_shell_function(rc_file)
            if modified:
                console.print(f"[success]✅ Shell wrapper appended to {rc_file}[/]")
            else:
                console.print(f"✓ Shell wrapper already present in [dim]{rc_file}[/]")
        except Exception as e:
            console.print(f"[error]Error modifying {rc_file}: {e}[/]")
    except RuntimeError as e:
        console.print(f"[yellow]Skipping shell injection:[/yellow] {e}")

    # 7. Final Instructions
    console.print(
        Panel(
            "[bold green]Setup Complete![/]\n\n"
            "To activate the new tools, reload your shell:\n\n"
            f"    [bold white on black] source {rc_file} [/]\n\n"
            "Then login and switch contexts simply by typing:\n\n"
            f"    [bold]awsctl login --org {selected_orgs[0]['name']}[/]\n"
            "    [bold]awsctl switch[/]",
            title="⚠️  Action Required",
            border_style="yellow",
            expand=False,
        )
    )
    return True
