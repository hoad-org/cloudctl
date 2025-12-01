# file: src/awsctl/cool_features.py
# SPDX-License-Identifier: MIT
"""
awsctl.cool_features
--------------------
Hidden 'Matrix' mode visualizer.
"""
import random  # nosec B311 (Used for visual flair/random delay, not crypto)
import time

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table


def run_matrix_login() -> None:
    console = Console()

    table = Table(show_header=False, box=None, expand=True)
    table.add_column("Status", style="green")

    steps = [
        "Initializing quantum uplink...",
        "Bypassing mainframe firewall...",
        "Injecting SSO payload...",
        "Decrypting STS tokens...",
        "Establishing secure tunnel to us-east-1...",
        "Compiling neural net...",
        "Optimizing route metrics...",
        "Access Granted.",
    ]

    with Live(
        Panel(table, title="[bold green]AWSCTL SYSTEM LINK[/]", border_style="green"),
        refresh_per_second=12,
    ) as live:
        for step in steps:
            delay = random.uniform(0.1, 0.4)  # nosec B311
            time.sleep(delay)
            table.add_row(f"[bold green]>[/] {step}")
            live.update(
                Panel(
                    table,
                    title="[bold green]AWSCTL SYSTEM LINK[/]",
                    border_style="green",
                )
            )

    console.print("\n[bold white on green] SYSTEM READY [/]\n")
