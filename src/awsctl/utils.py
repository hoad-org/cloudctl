# file: src/awsctl/utils.py
# SPDX-License-Identifier: MIT
"""
awsctl.utils
------------
Shared utilities for UI, process execution, and cross-platform compatibility.
"""

from __future__ import annotations

import os
import platform
import shutil
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, TextIO

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.theme import Theme

# Global debug state
_DEBUG_MODE = False

# Global TTY Handle (Singleton)
_TTY_HANDLE: Optional[TextIO] = None


def set_debug(enabled: bool) -> None:
    global _DEBUG_MODE
    _DEBUG_MODE = enabled


def _redact_cmd(cmd: List[str]) -> str:
    """
    [FIX] PYBH-0035: Redact sensitive arguments from debug logs.
    """
    SENSITIVE = {"--access-token", "--session-token", "sessionToken"}
    out = []
    skip = False
    for arg in cmd:
        if skip:
            out.append("[REDACTED]")
            skip = False
            continue
        if arg in SENSITIVE:
            out.append(arg)
            skip = True
            continue
        out.append(arg)
    return " ".join(out)


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

# Global console instance (stderr)
console = Console(theme=custom_theme, stderr=True)


class LazyStdoutConsole:
    """
    [FIX] PYBH-0036: Lazy proxy for stdout console.
    This ensures that if sys.stdout is swapped (e.g. by secure_stdout),
    the console writes to the NEW stream, not the old captured fd.
    """

    def __getattr__(self, name: str) -> Any:
        # Create a fresh console bound to the current sys.stdout
        _c = Console(theme=custom_theme, file=sys.stdout)
        return getattr(_c, name)


# Export the lazy console
stdout_console = LazyStdoutConsole()


class ForceStderr:
    """
    Context manager to force stdout to use the TTY explicitly.
    """

    def __enter__(self) -> ForceStderr:
        global _TTY_HANDLE

        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except (OSError, AttributeError):
            pass

        self.original_stdout_fd = -1
        self.saved_stdout_fd = -1
        self.original_stdout_obj = sys.stdout

        try:
            self.original_stdout_fd = sys.stdout.fileno()
            self.saved_stdout_fd = os.dup(self.original_stdout_fd)
        except (OSError, AttributeError):
            pass

        target_obj = sys.stderr
        target_fd = sys.stderr.fileno()

        try:
            if os.isatty(2):
                if _TTY_HANDLE is None or _TTY_HANDLE.closed:
                    # [FIX] Windows does not have /dev/tty. Use CON: instead.
                    dev_tty = "CON:" if sys.platform == "win32" else "/dev/tty"
                    try:
                        _TTY_HANDLE = open(dev_tty, "w", buffering=1, encoding="utf-8")
                    except OSError:
                        # Fallback if special device fails
                        pass

                if _TTY_HANDLE:
                    target_obj = _TTY_HANDLE
                    target_fd = _TTY_HANDLE.fileno()
        except OSError:
            pass

        if self.original_stdout_fd != -1:
            try:
                os.dup2(target_fd, self.original_stdout_fd)
            except OSError:
                pass

        sys.stdout = target_obj
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        try:
            sys.stdout.flush()
        except (OSError, AttributeError):
            pass

        sys.stdout = self.original_stdout_obj

        if self.saved_stdout_fd != -1 and self.original_stdout_fd != -1:
            try:
                os.dup2(self.saved_stdout_fd, self.original_stdout_fd)
                os.close(self.saved_stdout_fd)
            except OSError:
                pass


def run(
    cmd: List[str],
    check: bool = True,
    env: Optional[Dict[str, str]] = None,
    timeout: Optional[float] = 10.0,
    capture: bool = True,
) -> subprocess.CompletedProcess[str]:
    """
    Run a command securely with timeout enforcement.
    """
    if _DEBUG_MODE:
        # [FIX] PYBH-0035: Redact credentials in logs
        debug_print(f"Exec: {_redact_cmd(cmd)}")

    stdout_dest = subprocess.PIPE if capture else None
    stderr_dest = subprocess.PIPE if capture else None

    # [FIX] PYBH-0043: Only detach session if capturing.
    # Interactive commands (capture=False) need the TTY group.
    start_new_session = False
    if os.name == "posix" and capture:
        start_new_session = True

    try:
        with subprocess.Popen(
            cmd,
            stdout=stdout_dest,
            stderr=stderr_dest,
            text=True,
            env=env,
            start_new_session=start_new_session,
        ) as proc:
            try:
                stdout, stderr = proc.communicate(timeout=timeout)

            except subprocess.TimeoutExpired as e:
                if start_new_session:
                    try:
                        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                else:
                    proc.kill()

                if _DEBUG_MODE:
                    debug_print(f"Command timed out after {timeout}s (KILLED)")

                # [FIX] PYBH-0054: If check=False, return a failed process instead of crashing
                if not check:
                    return subprocess.CompletedProcess(
                        args=cmd,
                        returncode=124,  # Standard timeout exit code
                        stdout=e.stdout.decode() if isinstance(e.stdout, bytes) else "",
                        stderr=e.stderr.decode() if isinstance(e.stderr, bytes) else "",
                    )

                out_capture = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
                err_capture = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")

                raise RuntimeError(f"Command timed out after {timeout}s: {' '.join(cmd)}\n" f"Stdout: {out_capture.strip()}\n" f"Stderr: {err_capture.strip()}") from e

            except KeyboardInterrupt:
                # [FIX] PYBH-0022: Ensure child process group is killed on Ctrl+C
                if start_new_session:
                    try:
                        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                else:
                    proc.terminate()
                raise

            if check and proc.returncode != 0:
                err_msg = stderr if capture else "(Interactive output)"
                if _DEBUG_MODE:
                    debug_print(f"Command failed (rc={proc.returncode}): {err_msg}")
                raise subprocess.CalledProcessError(proc.returncode, cmd, output=stdout, stderr=stderr)

            return subprocess.CompletedProcess(
                args=cmd,
                returncode=proc.returncode,
                stdout=stdout,
                stderr=stderr,
            )

    except subprocess.CalledProcessError as e:
        msg = e.stderr if capture else "Process failed"
        raise RuntimeError(f"Command failed: {msg}") from e
    except Exception as e:
        raise e


def is_wsl() -> bool:
    if "microsoft-standard" in platform.uname().release:
        return True
    return False


def open_browser(url: str) -> None:
    try:
        if is_wsl():
            if shutil.which("wslview"):
                subprocess.run(["wslview", url], check=True)
                return

            subprocess.run(["explorer.exe", url], check=False)
            return

        import webbrowser

        webbrowser.open(url)
    except Exception as e:
        console.print(f"[warning]Could not open browser automatically: {e}[/]")
        console.print(f"Please open this URL manually: [link={url}]{url}[/]")


def print_kv_table(title: str, data: Dict[str, Any]) -> None:
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="bold cyan")
    table.add_column("Value", style="white")

    for k, v in data.items():
        table.add_row(str(k), str(v))

    console.print(Panel(table, title=f"[bold]{title}[/]", border_style="blue"))


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)
    if sys.platform != "win32":
        p.chmod(0o700)
