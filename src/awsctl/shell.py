# file: src/awsctl/shell.py
# SPDX-License-Identifier: MIT
"""
Shell integration logic.
Detects the user's shell (Bash/Zsh) and injects the 'awsctl' wrapper function.
"""

import os
import shutil
import tempfile
from pathlib import Path

# The exact string we inject. Used for detection and removal.
AWSCTL_WRAPPER = """
# AWSCTL SHELL INTEGRATION (v2.2-SECURE)
awsctl() {
    if ! command -v _awsctl_bin >/dev/null 2>&1; then
        echo "Error: _awsctl_bin not found." >&2
        return 1
    fi

    local raw_output
    raw_output=$(_awsctl_bin --check-strategy "$@")
    local check_rc=$?
    # 🛡️ SECURITY FIX: Fail closed if strategy check fails.
    if [[ $check_rc -ne 0 ]] || [[ -z "$raw_output" ]]; then
        echo "Error: Failed to determine execution strategy." >&2
        return 1
    fi

    local strategy
    strategy=$(echo "$raw_output" | tail -n1)

    if [[ "$strategy" == "EXEC" ]]; then
        _awsctl_bin "$@"
        return $?
    fi

    if [[ "$strategy" == "EVAL" ]]; then
        local output
        output=$(_awsctl_bin "$@")
        local rc=$?
        if [[ $rc -eq 0 ]]; then
            eval "$output"
        else
            echo "$output"
        fi
        return $rc
    fi

    echo "Error: Unknown strategy '$strategy'" >&2
    return 1
}
"""


def detect_shell_profile() -> Path:
    """Heuristic to find the correct rc file."""
    home = Path.home()
    shell_env = os.environ.get("SHELL", "").lower()

    # [FIX] Explicitly detect Fish shell to prevent writing to .bashrc
    if "fish" in shell_env:
        raise RuntimeError(
            "Fish shell detected. Automatic injection is not supported.\n"
            "Please see docs/SHELL_INTEGRATION.md for manual setup instructions."
        )

    if "zsh" in shell_env:
        return home / ".zshrc"

    candidates = [
        home / ".bash_profile",
        home / ".bash_login",
        home / ".profile",
        home / ".bashrc",
    ]
    for cand in candidates:
        if cand.exists():
            return cand

    return home / ".bashrc"


def inject_shell_function(rc_file: Path) -> bool:
    """Appends the wrapper function to the rc_file."""
    target_file = rc_file.resolve()

    # Ensure target exists
    if not target_file.exists():
        try:
            target_file.touch(0o600)
        except OSError:
            pass

    try:
        content = target_file.read_text(encoding="utf-8")
    except FileNotFoundError:
        content = ""

    if "AWSCTL SHELL INTEGRATION" in content:
        return False

    # Atomic Append
    fd, tmp_path = tempfile.mkstemp(dir=target_file.parent, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            if content and not content.endswith("\n"):
                f.write("\n")
            f.write("\n")
            f.write(AWSCTL_WRAPPER)

        # Preserve permissions roughly
        try:
            st = target_file.stat()
            os.chmod(tmp_path, st.st_mode)
        except OSError:
            os.chmod(tmp_path, 0o644)

        shutil.move(tmp_path, target_file)
        return True

    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def remove_shell_function(rc_file: Path) -> bool:
    """Removes the awsctl wrapper function from the rc_file."""
    target_file = rc_file.resolve()
    if not target_file.exists():
        return False

    try:
        content = target_file.read_text(encoding="utf-8")
    except Exception:
        return False

    if "AWSCTL SHELL INTEGRATION" not in content:
        return False

    # Naive but safe removal: exact string match
    # We strip whitespace to handle auto-formatting drift
    clean_content = content.replace(AWSCTL_WRAPPER, "")

    # If naive failed (user edited it?), try a fallback or just leave it.
    if len(clean_content) == len(content):
        # Fallback: Try removing with surrounding newlines
        clean_content = content.replace("\n" + AWSCTL_WRAPPER, "")

    if len(clean_content) == len(content):
        return False  # Could not cleanly remove

    target_file.write_text(clean_content, encoding="utf-8")
    return True
