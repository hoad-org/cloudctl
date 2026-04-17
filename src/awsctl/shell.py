import os
import tempfile
from pathlib import Path

# Module-level HOME so tests can monkeypatch it.
HOME = Path.home()
# _ORIGINAL_HOME tracks what HOME was at import time so detect_shell_profile
# can distinguish "test patched shell.HOME" from "test patched pathlib.Path.home".
_ORIGINAL_HOME = HOME

# ---------------------------------------------------------------------------
# bash / zsh wrapper
# ---------------------------------------------------------------------------

# Contract: Exact markers and content for shell wrapper.
AWSCTL_WRAPPER = """# AWSCTL SHELL INTEGRATION
awsctl() {
    local first="${1:-}" needs_eval=0 arg
    case "$first" in
        switch|use|logout) needs_eval=1 ;;
        login)
            for arg in "$@"; do
                case "$arg" in --account|-a|--role|-r|--region|-R) needs_eval=1; break ;; esac
            done ;;
    esac
    if [[ $needs_eval -eq 1 ]]; then
        local tmp exit_code
        tmp=$(mktemp)
        AWSCTL_WRAPPER_ACTIVE=1 command awsctl --eval "$@" > "$tmp"
        exit_code=$?
        if [[ $exit_code -eq 0 ]]; then
            source "$tmp" || exit_code=$?
        fi
        rm -f "$tmp"
        return $exit_code
    else
        AWSCTL_WRAPPER_ACTIVE=1 command awsctl "$@"
    fi
}"""

# ---------------------------------------------------------------------------
# PowerShell wrapper (Windows native + cross-platform pwsh)
# ---------------------------------------------------------------------------

AWSCTL_PS_WRAPPER = r"""# AWSCTL SHELL INTEGRATION
function awsctl {
    $mutating = @('switch', 'use', 'logout')
    $first = if ($args.Count -gt 0) { $args[0] } else { '' }
    $loginWithFlags = $first -eq 'login' -and (
        $args -contains '--account' -or $args -contains '-a' -or
        $args -contains '--role'    -or $args -contains '-r' -or
        $args -contains '--region'  -or $args -contains '-R'
    )
    if ($mutating -contains $first -or $loginWithFlags) {
        $tmp = [System.IO.Path]::GetTempFileName()
        try {
            $awsctlBin = (Get-Command awsctl -CommandType Application -ErrorAction Stop).Source
            $env:AWSCTL_WRAPPER_ACTIVE = '1'
            & $awsctlBin --eval @args | Out-File -FilePath $tmp -Encoding utf8
            Remove-Item env:AWSCTL_WRAPPER_ACTIVE -ErrorAction SilentlyContinue
            $ec = $LASTEXITCODE
            if ($ec -eq 0) {
                Get-Content $tmp | ForEach-Object {
                    if ($_ -match '^export ([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
                        [System.Environment]::SetEnvironmentVariable(
                            $Matches[1], $Matches[2], 'Process')
                        Set-Item -Path "env:$($Matches[1])" -Value $Matches[2]
                    } elseif ($_ -match '^unset ([A-Za-z_][A-Za-z0-9_]*)') {
                        [System.Environment]::SetEnvironmentVariable(
                            $Matches[1], $null, 'Process')
                        Remove-Item -Path "env:$($Matches[1])" -ErrorAction SilentlyContinue
                    }
                }
            }
            return $ec
        } finally {
            Remove-Item $tmp -ErrorAction SilentlyContinue
        }
    } else {
        $awsctlBin = (Get-Command awsctl -CommandType Application -ErrorAction Stop).Source
        & $awsctlBin @args
        return $LASTEXITCODE
    }
}"""

# ---------------------------------------------------------------------------
# Fish wrapper
# ---------------------------------------------------------------------------

AWSCTL_FISH_WRAPPER = r"""# AWSCTL SHELL INTEGRATION
function awsctl
    set -l first (count $argv > /dev/null; and echo $argv[1]; or echo '')
    set -l needs_eval 0
    if contains -- $first switch use logout
        set needs_eval 1
    else if test "$first" = login
        if contains -- --account $argv; or contains -- -a $argv
            or contains -- --role $argv; or contains -- -r $argv
            or contains -- --region $argv; or contains -- -R $argv
            set needs_eval 1
        end
    end
    if test $needs_eval -eq 1
        set -l tmp (mktemp)
        AWSCTL_WRAPPER_ACTIVE=1 command awsctl --eval $argv > $tmp
        set -l ec $status
        if test $ec -eq 0
            while read -l line
                if string match -qr '^export ([^=]+)=(.+)$' -- $line
                    set -gx (string replace -r '^export ([^=]+)=.*' '$1' -- $line) \
                             (string replace -r '^export [^=]+=(.*)' '$1' -- $line)
                else if string match -qr '^unset (.+)$' -- $line
                    set -e (string replace -r '^unset ' '' -- $line)
                end
            end < $tmp
        end
        rm -f $tmp
        return $ec
    else
        command awsctl $argv
    end
end"""


