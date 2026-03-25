import os
import tempfile
from pathlib import Path

# Contract: Exact markers and content for shell wrapper.
AWSCTL_WRAPPER = """# AWSCTL SHELL INTEGRATION
awsctl() {
    local tmp=$(mktemp)
    command awsctl --eval "$@" > "$tmp"
    local exit_code=$?
    source "$tmp"
    rm -f "$tmp"
    return $exit_code
}"""


def detect_shell_profile() -> Path:
    # Contract: Dynamic resolution of home for monkeypatching.
    home = Path.home()
    shell_env = os.environ.get("SHELL", "")
    if "zsh" in shell_env:
        return home / ".zshrc"
    # Search order defined by test_detect_shell_profile_fallbacks.
    for f in [".bash_profile", ".bashrc", ".profile"]:
        if (home / f).exists():
            return home / f
    return home / ".bashrc"


def inject_shell_function(path: Path) -> bool:
    try:
        content = path.read_text(encoding="utf-8") if path.exists() else ""
        # Idempotence Check.
        if "AWSCTL SHELL INTEGRATION" in content:
            return False

        # Atomic Write Path to satisfy primitive failure tests (mkstemp).
        fd, temp_path = tempfile.mkstemp(dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                spacer = "\n\n" if content and not content.endswith("\n") else ""
                f.write(content + spacer + AWSCTL_WRAPPER + "\n")

            if path.exists():
                st = path.stat()
                os.chmod(temp_path, st.st_mode)
            os.replace(temp_path, path)
            return True
        except Exception:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise
    except Exception:
        return False


def remove_shell_function(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        content = path.read_text(encoding="utf-8")
        if "AWSCTL SHELL INTEGRATION" not in content:
            return False

        # Structural replacement based on exact wrapper content.
        new_content = content.replace(AWSCTL_WRAPPER, "").strip()
        path.write_text(new_content, encoding="utf-8")
        return True
    except Exception:
        return False
