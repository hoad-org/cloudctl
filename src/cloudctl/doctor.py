"""
cloudctl.doctor — system health diagnostics.

All check_* functions return Tuple[bool, str]:
  (True,  <detail message>)   on success
  (False, <detail message>)   on failure
"""

import concurrent.futures
import json
import os
import platform
import shutil
import ssl
import socket
import subprocess
import sys
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

    marker = "CLOUDCTL SHELL INTEGRATION"

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

    return False, "Shell integration not found — run 'cloudctl init' to install"


def check_permissions() -> Tuple[bool, str]:
    """Return (True, msg) if ~/.cloudctl is accessible and user-owned."""
    from pathlib import Path

    cloudctl_dir = Path.home() / ".cloudctl"
    if not cloudctl_dir.exists():
        return True, "~/.cloudctl not yet created (OK)"

    # Windows has no getuid / st_uid — skip ownership check.
    if platform.system() == "Windows" or not hasattr(os, "getuid"):
        return True, "User owned (Windows)"

    try:
        st = cloudctl_dir.stat()
        uid = os.getuid()
        if st.st_uid == uid:
            return True, "User owned"
        return False, f"Owned by uid {st.st_uid}, current uid {uid}"
    except Exception as e:
        return False, str(e)


def check_time_sync() -> Tuple[bool, str]:
    """Return (True, 'Synced') if we can reach a time endpoint, else warn.

    Uses a thread with a hard 3-second wall-clock timeout so filtered firewall
    rules (which cause the OS TCP stack to retry beyond the socket timeout) can
    never cause this check to hang.
    """

    def _connect() -> None:
        # Port 443 on time.cloudflare.com — unlikely to be blocked on corporate networks.
        sock = socket.create_connection(("time.cloudflare.com", 443), timeout=2)
        sock.close()

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            executor.submit(_connect).result(timeout=3)
        return True, "Synced"
    except Exception:
        # Not a hard failure — clock may still be fine; just can't verify.
        return True, "Could not reach time server (network may be restricted)"


def check_network_ssl() -> Tuple[bool, str]:
    """Return (True, 'Reachable') if TLS 1.2+ to sts.amazonaws.com succeeds."""
    try:
        ctx = ssl.create_default_context()
        # Enforce TLS 1.2 minimum (disable older versions)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        with ctx.wrap_socket(
            socket.create_connection(("sts.amazonaws.com", 443), timeout=10),
            server_hostname="sts.amazonaws.com",
        ):
            pass
        return True, "Reachable (TLS 1.2+)"
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


def _cloud_cli_checks() -> list:
    """Presence of the non-AWS cloud CLIs (gcloud, az).

    A multi-cloud tool's doctor shouldn't be AWS-only. Absence is ADVISORY —
    you may only use AWS — so a missing gcloud/az never counts as a hard issue.
    Returns [(label, ok, detail), ...].
    """
    out = []
    for tool in ("gcloud", "az"):
        ok, detail = check_tool(tool)
        # shutil.which may be mocked to return a non-str in tests; coerce so the
        # detail is always a printable/serialisable string.
        out.append((f"{tool} CLI", bool(ok), str(detail)))
    return out


