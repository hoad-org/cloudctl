import os
from typing import Optional


def detect_shell() -> Optional[str]:
    """
    Detect the user's shell in a deterministic way.

    Precedence:
    1. $PSModulePath → powershell  (always set inside PS/pwsh sessions)
    2. $SHELL basename             (bash, zsh, fish)
    3. $_ basename                 (fallback for bash / zsh)
    """
    # PowerShell sets $PSModulePath unconditionally on startup.
    if os.environ.get("PSModulePath"):
        return "powershell"

    shell_env = os.environ.get("SHELL")
    if shell_env:
        name = os.path.basename(shell_env)
        if name in ("bash", "zsh", "fish"):
            return name

    last = os.environ.get("_")
    if last:
        name = os.path.basename(last)
        if name in ("bash", "zsh", "fish"):
            return name

    return None


def is_wsl() -> bool:
    try:
        with open("/proc/version", encoding="utf-8") as fh:
            return "microsoft" in fh.read().lower()
    except OSError:
        return False
