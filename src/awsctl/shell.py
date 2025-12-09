# file: src/awsctl/shell.py
# SPDX-License-Identifier: MIT
"""
Shell integration logic.
Detects the user's shell (Bash/Zsh) and injects the 'awsctl' wrapper function.
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path

# [FIX] PYBH-0111: Pass --check-strategy FIRST to ensure it's parsed as a global flag
# [FIX] PYBH-0057: Robust output parsing (tail -n1)
# [SEC-FIX] Fail closed if strategy check fails to prevent token leakage
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
    """
    Heuristic to find the correct rc file.
    """
    home = Path.home()

    # We rely on SHELL env var for detection, then fall back to file existence checks
    shell_env = os.environ.get("SHELL", "").lower()

    if "zsh" in shell_env:
        return home / ".zshrc"

    # Assume Bash/generic POSIX for fallback
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
    """
    Appends the wrapper function to the rc_file.
    [FIX] PYBH-0041: Atomic write with chown to prevent root lockout
    [FIX] PYBH-0050: Handle missing SUDO_UID
    [FIX] PYBH-0068: Resolve symlinks to avoid destroying them during move
    """
    # Resolve symlinks so we operate on the physical file
    target_file = rc_file.resolve()

    is_posix = sys.platform != "win32"
    is_root = is_posix and hasattr(os, "geteuid") and os.geteuid() == 0

    # Safely get SUDO_UID, defaulting to -1 (failure)
    try:
        sudo_uid = int(os.environ.get("SUDO_UID", -1))
        sudo_gid = int(os.environ.get("SUDO_GID", -1))
    except ValueError:
        sudo_uid = -1
        sudo_gid = -1

    # Ensure target exists before read
    if not target_file.exists():
        try:
            target_file.touch(0o600)
            if is_root and sudo_uid != -1:
                os.chown(target_file, sudo_uid, sudo_gid)
        except OSError:
            pass

    try:
        # [FIX] Explicit utf-8 is required on Windows
        content = target_file.read_text(encoding="utf-8")
    except FileNotFoundError:
        content = ""

    if "AWSCTL SHELL INTEGRATION (v2.2-SECURE)" in content:
        return False

    # Atomic Append
    # Create temp file in same directory to allow atomic move
    fd, tmp_path = tempfile.mkstemp(dir=target_file.parent, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            if content and not content.endswith("\n"):
                f.write("\n")
            f.write("\n")
            f.write(AWSCTL_WRAPPER)

        # Match permissions
        if is_root and sudo_uid != -1:
            os.chown(tmp_path, sudo_uid, sudo_gid)

        # Preserve mode if possible, else 644/600
        try:
            st = target_file.stat()
            os.chmod(tmp_path, st.st_mode)
        except OSError:
            os.chmod(tmp_path, 0o644)

        # Atomic swap
        shutil.move(tmp_path, target_file)
        return True

    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise

    return True
