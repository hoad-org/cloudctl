# Shell Integration Guide

This document explains how `awsctl` integrates with your interactive shell (`bash`, `zsh`) using the **Trojan Horse** pattern.

---

## 1. The Mechanism

Instead of the user running the Python binary directly, they run a shell wrapper function named `awsctl`.  
This wrapper intercepts commands.

### 1.1 The Wrapper Logic

The actual Python binary is installed as `_awsctl_bin` (hidden).  
The shell function `awsctl` manages the workflow:

    awsctl() {
        # 1. Ask the binary: "Does this command need to modify the shell?"
        local outcome
        outcome=$(_awsctl_bin "$@" --check-strategy 2>/dev/null)

        # 2. Strategy: EXEC (normal command like 'doctor', 'status')
        if [[ "$outcome" == "EXEC" ]]; then
            _awsctl_bin "$@"
            return $?
        fi

        # 3. Strategy: EVAL (context switching command like 'switch')
        if [[ "$outcome" == "EVAL" ]]; then
            local output
            output=$(_awsctl_bin "$@")
            # If successful, apply exports to the current shell
            if [[ $? -eq 0 ]]; then
                eval "$output"
            else
                echo "$output"
            fi
            return $?
        fi

        # Fallback
        _awsctl_bin "$@"
    }

This integration allows `awsctl switch` to export variables to your current session seamlessly, without you typing `eval $(...)`.

---

## 2. Installation

### 2.1 Automatic (Recommended)

Run:

    awsctl setup

The wizard will:

- Append the function above to your rc file (`~/.bashrc` or `~/.zshrc`).
- Ensure the internal binary (`_awsctl_bin`) is accessible on your `PATH`.

Then reload your shell:

    source ~/.bashrc
    # or
    source ~/.zshrc

### 2.2 Manual Configuration

If you manage dotfiles manually, copy the function definition above into your `~/.bashrc` or `~/.zshrc`.  
Ensure that `_awsctl_bin` is in your `PATH`.

---

## 3. Platform Support

### 3.1 Bash and Zsh

Status: ✅ Fully supported.  
The installer handles this automatically by appending the `awsctl` function to your shell rc file.

---

### 3.2 Fish Shell

Status: ⚠ Partial support.

Fish does not use `eval` syntax compatible with Bash-style `export FOO=BAR`.  
You need a Fish-specific wrapper that translates `export FOO=BAR` to `set -gx FOO BAR`.

Fish wrapper example:

    function awsctl
        set -l cmd $argv[1]

        if contains $cmd "switch" "logout" "use"
            # Eval mode
            set -l output (_awsctl_bin $argv)
            if test $status -eq 0
                for line in $output
                    # Naive translation of 'export VAR=VAL' -> 'set -gx VAR VAL'
                    set -l kv (string split -m1 = (string replace "export " "" $line))
                    set -gx $kv[1] (string trim -c '"' $kv[2])
                end
            else
                echo $output
            end
        else
            # Exec mode
            _awsctl_bin $argv
        end
    end

---

### 3.3 PowerShell / Windows

Status: ❌ Not supported directly.

Use WSL2 (Windows Subsystem for Linux) running Ubuntu/Debian and install `awsctl` inside that environment.  
The Bash integration works normally inside WSL2.

---

## 4. Troubleshooting

**Problem:** `command not found: _awsctl_bin`

- Cause: `pipx` (or `pip`) has not added the binary path to your shell `PATH`, or you are in a shell where the `awsctl` environment is not active.
- Fix: Ensure `~/.local/bin` (or the appropriate `pipx` bin path) is in your `PATH`. Restart your shell.

---

**Problem:** `awsctl switch` does not change my variables

- Cause: Your shell config might not be reloaded, so the `awsctl` function is not in scope.
- Fix:

      source ~/.zshrc
      # or
      source ~/.bashrc

  Then verify the wrapper is active:

      type awsctl

  It should show that `awsctl` is a function.

---

**Problem:** Infinite loop when running `awsctl`

- Cause: You aliased `_awsctl_bin` to `awsctl` manually, or otherwise misconfigured the wrapper.
- Fix: Remove manual aliases and ensure you are using the function definition provided by `awsctl setup`.

---

This shell integration is the core of the v2.0.0 **Trojan Horse** architecture, enabling `awsctl` to safely modify your current shell environment for context switching without ever persisting secrets to disk.
