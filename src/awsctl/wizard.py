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

    # ---------------------------------------------------------
    # 1. Select Organizations
    # ---------------------------------------------------------
    console.print("\n[bold cyan]Step 1: Organization Subscriptions[/]")
    console.print("[dim]Select the organizations you need access to:[/]")

    with ForceStderr():
        selected_orgs = inquirer.checkbox(  # type: ignore[attr-defined]
            message="Available Orgs:",
            choices=registry.get_choices(),
            instruction="(Use Space to select multiple, Enter to confirm)",
            validate=lambda result: len(result) > 0,
            invalid_message="Please select at least one organization.",
        ).execute()

    # ---------------------------------------------------------
    # 2. Build Configuration
    # ---------------------------------------------------------
    enabled_names = [org["name"] for org in selected_orgs]

    final_yaml = {
        "enabled_orgs": enabled_names,
        "plugins": {"enabled": []},
    }

    # ---------------------------------------------------------
    # 3. Write Config
    # ---------------------------------------------------------
    config_path = config.get_orgs_path(ensure=True)

    if config_path.exists():
        console.print(f"\n[yellow]Configuration already exists at {config_path}[/]")

        with ForceStderr():
            should_overwrite = inquirer.confirm(
                message="Overwrite existing configuration?", default=False
            ).execute()  # type: ignore[attr-defined]

        if not should_overwrite:
            console.print("[red]Aborted.[/]")
            return False

    # 🛡️ SECURITY FIX: Atomic open with restricted permissions (0600)
    # [FIX] PYBH-0046: Use temp file and move to prevent data loss on crash
    try:
        fd, tmp_path = tempfile.mkstemp(dir=config_path.parent, text=True)
        try:
            os.chmod(tmp_path, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                yaml.dump(final_yaml, f, sort_keys=False, default_flow_style=False)

            shutil.move(tmp_path, config_path)
            console.print(f"[success]✅ Configuration written to {config_path}[/]")
        except Exception:
            os.remove(tmp_path)
            raise
    except Exception as e:
        console.print(f"[error]Failed to write config: {e}[/]")
        return False

    # ---------------------------------------------------------
    # 4. Bootstrap AWS CLI
    # ---------------------------------------------------------
    console.print("\n[bold cyan]Step 2: Bootstrapping AWS CLI[/]")
    try:
        core.cmd_config_sync()
    except Exception as e:
        console.print(f"[error]Failed to sync profiles: {e}[/]")

    # ---------------------------------------------------------
    # 5. Shell Integration
    # ---------------------------------------------------------
    console.print("\n[bold cyan]Step 3: Shell Integration[/]")
    rc_file = shell.detect_shell_profile()

    try:
        modified = shell.inject_shell_function(rc_file)
        if modified:
            console.print(f"[success]✅ Shell wrapper appended to {rc_file}[/]")
        else:
            console.print(f"✓ Shell wrapper already present in [dim]{rc_file}[/]")
    except Exception as e:
        console.print(f"[error]Error modifying {rc_file}: {e}[/]")

    # ---------------------------------------------------------
    # 6. Final Instructions
    # ---------------------------------------------------------
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
