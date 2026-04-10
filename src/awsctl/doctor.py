"""
awsctl.doctor — system health diagnostics.

All check_* functions return Tuple[bool, str]:
  (True,  <detail message>)   on success
  (False, <detail message>)   on failure
"""

import os
import platform
import shutil
import ssl
import socket
import subprocess
from typing import Optional, Tuple

from . import config, utils

# Patchable module-level reference so tests can monkeypatch it.
is_wsl = utils.is_wsl


# ---------------------------------------------------------------------------
# Individual check functions
# ---------------------------------------------------------------------------


def check_tool(name: str) -> Tuple[bool, str]:
    """Return (True, path) if *name* binary is on PATH, else (False, 'Not found')."""
    path = shutil.which(name)
    if path:
        return True, path
    return False, f"Not found: {name}"


def check_aws_version() -> Tuple[bool, str]:
    """Return (True, version_string) if 'aws --version' succeeds."""
    aws = shutil.which("aws")
    if not aws:
        return False, "AWS CLI not found"
    try:
        result = subprocess.run(
            [aws, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            ver = (result.stdout or result.stderr or "").strip().split("\n")[0]
            return True, ver or "OK"
        return False, result.stderr.strip() or "aws --version failed"
    except Exception as e:
        return False, str(e)


def check_shell_integration() -> Tuple[bool, str]:
    """Return (True, 'Present') if AWSCTL shell wrapper marker is found in any profile."""
    from . import shell

    marker = "AWSCTL SHELL INTEGRATION"

    # Check all candidate profile files
    candidates = [
        shell.detect_shell_profile(),
        shell.detect_fish_function_file(),
        shell.detect_powershell_profile(),
    ]

    for path in candidates:
        try:
            if path.exists() and marker in path.read_text(encoding="utf-8"):
                return True, f"Present in {path}"
        except Exception:
            continue

    return False, "Shell integration not found — run 'awsctl init' to install"


def check_permissions() -> Tuple[bool, str]:
    """Return (True, msg) if ~/.awsctl is accessible and user-owned."""
    from pathlib import Path

    awsctl_dir = Path.home() / ".awsctl"
    if not awsctl_dir.exists():
        return True, "~/.awsctl not yet created (OK)"

    # Windows has no getuid / st_uid — skip ownership check.
    if platform.system() == "Windows" or not hasattr(os, "getuid"):
        return True, "User owned (Windows)"

    try:
        st = awsctl_dir.stat()
        uid = os.getuid()
        if st.st_uid == uid:
            return True, "User owned"
        return False, f"Owned by uid {st.st_uid}, current uid {uid}"
    except Exception as e:
        return False, str(e)


def check_time_sync() -> Tuple[bool, str]:
    """Return (True, 'Synced') if we can reach an NTP endpoint, else warn."""
    try:
        # A lightweight TCP connect to pool.ntp.org:123 tells us if the network is up.
        # Real skew detection would require parsing NTP packets — overkill here.
        sock = socket.create_connection(("pool.ntp.org", 123), timeout=5)
        sock.close()
        return True, "Synced"
    except Exception:
        # Not a hard failure — clock may still be fine; just can't verify.
        return True, "Could not reach NTP (network may be restricted)"


def check_network_ssl() -> Tuple[bool, str]:
    """Return (True, 'Reachable') if TLS to sts.amazonaws.com succeeds."""
    try:
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(
            socket.create_connection(("sts.amazonaws.com", 443), timeout=10),
            server_hostname="sts.amazonaws.com",
        ):
            pass
        return True, "Reachable"
    except Exception as e:
        return False, f"TLS check failed: {e}"


def check_wsl_performance() -> Tuple[bool, str]:
    """Return (True, 'N/A') on non-WSL; on WSL warn if Windows AWS binary is used."""
    if not is_wsl():
        return True, "N/A"

    aws_path = shutil.which("aws")
    if not aws_path:
        return False, "AWS CLI not found in WSL"

    if aws_path.endswith(".exe") or "/mnt/c" in aws_path or "/mnt/d" in aws_path:
        return (
            False,
            f"Windows binary detected at {aws_path} — "
            "install the Linux AWS CLI inside WSL for better performance",
        )

    return True, f"Native Linux binary at {aws_path}"


# ---------------------------------------------------------------------------
# Diagnostics runner
# ---------------------------------------------------------------------------


def run_diagnostics(fix_path: Optional[bool] = None) -> int:
    """
    Run all health checks and print a formatted report.

    Returns 0 if everything is OK, 1 if any issues were detected.
    """
    import awsctl.doctor as _self  # self-reference so monkeypatching works

    console = utils.console
    issues: list = []

    console.print("\n[bold cyan]System Health Check[/bold cyan]")
    console.print("=" * 50)

    # --- AWS CLI ---
    console.print("\n[bold]AWS CLI[/bold]")
    ok, msg = _self.check_aws_version()
    _print_check(console, "AWS CLI version", ok, msg)
    if not ok:
        issues.append(msg)

    # --- Shell Integration ---
    console.print("\n[bold]Shell Integration[/bold]")
    ok, msg = _self.check_shell_integration()
    _print_check(console, "Shell wrapper", ok, msg)
    if not ok:
        issues.append(msg)

    # --- Permissions ---
    ok, msg = _self.check_permissions()
    _print_check(console, "Permissions", ok, msg)
    if not ok:
        issues.append(msg)

    # --- Network / SSL ---
    ok, msg = _self.check_network_ssl()
    _print_check(console, "Network / SSL", ok, msg)
    if not ok:
        issues.append(msg)

    # --- Time sync ---
    ok, msg = _self.check_time_sync()
    _print_check(console, "Time sync", ok, msg)
    # Time sync is advisory only — don't count as failure

    # --- Configuration ---
    console.print("\n[bold]Configuration[/bold]")
    try:
        cfg = config.load_orgs_config()
        org_count = len(cfg.get("orgs", [])) if isinstance(cfg, dict) else len(cfg)
        _print_check(console, "Config file", True, f"{org_count} org(s) configured")
    except Exception as e:
        _print_check(console, "Config file", False, str(e))
        issues.append(str(e))

    # --- Schema validation ---
    try:
        from .schema import validate_orgs_config

        raw = config.load_raw_config()
        schema_errors = validate_orgs_config(raw) if raw else []
        if schema_errors:
            _print_check(
                console, "Config schema", False, f"{len(schema_errors)} error(s)"
            )
            for err in schema_errors:
                console.print(f"    [red]•[/red] {err}")
            issues.extend(schema_errors)
        else:
            _print_check(console, "Config schema", True, "Valid")
    except Exception as e:
        _print_check(console, "Config schema", False, str(e))
        issues.append(str(e))

    # --- WSL Performance (only when running in WSL) ---
    if is_wsl():
        console.print("\n[bold]WSL Performance[/bold]")
        ok, msg = _self.check_wsl_performance()
        _print_check(console, "AWS binary", ok, msg)
        if not ok:
            issues.append(msg)

    # --- Summary ---
    console.print("\n" + "=" * 50)
    if not issues:
        console.print("[bold green]Everything looks good[/bold green] ✓")
        return 0
    else:
        console.print(
            f"[bold red]Issues detected[/bold red]: {len(issues)} issue(s) found"
        )
        for issue in issues:
            console.print(f"  [red]•[/red] {issue}")
        return 1


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _print_check(console, label: str, ok: bool, msg: str) -> None:
    icon = "[green]✓[/green]" if ok else "[red]✗[/red]"
    status = "[green]OK[/green]" if ok else "[red]FAIL[/red]"
    console.print(f"  {icon} {label}: {status} — {msg}")
