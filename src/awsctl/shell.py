# file: src/awsctl/shell.py
# SPDX-License-Identifier: MIT
"""
Shell integration logic.
Detects the user's shell (Bash/Zsh) and injects the 'awsctl' wrapper function.
"""
import os
from pathlib import Path

# The Trojan Horse Wrapper
# This function intercepts the user's command and decides whether to
# just run it (EXEC) or capture output and eval it (EVAL).
AWSCTL_WRAPPER = """
# AWSCTL SHELL INTEGRATION (v1.3.0)
# Installed by `awsctl setup`
awsctl() {
    # 1. Check if the core binary is available
    if ! command -v _awsctl_bin >/dev/null 2>&1; then
        echo "Error: _awsctl_bin not found. Is the python package installed?" >&2
        return 1
    fi

    # 2. Ask the binary which strategy to use for these arguments
    # We ignore standard error here to keep the check silent
    local strategy
    strategy=$(_awsctl_bin "$@" --check-strategy 2>/dev/null)
    local check_rc=$?
    # Fallback: If strategy check fails, assume EXEC (safer than evaling random output)
    if [[ $check_rc -ne 0 ]] || [[ -z "$strategy" ]]; then
        _awsctl_bin "$@"
        return $?
    fi

    # 3. Strategy: EXEC (Standard command, e.g., 'doctor', 'status')
    if [[ "$strategy" == "EXEC" ]]; then
        _awsctl_bin "$@"
        return $?
    fi

    # 4. Strategy: EVAL (Context switch, e.g., 'use', 'switch', 'login --account')
    if [[ "$strategy" == "EVAL" ]]; then
        local output
        # Capture stdout for eval, let stderr pass through for UI
        output=$(_awsctl_bin "$@")
        local rc=$?
        if [[ $rc -eq 0 ]]; then
            eval "$output"
        else
            # If failed, output might contain error text rather than exports,
            # but usually the binary writes errors to stderr.
            # We print output just in case it contains info.
            echo "$output"
        fi
        return $rc
    fi

    # Unknown strategy fallback
    _awsctl_bin "$@"
}
"""


def detect_shell_profile() -> Path:
    """
    Heuristic to find the correct rc file.
    Prioritizes Zsh if present in SHELL env, otherwise checks standard Bash startups.
    """
    shell = os.environ.get("SHELL", "")
    home = Path.home()

    # 1. Zsh check
    if "zsh" in shell:
        return home / ".zshrc"

    # 2. Bash / POSIX startup order
    # Most logical place for user functions is .bashrc, but login shells read others.
    candidates = [
        home / ".bash_profile",
        home / ".bash_login",
        home / ".profile",
        home / ".bashrc",
    ]

    for cand in candidates:
        if cand.exists():
            return cand

    # Default fallback if nothing exists
    return home / ".bashrc"


def inject_shell_function(rc_file: Path) -> bool:
    """
    Appends the wrapper function to the rc_file if not already present.
    Returns True if modifications were made.
    """
    if not rc_file.exists():
        rc_file.touch(0o600)

    content = rc_file.read_text(encoding="utf-8")

    if "AWSCTL SHELL INTEGRATION" in content:
        return False

    with rc_file.open("a", encoding="utf-8") as f:
        f.write("\n")
        f.write(AWSCTL_WRAPPER)

    return True
