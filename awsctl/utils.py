# file: awsctl/utils.py
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from colorama import Fore, Style


def run(cmd: Sequence[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a command capturing output. Raise on failure if check=True."""
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if check and proc.returncode != 0:
        raise RuntimeError(f"Command failed ({proc.returncode}): {' '.join(cmd)}\n{proc.stderr}")
    return proc


def success(msg: str) -> None:
    print(Fore.GREEN + msg + Style.RESET_ALL)


def info(msg: str) -> None:
    print(Fore.CYAN + msg + Style.RESET_ALL)


def warn(msg: str) -> None:
    print(Fore.YELLOW + msg + Style.RESET_ALL)


def error(msg: str) -> None:
    print(Fore.RED + msg + Style.RESET_ALL, file=sys.stderr)


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


# -------------------------
# Summary
# - Added warn() and ensure_dir() helpers for CLI flows.
# -------------------------
