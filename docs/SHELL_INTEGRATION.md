# file: docs/SHELL_INTEGRATION.md
# awsctl Shell Integration Guide

This document explains how `awsctl` integrates with your shell (`bash`, `zsh`, `fish`) using the **Context Bridge** pattern.
`awsctl` must be installed as a **shell function wrapper** around an internal binary (commonly `_awsctl_bin`).
This wrapper decides when to simply run the binary and when to `eval` its output to update your current shell’s environment variables (for example, `AWS_ACCESS_KEY_ID`, `AWS_SESSION_TOKEN`, `AWS_DEFAULT_REGION`).

---

## 1. The Mechanism (v2.7.0)

`awsctl` is not just a binary; it is a shell function wrapper.
When you run:

    awsctl switch

you are actually calling a **shell function** named `awsctl`.
That function:

1. Calls the internal binary `_awsctl_bin` with a special flag (`--check-strategy`) to determine how the command should run.
2. Reads the “strategy” result:
   - `EXEC` → run the binary normally (no environment modification).
   - `EVAL` → capture `export` statements and `eval` them into your current shell.
3. Applies the appropriate strategy.

This pattern allows `awsctl` to safely modify your environment variables **without** writing AWS credentials to disk.

### 1.1 The Wrapper Logic (Bash/Zsh)

