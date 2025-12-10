# file: src/awsctl/doctor.py
# SPDX-License-Identifier: MIT
"""
awsctl.doctor
-------------
Diagnostics and environment health checks.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Tuple

import requests
from rich.table import Table

from awsctl import config, shell
from awsctl.utils import console, is_wsl


def check_tool(name: str) -> Tuple[bool, str]:
    path = shutil.which(name)
    if path:
        return True, path
    if name == "git":
        try:
            subprocess.run(
                ["git", "--version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True, "Found via shell"
        except FileNotFoundError:
            pass
    return False, "Not found"


def check_aws_version() -> Tuple[bool, str]:
    try:
        result = subprocess.run(["aws", "--version"], capture_output=True, text=True)
        output = result.stdout + result.stderr
        match = re.search(r"aws-cli/(\d+)\.", output)
        if match:
            major = int(match.group(1))
            return (True, f"v{major}") if major >= 2 else (False, f"v{major} (Legacy)")
        return False, "Unknown format"
    except Exception:
        return False, "Failed to run"


def check_shell_integration() -> Tuple[bool, str]:
    rc_file = shell.detect_shell_profile()
    if not rc_file.exists():
        return False, f"Missing: {rc_file}"
    try:
        content = rc_file.read_text(encoding="utf-8", errors="ignore")
        return (
            (True, f"Present in {rc_file.name}")
            if "AWSCTL SHELL INTEGRATION" in content
            else (False, "Missing")
        )
    except Exception:
        return False, "Read error"


def check_permissions() -> Tuple[bool, str]:
    # [FIX] os.getuid() is POSIX-only. Skip check on Windows.
    if os.name == "nt":
        return True, "Skipped (Windows)"

    paths = [config.get_orgs_path(ensure=False), Path.home() / ".awsctl"]
    uid = os.getuid()
    issues = [p.name for p in paths if p.exists() and p.stat().st_uid != uid]
    if issues:
        return False, f"Root owned: {', '.join(issues)}"
    return True, "User owned"


def check_time_sync() -> Tuple[bool, str]:
    """Check against AWS date header to detect clock skew (common in WSL)."""
    try:
        # Use a publicly available AWS endpoint (S3 usually reliable)
        resp = requests.head("https://aws.amazon.com", timeout=3)
        date_header = resp.headers.get("Date")
        if not date_header:
            return True, "Skipped (No header)"

        # Parse RFC 1123 date
        # Example: Tue, 09 Dec 2025 10:00:00 GMT
        server_time = datetime.strptime(
            date_header, "%a, %d %b %Y %H:%M:%S %Z"
        ).replace(tzinfo=timezone.utc)
        local_time = datetime.now(timezone.utc)

        diff = abs((server_time - local_time).total_seconds())
        if diff > 120:  # 2 minutes tolerance
            return False, f"Skew: {int(diff)}s"
        return True, f"Synced (<{int(diff)}s)"
    except Exception:
        return True, "Skipped (Network)"


def check_network_ssl() -> Tuple[bool, str]:
    """Check connectivity and SSL trust."""
    try:
        # [FIX] Use generic AWS endpoint instead of hardcoded internal URL
        url = "https://aws.amazon.com"
        requests.head(url, timeout=3)
        return True, "Reachable & Trusted"
    except requests.exceptions.SSLError:
        return False, "SSL Cert Error (Corp Proxy?)"
    except requests.exceptions.ConnectionError:
        return False, "Connection Failed"
    except Exception as e:
        return False, str(e)


def check_wsl_performance() -> Tuple[bool, str]:
    if not is_wsl():
        return True, "N/A"

    aws_path = shutil.which("aws")
    if not aws_path:
        return False, "AWS CLI not found"

    # Check if resolving to a windows executable in /mnt/c
    if aws_path.endswith(".exe") or "/mnt/c/" in aws_path.lower():
        return False, "Using Windows binary (Slow!)"

    return True, "Native Linux Binary"


def run_diagnostics(fix_path: bool = False) -> int:
    table = Table(title="System Health Check", expand=True)
    table.add_column("Component", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Details", style="dim")

    overall_status = 0

    with console.status("[bold green]Running diagnostics...[/]"):
        # Permissions
        ok, msg = check_permissions()
        table.add_row("Permissions", "✅" if ok else "❌", msg)
        if not ok:
            overall_status = 1

        # Config
        try:
            c = len(config.load_orgs_config().get("orgs", []))
            table.add_row("Configuration", "✅", f"Valid ({c} orgs)")
        except Exception as e:
            table.add_row("Configuration", "❌", str(e))
            overall_status = 1

        # AWS CLI
        ok, msg = check_aws_version()
        table.add_row("AWS CLI", "✅" if ok else "❌", msg)
        if not ok:
            overall_status = 1

        # Shell
        ok, msg = check_shell_integration()
        table.add_row("Shell Integration", "✅" if ok else "❌", msg)
        if not ok:
            overall_status = 1

        # Network / SSL
        ok, msg = check_network_ssl()
        table.add_row("Network / SSL", "✅" if ok else "❌", msg)
        # Don't fail overall status for network, just warn

        # Time Sync
        ok, msg = check_time_sync()
        table.add_row("Time Sync", "✅" if ok else "❌", msg)
        if not ok:
            overall_status = 1

        # WSL Performance
        if is_wsl():
            ok, msg = check_wsl_performance()
            table.add_row("WSL Performance", "✅" if ok else "⚠️", msg)

        # Env
        table.add_row("OS Type", "💻", "WSL" if is_wsl() else "POSIX")

    console.print(table)

    if overall_status == 0:
        console.print("\n[bold green]Everything looks good![/]")
    else:
        console.print("\n[bold red]Issues detected.[/]")

        # Smart Hints
        if not check_shell_integration()[0]:
            console.print("[yellow]Hint: Run `awsctl setup` to install shell hooks.[/]")

        if not check_permissions()[0]:
            console.print("[yellow]Hint: Run `sudo chown -R $(id -un) ~/.awsctl`[/]")

        if not check_time_sync()[0] and is_wsl():
            console.print("[yellow]Hint: Clock skewed. Run `sudo hwclock -s`[/]")

        if not check_network_ssl()[0]:
            if sys.platform == "darwin":
                console.print("[yellow]Hint: SSL Error. Try exporting system certs:[/]")
                console.print(
                    "[dim]  security find-certificate -a -p /Library/Keychains/System.keychain > certs.pem[/]"
                )
                console.print("[dim]  export REQUESTS_CA_BUNDLE=$(pwd)/certs.pem[/]")

    if is_wsl() and not check_wsl_performance()[0]:
        console.print("[yellow]Hint: You are using the Windows AWS CLI inside WSL.[/]")
        console.print(
            "[dim]      This adds significant latency. Install the Linux version for speed.[/]"
        )

    return overall_status
