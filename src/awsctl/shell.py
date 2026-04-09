import os
import tempfile
from pathlib import Path

# Module-level HOME so tests can monkeypatch it.
HOME = Path.home()

# ---------------------------------------------------------------------------
# bash / zsh wrapper
# ---------------------------------------------------------------------------

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
            & $awsctlBin --eval @args | Out-File -FilePath $tmp -Encoding utf8
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
    set -l mutating switch use logout
    set -l first (count $argv > /dev/null; and echo $argv[1]; or echo '')
    if contains -- $first $mutating
        set -l tmp (mktemp)
        command awsctl --eval $argv > $tmp
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
    # Use module-level HOME so tests can monkeypatch it.
    home = HOME
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
