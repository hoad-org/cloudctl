# file: docs/SHELL_INTEGRATION.md
# Shell Integration & Context Bridge — v2.8.1

## 1. Overview

`awsctl` uses a shell function wrapper to safely:

1.  Invoke the internal binary (`_awsctl_bin`)
2.  Determine the execution strategy (`EXEC` vs `EVAL`)
3.  Modify the environment **only** when safe

## 2. Fail-Closed Design

The wrapper logic is defensive. It verifies:

- Strategy output exists
- Exit code is 0
- Strategy is exactly `EXEC` or `EVAL`

If any check fails, the wrapper exits with an error and **does not** evaluate output. This prevents partial/corrupt credential exports.

## 3. The Wrapper Code (Bash/Zsh)

If `awsctl setup` cannot modify your rc file, copy this function manually:

> awsctl() {
>     if ! command -v _awsctl_bin >/dev/null 2>&1; then
>         echo "Error: _awsctl_bin not found." >&2
>         return 1
>     fi
>
>     local raw_output
>     raw_output=$(_awsctl_bin --check-strategy "$@")
>     local check_rc=$?
>
>     if [[ $check_rc -ne 0 ]] || [[ -z "$raw_output" ]]; then
>         echo "Error: Failed to determine execution strategy." >&2
>         return 1
>     fi
>
>     local strategy
>     strategy=$(echo "$raw_output" | tail -n1)
>
>     if [[ "$strategy" == "EXEC" ]]; then
>         _awsctl_bin "$@"
>         return $?
>     fi
>
>     if [[ "$strategy" == "EVAL" ]]; then
>         local output
>         output=$(_awsctl_bin "$@")
>         local rc=$?
>         if [[ $rc -eq 0 ]]; then
>             eval "$output"
>         else
>             echo "$output"
>         fi
>         return $rc
>     fi
>
>     echo "Error: Unknown strategy '$strategy'" >&2
>     return 1
> }

## 4. Fish Shell Support

**Status:** Manual Setup Required.

`awsctl setup` will **abort** if it detects Fish shell to prevent corrupting `~/.bashrc`.
Fish users must manually create `~/.config/fish/functions/awsctl.fish`:

> function awsctl
>     set -l outcome (_awsctl_bin --check-strategy $argv)
>     if test $status -ne 0
>         echo "Error: Strategy check failed."
>         return 1
>     end
>
>     set -l strategy (echo $outcome | tail -n1)
>
>     if test "$strategy" = "EXEC"
>         _awsctl_bin $argv
>     else if test "$strategy" = "EVAL"
>         set -l output (_awsctl_bin $argv)
>         if test $status -eq 0
>             for line in $output
>                 set -l kv (string split -m1 = (string replace "export " "" $line))
>                 set -gx $kv[1] (string trim --chars \"\' $kv[2])
>             end
>         else
>             echo $output
>         end
>     else
>         _awsctl_bin $argv
>     end
> end

## 5. PowerShell

**Status:** Not Supported.

Users on Windows **must** use WSL2 (Ubuntu/Debian) to run `awsctl`.