Below is the hardened shell wrapper installed by `awsctl setup`:

    # AWSCTL SHELL INTEGRATION (v2.2-SECURE)
    awsctl() {
        # 1. Ensure the binary exists
        if ! command -v _awsctl_bin >/dev/null 2>&1; then
            echo "Error: _awsctl_bin not found." >&2
            return 1
        fi

        # 2. Ask the binary for the execution strategy
        local raw_output
        raw_output=$(_awsctl_bin --check-strategy "$@")
        local check_rc=$?

        # 🛡️ SECURITY FIX: Fail closed if strategy check fails.
        # Prevents secrets from being printed to stdout/history if the binary crashes.
        if [[ $check_rc -ne 0 ]] || [[ -z "$raw_output" ]]; then
            echo "Error: Failed to determine execution strategy." >&2
            return 1
        fi

        local strategy
        strategy=$(echo "$raw_output" | tail -n1)

        # 3. Strategy: EXEC (Pass-through)
        if [[ "$strategy" == "EXEC" ]]; then
            _awsctl_bin "$@"
            return $?
        fi

        # 4. Strategy: EVAL (Modify Environment)
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

Key points:

- `--check-strategy` allows the binary to decide if a command needs to modify the shell environment.
- If anything looks wrong (non-zero status or empty output), the wrapper **fails closed** and refuses to eval anything.

---

## 2. Installation

### 2.1 Automatic (Recommended)

Run the setup wizard:

    awsctl setup

The wizard will:

- Detect your shell (`bash` or `zsh`).
- Append the wrapper function to your shell configuration file:
  - `~/.bashrc` for bash, or
  - `~/.zshrc` for zsh.
- Ensure `_awsctl_bin` is discoverable on your `PATH` (typically `~/.local/bin` when installed via `pipx`).

You must reload your shell for changes to take effect:

    source ~/.zshrc   # or
    source ~/.bashrc

Confirm that `awsctl` is now a function:

    type awsctl

You should see:

    awsctl is a function

If you see something like `awsctl is /usr/bin/awsctl`, the wrapper is not loaded, and `switch` will not update your environment.

---

### 2.2 Manual Configuration

If you manage dotfiles manually (for example, with a dotfile manager or Git repo):

1. Copy the function definition from section **1.1** into your shell configuration file (`~/.bashrc` or `~/.zshrc`).
2. Ensure `_awsctl_bin` is on your `PATH`:

       ls ~/.local/bin/_awsctl_bin

3. Reload your shell:

       source ~/.zshrc
       # or
       source ~/.bashrc

4. Verify:

       type awsctl

---

## 3. Platform Support

### 3.1 Bash and Zsh

Status: ✅ **Fully supported**

- The wrapper in section **1.1** works natively in both bash and zsh.
- All environment exports are POSIX-style `export KEY=VALUE`.
- `awsctl` setup automates this for common configurations.

Typical files:

- Bash:
  - `~/.bashrc`
  - `~/.bash_profile` (may source `~/.bashrc`)
- Zsh:
  - `~/.zshrc`

Ensure your login shell sources the file where the wrapper is defined.

---

### 3.2 Fish Shell

Status: ⚠️ **Manual setup required**

Fish uses a different function and export syntax and does not support `eval` in the same way as bash/zsh.
To integrate with Fish, you must define a compatible wrapper.

Create or edit:

    ~/.config/fish/functions/awsctl.fish

Example wrapper:

    function awsctl
        # Ask for strategy
        set -l outcome (_awsctl_bin --check-strategy $argv)

        if test $status -ne 0
            echo "Error: Strategy check failed."
            return 1
        end

        set -l strategy (echo $outcome | tail -n1)

        if test "$strategy" = "EXEC"
            _awsctl_bin $argv
        else if test "$strategy" = "EVAL"
            set -l output (_awsctl_bin $argv)
            if test $status -eq 0
                # Naive parsing of 'export KEY=VAL' -> 'set -gx KEY VAL'
                for line in $output
                    set -l kv (string split -m1 = (string replace "export " "" $line))
                    # [FIX] PYBH-0025: Correctly trim both " and ' characters
                    set -gx $kv[1] (string trim --chars \"\' $kv[2])
                end
            else
                echo $output
            end
        else
            # Fallback: just run the binary
            _awsctl_bin $argv
        end
    end

Notes:

- This example assumes `_awsctl_bin` outputs simple `export KEY=VALUE` lines on `EVAL`.
- If additional diagnostics are printed to stdout, they may break the naive parsing. In that case:
  - Use `awsctl doctor` and logs to debug.
  - Coordinate with your platform team if stricter output isolation is required.

After defining the function:

    exec fish

or open a new Fish session, then verify:

    type awsctl

Fish should report `awsctl` as a function.

---

### 3.3 PowerShell / Windows

Status: ❌ **Not supported**

`awsctl` does not provide a native PowerShell integration layer and there are no plans to support it.
The recommended options are:

- Run `awsctl` inside **WSL2** (Ubuntu/Debian).
- Use a standard bash/zsh shell within WSL, with the wrapper from section **1.1**.

Typical setup:

1. Install WSL2 and a Linux distribution (for example, Ubuntu).
2. In WSL:

       pipx install "git+https://github.com/BT-IT-Infrastructure-CloudOps/awsctl.git@<version>"
       awsctl setup
       source ~/.bashrc   # or ~/.zshrc

3. Use `awsctl` from your WSL shell for AWS interactions.

---

## 4. Troubleshooting Shell Integration

### 4.1 `command not found: _awsctl_bin`

**Symptom:**

- Shell error when running `awsctl`: `command not found: _awsctl_bin`.

**Cause:**

- `_awsctl_bin` is not on your `PATH`.
- `pipx` has installed into `~/.local/bin`, but your shell does not include that directory in `PATH`.

**Fix:**

1. Verify the binary exists:

       ls ~/.local/bin/_awsctl_bin

2. If missing, reinstall:

       pipx install --force "git+https://github.com/BT-IT-Infrastructure-CloudOps/awsctl.git@<version>"

3. Ensure `~/.local/bin` is in your `PATH`.
   For example, in bash:

       export PATH="$HOME/.local/bin:$PATH"

   You can re-run:

       pipx ensurepath

4. Open a new terminal or reload your shell:

       source ~/.zshrc
       # or
       source ~/.bashrc

---

### 4.2 `awsctl switch` does not change my variables

**Symptom:**

- `awsctl switch` runs without error, but `env | grep AWS_` shows no changes.

**Cause:**

- The shell wrapper is not loaded, so you are running the binary directly.
- Or you executed `awsctl` in a subshell (script) rather than your interactive session.

**Fix:**

1. Check how `awsctl` is defined:

       type awsctl

   - If it says `awsctl is a function`, the wrapper is loaded.
   - If it prints a path (for example, `/usr/bin/awsctl`), you are calling the binary directly.

2. Reload your shell configuration:

       source ~/.zshrc
       # or
       source ~/.bashrc

3. If `awsctl` is still not a function, re-run the setup wizard:

       awsctl setup
       source ~/.zshrc   # or ~/.bashrc

4. Avoid running `awsctl switch` inside a subshell:

   Wrong (subshell, no effect on parent):

       ./myscript.sh

   Correct (runs in current shell):

       source myscript.sh

---

### 4.3 Infinite loop or recursion

**Symptom:**

- Running `awsctl` causes unexpected recursion or infinite loop behavior.

**Cause:**

- `_awsctl_bin` has been aliased or symlinked incorrectly.
- You manually aliased `awsctl` to `_awsctl_bin` or vice versa.

**Fix:**

1. Remove any custom aliases:

       unalias awsctl 2>/dev/null || true
       unalias _awsctl_bin 2>/dev/null || true

2. Ensure that:
   - `awsctl` is a function defined as in section **1.1**.
   - `_awsctl_bin` is an executable binary on your `PATH`.

3. Reload your shell config and verify:

       source ~/.zshrc   # or ~/.bashrc
       type awsctl
       command -v _awsctl_bin

---

### 4.4 Wrapper installed, but still “command not found”

**Symptom:**

- `awsctl` is defined as a function in your rc file, but new terminals still show `command not found`.

**Cause:**

- Your login shell is not sourcing the file where the function is defined (for example, `.zprofile` vs `.zshrc`, or `.bash_profile` vs `.bashrc`).

**Fix:**

- For bash:
  - Ensure `.bash_profile` sources `.bashrc`, or define the wrapper directly in `.bash_profile`.
- For zsh:
  - Ensure your terminal configuration sources `.zshrc`.
  Many terminal emulators do this by default, but some may use `.zprofile` or other startup files.

---

## 5. Quick Verification Checklist

After installation or troubleshooting, verify:

1. **Function vs Binary**

       type awsctl

   Expect: `awsctl is a function`.

2. **Binary Availability**

       command -v _awsctl_bin

   Expect: a valid path, typically under `~/.local/bin`.

3. **Context Change**

   - Run:

         awsctl login --org <org>
         awsctl switch

   - Then check:

         env | grep -E '^AWS_(ACCESS_KEY_ID|SECRET_ACCESS_KEY|SESSION_TOKEN|DEFAULT_REGION)'

   Expect: non-empty values corresponding to your selected context.

If all three checks pass, shell integration for `awsctl` is functioning correctly.
