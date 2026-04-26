import os
import platform
import shutil
import signal
import subprocess
import sys
import webbrowser
from typing import Any, Dict, List, Optional

from rich.console import Console

# Contract: console must not be bound to stderr=True or the test mock fails to intercept.
console = Console()
stdout_console = Console()
which = shutil.which


class ForceStderr:
    def __enter__(self):
        self._stdout = sys.stdout
        sys.stdout = sys.stderr
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout = self._stdout


def is_wsl() -> bool:
    try:
        if os.path.exists("/proc/version"):
            with open("/proc/version", "r") as f:
                if "microsoft" in f.read().lower():
                    return True
    except (FileNotFoundError, PermissionError):
        pass
    return "microsoft" in platform.uname().release.lower()


def is_headless() -> bool:
    return os.environ.get("AWSCTL_HEADLESS") == "1"


def set_debug(val: bool) -> None:
    if val:
        os.environ["AWSCTL_DEBUG"] = "1"
    else:
        os.environ["AWSCTL_DEBUG"] = "0"


def debug_print(msg: str) -> None:
    if os.environ.get("AWSCTL_DEBUG") == "1":
        console.print(f"DEBUG: {msg}")


def print_kv_table(title: str, data: Dict[str, Any]) -> None:
    console.print(f"--- {title} ---")
    for k, v in data.items():
        console.print(f"{k}: {v}")


def ensure_dir(path: Any) -> None:
    os.makedirs(path, exist_ok=True)


def _redact_cmd(cmd: List[str]) -> List[str]:
    redacted = []
    for a in cmd:
        if any(k in a.lower() for k in ["token", "secret", "password"]):
            redacted.append("[REDACTED]")
        else:
            redacted.append(a)
    return redacted


def run(
    cmd: List[str],
    check: bool = True,
    capture: bool = True,
    timeout: Optional[float] = None,
) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {"capture_output": capture, "text": True}
    if timeout is not None:
        kwargs["timeout"] = timeout

    try:
        res = subprocess.run(cmd, **kwargs)
        if check and res.returncode != 0:
            raise RuntimeError(f"Command failed: {res.stderr or ''}")
        return {
            "stdout": res.stdout or "",
            "stderr": res.stderr or "",
            "returncode": res.returncode,
        }
    except subprocess.TimeoutExpired:
        # Only attempt process-group kill when we explicitly set a timeout
        # (avoids killing the test runner when a mock raises TimeoutExpired).
        if timeout is not None and os.name != "nt":
            try:
                pgid = os.getpgid(0)
                os.killpg(pgid, signal.SIGKILL)
            except OSError:
                pass
        console.print("timed out")
        raise RuntimeError("Command timed out")
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Execution failure: {e}")


def open_browser(url: str) -> None:
    if is_headless():
        return
    if is_wsl():
        wv = shutil.which("wslview")
        if wv:
            subprocess.run([wv, url], check=True)
        else:
            subprocess.run(["explorer.exe", url], check=False)
        return
    try:
        if not webbrowser.open(url):
            raise Exception("No Browser")
    except Exception as e:
        console.print(f"Browser open failed: {e}")
