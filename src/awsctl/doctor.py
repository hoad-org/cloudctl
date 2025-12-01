# file: src/awsctl/doctor.py
# SPDX-License-Identifier: MIT
"""
awsctl.doctor
-------------
Diagnostics and environment health checks.
"""
from __future__ import annotations

import shutil
from typing import Tuple

from rich.table import Table

from awsctl import config
from awsctl.utils import console, is_wsl


def check_tool(name: str) -> Tuple[bool, str]:
    """Check if a binary exists."""
    path = shutil.which(name)
    if path:
        return True, path
    return False, "Not found"


def run_diagnostics(fix_path: bool = False) -> int:  # noqa: ARG001
    """Run system checks with a rich UI."""

    table = Table(title="System Health Check", expand=True)
    table.add_column("Component", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Details", style="dim")

    overall_status = 0

    with console.status("[bold green]Running diagnostics...[/]"):
        # 1. Config Check
        try:
            cfg = config.load_orgs_config()
            count = len(cfg.get("orgs", []))
            table.add_row("Configuration", "✅", f"Valid ({count} orgs enabled)")
        except Exception as e:
            table.add_row("Configuration", "❌", f"Error: {e}")
            overall_status = 1

        # 2. Dependencies
        required_tools = ["aws", "git", "python3"]
        if is_wsl():
            # Check for wslview (part of wslu)
            required_tools.append("wslview")

        for tool in required_tools:
            found, details = check_tool(tool)
            if found:
                table.add_row(f"Binary: {tool}", "✅", details)
            else:
                table.add_row(f"Binary: {tool}", "❌", "Missing from PATH")
                overall_status = 1

        # 3. Environment
        if is_wsl():
            table.add_row("Environment", "🐧", "WSL Detected")
        else:
            table.add_row("Environment", "💻", "Native POSIX")

    console.print(table)

    if overall_status == 0:
        console.print("\n[bold green]Everything looks good![/]")
    else:
        console.print("\n[bold red]Issues detected.[/]")
        if is_wsl() and not shutil.which("wslview"):
            console.print(
                "[yellow]Hint: Install 'wslu' in WSL for browser support: `sudo apt install wslu`[/]"
            )

    return overall_status
