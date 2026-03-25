import os
from typing import Optional


def detect_shell() -> Optional[str]:
    """
    Detect the user's shell in a deterministic way.

    Precedence:
    1. $SHELL basename
    2. $_ (last executed command)
    """
    shell = os.environ.get("SHELL")
    if shell:
        name = os.path.basename(shell)
        if name in ("bash", "zsh"):
            return name

    last = os.environ.get("_")
    if last:
        name = os.path.basename(last)
        if name in ("bash", "zsh"):
            return name

    return None


def is_wsl() -> bool:
    try:
        with open("/proc/version", encoding="utf-8") as fh:
            return "microsoft" in fh.read().lower()
    except OSError:
        return False