def detect_shell_profile() -> Path:
    # Priority:
    # 1. Module-level HOME if it was patched by a test (differs from _ORIGINAL_HOME)
    #    — test_env_detection.py patches shell.HOME directly
    # 2. Path.home() dynamically (allows pathlib.Path.home to be patched)
    #    — test_detect_shell_fallback patches pathlib.Path.home
    import pathlib

    if HOME != _ORIGINAL_HOME:
        # Module-level HOME has been patched by a test (e.g. test_env_detection.py)
        home = HOME
    else:
        # Use dynamically-resolved home so pathlib.Path.home patches take effect
        home = pathlib.Path.home()
    shell_env = os.environ.get("SHELL", "")
    if "zsh" in shell_env:
        return home / ".zshrc"
    # Search order defined by test_detect_shell_profile_fallbacks.
    for f in [".bash_profile", ".bashrc", ".profile"]:
        if (home / f).exists():
            return home / f
    return home / ".bashrc"


def detect_powershell_profile() -> Path:
    """Return the PowerShell $PROFILE path for the current user."""
    ps_profile = os.environ.get("PROFILE")
    if ps_profile:
        return Path(ps_profile)
    home = Path.home()
    if os.name == "nt":
        return home / "Documents" / "PowerShell" / "Microsoft.PowerShell_profile.ps1"
    return home / ".config" / "powershell" / "Microsoft.PowerShell_profile.ps1"


def detect_fish_function_file() -> Path:
    """Return the fish function file path for the awsctl function."""
    config_fish = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
    return Path(config_fish) / "fish" / "functions" / "awsctl.fish"


# ---------------------------------------------------------------------------
# bash / zsh — original implementation preserved exactly for test contracts
# ---------------------------------------------------------------------------


def inject_shell_function(path: Path) -> bool:
    # If read fails (e.g. mocked FileNotFoundError), treat as empty — still inject.
    try:
        content = path.read_text(encoding="utf-8") if path.exists() else ""
    except Exception:
        content = ""

    # Idempotence Check.
    if "AWSCTL SHELL INTEGRATION" in content:
        return False

    # Atomic Write — let OSError from mkstemp propagate so callers detect disk-full.
    fd, temp_path = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            # Three newlines when content has no trailing \n:
            #   end current line (\n) + blank line (\n) + blank separator (\n) + wrapper
            spacer = "\n\n\n" if content and not content.endswith("\n") else ""
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


def remove_shell_function(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        content = path.read_text(encoding="utf-8")
        # Only remove if the exact wrapper is present; user-modified versions
        # return False to avoid silently mangling a customized profile.
        if AWSCTL_WRAPPER not in content:
            return False

        new_content = content.replace(AWSCTL_WRAPPER, "").strip()
        path.write_text(new_content, encoding="utf-8")
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# PowerShell — same atomic-write pattern as bash/zsh
# ---------------------------------------------------------------------------


def inject_powershell_function(path: Path) -> bool:
    try:
        content = path.read_text(encoding="utf-8") if path.exists() else ""
        if "AWSCTL SHELL INTEGRATION" in content:
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                spacer = "\n\n" if content and not content.endswith("\n") else ""
                f.write(content + spacer + AWSCTL_PS_WRAPPER + "\n")
            if path.exists():
                os.chmod(temp_path, path.stat().st_mode)
            os.replace(temp_path, path)
            return True
        except Exception:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise
    except Exception:
        return False


def remove_powershell_function(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        content = path.read_text(encoding="utf-8")
        if "AWSCTL SHELL INTEGRATION" not in content:
            return False
        new_content = content.replace(AWSCTL_PS_WRAPPER, "").strip()
        path.write_text(new_content, encoding="utf-8")
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Fish — dedicated function file, not appended to rc
# ---------------------------------------------------------------------------


def inject_fish_function(path: Path) -> bool:
    try:
        if path.exists() and "AWSCTL SHELL INTEGRATION" in path.read_text(
            encoding="utf-8"
        ):
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(AWSCTL_FISH_WRAPPER + "\n", encoding="utf-8")
        return True
    except Exception:
        return False


def remove_fish_function(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        if "AWSCTL SHELL INTEGRATION" not in path.read_text(encoding="utf-8"):
            return False
        path.unlink()
        return True
    except Exception:
        return False
