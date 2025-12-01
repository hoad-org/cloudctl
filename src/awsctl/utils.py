# file: src/awsctl/utils.py
# SPDX-License-Identifier: MIT
"""
awsctl.utils
------------
Shared utilities for UI, process execution, and cross-platform compatibility.
"""
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.theme import Theme

# Global debug state
_DEBUG_MODE = False


def set_debug(enabled: bool) -> None:
    global _DEBUG_MODE
    _DEBUG_MODE = enabled


def debug_print(msg: str) -> None:
    if _DEBUG_MODE:
        console.print(f"[dim][DEBUG] {msg}[/]")


# Define a consistent corporate theme
custom_theme = Theme(
    {
        "info": "cyan",
        "warning": "yellow",
        "error": "bold red",
        "success": "bold green",
        "header": "bold white on blue",
    }
)

# Global console instance.
# CRITICAL: We write to stderr by default to keep stdout clean for eval.
# [FIX] Disable pager environment to prevent ":q" windows on long output.
console = Console(theme=custom_theme, stderr=True, _environ={"PAGER": "cat"})


def run(
    cmd: List[str],
    check: bool = True,
    env: Optional[Dict[str, str]] = None,
    timeout: Optional[float] = 10.0,  # Force default timeout
) -> subprocess.CompletedProcess[str]:
    """
    Run a command securely with manual timeout enforcement.
    Uses manual polling to guarantee process termination.
    """
    if _DEBUG_MODE:
        debug_print(f"Exec: {' '.join(cmd)}")

    start_time = time.time()

    # Use Popen to control the lifecycle manually
    with subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    ) as proc:
        try:
            # If no timeout (rare), just block
            if timeout is None:
                stdout, stderr = proc.communicate()
            else:
                # Manual Polling Loop
                while proc.poll() is None:
                    if time.time() - start_time > timeout:
                        proc.kill()  # Force Kill (SIGKILL)
                        if _DEBUG_MODE:
                            debug_print(f"Command timed out after {timeout}s (KILLED)")
                        raise RuntimeError(
                            f"Command timed out after {timeout}s: {' '.join(cmd)}"
                        )
                    time.sleep(0.1)

                # Process finished, read remaining output
                stdout, stderr = proc.communicate()

            # [FIX] Check inside try block to catch and re-raise properly
            if check and proc.returncode != 0:
                if _DEBUG_MODE:
                    debug_print(f"Command failed (rc={proc.returncode}): {stderr}")
                raise subprocess.CalledProcessError(
                    proc.returncode, cmd, output=stdout, stderr=stderr
                )

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Command failed: {e.stderr}") from e

        except Exception as e:
            proc.kill()
            raise e

        return subprocess.CompletedProcess(
            args=cmd,
            returncode=proc.returncode,
            stdout=stdout,
            stderr=stderr,
        )


def is_wsl() -> bool:
    """Detect if running inside Windows Subsystem for Linux."""
    if "microsoft-standard" in platform.uname().release:
        return True
    return False


def open_browser(url: str) -> None:
    """Robust browser opener."""
    try:
        if is_wsl():
            if shutil.which("wslview"):
                subprocess.run(["wslview", url], check=True)
                return
            subprocess.run(["explorer.exe", url], check=True)
            return

        import webbrowser

        webbrowser.open(url)
    except Exception as e:
        console.print(f"[warning]Could not open browser automatically: {e}[/]")
        console.print(f"Please open this URL manually: [link={url}]{url}[/]")


def print_kv_table(title: str, data: Dict[str, Any]) -> None:
    """Render a simple Key-Value table."""
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="bold cyan")
    table.add_column("Value", style="white")

    for k, v in data.items():
        table.add_row(str(k), str(v))

    console.print(Panel(table, title=f"[bold]{title}[/]", border_style="blue"))


def ensure_dir(p: Path) -> None:
    """Create directory with 700 permissions."""
    p.mkdir(parents=True, exist_ok=True)
    if sys.platform != "win32":
        p.chmod(0o700)