def run_diagnostics(
    fix_path: Optional[bool] = None, fmt: Optional[str] = None
) -> int:
    """
    Run all health checks and print a formatted report.

    Returns 0 if everything is OK, 1 if any issues were detected.

    With ``fmt="json"`` (or a non-TTY when ``fmt`` is unset) a machine-parseable
    summary of every check is emitted to STDOUT instead of the Rich table, so an
    agent can consume the results.
    """
    import cloudctl.doctor as _self  # self-reference so monkeypatching works

    console = utils.console
    issues: list = []
    # Structured record of every check for the JSON summary.
    records: list = []

    def _record(name, ok, detail, advisory=False):
        records.append(
            {"name": name, "ok": bool(ok), "detail": str(detail), "advisory": advisory}
        )

    console.print("\n[bold cyan]System Health Check[/bold cyan]")
    console.print("=" * 50)

    # --- AWS CLI ---
    console.print("\n[bold]AWS CLI[/bold]")
    ok, msg = _self.check_aws_version()
    _print_check(console, "AWS CLI version", ok, msg)
    _record("AWS CLI version", ok, msg)
    if not ok:
        issues.append(msg)

    # --- Cloud CLIs (multi-cloud presence; advisory) ---
    console.print("\n[bold]Cloud CLIs[/bold]")
    for label, cli_ok, detail in _cloud_cli_checks():
        _print_check(console, label, cli_ok, detail)
        _record(label, cli_ok, detail, advisory=True)

    # --- Shell Integration ---
    console.print("\n[bold]Shell Integration[/bold]")
    ok, msg = _self.check_shell_integration()
    _print_check(console, "Shell wrapper", ok, msg)
    _record("Shell wrapper", ok, msg)
    if not ok:
        issues.append(msg)

    # --- Permissions ---
    ok, msg = _self.check_permissions()
    _print_check(console, "Permissions", ok, msg)
    _record("Permissions", ok, msg)
    if not ok:
        issues.append(msg)

    # --- Network / SSL ---
    ok, msg = _self.check_network_ssl()
    _print_check(console, "Network / SSL", ok, msg)
    _record("Network / SSL", ok, msg)
    if not ok:
        issues.append(msg)

    # --- Time sync ---
    ok, msg = _self.check_time_sync()
    _print_check(console, "Time sync", ok, msg)
    _record("Time sync", ok, msg, advisory=True)
    # Time sync is advisory only — don't count as failure

    # --- Configuration ---
    console.print("\n[bold]Configuration[/bold]")
    try:
        cfg = config.load_raw_config()
        # Support both the dict schema (organizations: {...}) and the legacy
        # list schema (orgs: [...]) — same resolution config.get_org() uses.
        orgs_data = cfg.get("organizations", {}) or cfg.get("orgs", [])
        org_count = len(orgs_data)
        _print_check(console, "Config file", True, f"{org_count} org(s) configured")
        _record("Config file", True, f"{org_count} org(s) configured")
    except Exception as e:
        _print_check(console, "Config file", False, str(e))
        _record("Config file", False, str(e))
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
            _record("Config schema", False, "; ".join(schema_errors))
            for err in schema_errors:
                console.print(f"    [red]•[/red] {err}")
            issues.extend(schema_errors)
        else:
            _print_check(console, "Config schema", True, "Valid")
            _record("Config schema", True, "Valid")
    except Exception as e:
        _print_check(console, "Config schema", False, str(e))
        _record("Config schema", False, str(e))
        issues.append(str(e))

    # --- WSL Performance (only when running in WSL) ---
    if is_wsl():
        console.print("\n[bold]WSL Performance[/bold]")
        ok, msg = _self.check_wsl_performance()
        _print_check(console, "AWS binary", ok, msg)
        _record("AWS binary (WSL)", ok, msg)
        if not ok:
            issues.append(msg)

    # Resolve the effective output format: explicit wins; otherwise json when
    # stdout is not a TTY (agent context). The Rich table above renders to
    # stderr, so a JSON summary on stdout is a clean, separable stream.
    if fmt not in ("table", "json"):
        try:
            fmt = "table" if sys.stdout.isatty() else "json"
        except Exception:
            fmt = "json"

    if fmt == "json":
        # Machine-readable summary on STDOUT (plain print → capturable, never
        # Rich-decorated). Advisory failures do not flip `ok` / the exit code.
        print(
            json.dumps(
                {
                    "ok": not issues,
                    "issue_count": len(issues),
                    "checks": records,
                    "issues": issues,
                }
            )
        )
        return 0 if not issues else 1

    # --- Summary (table mode) ---
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
