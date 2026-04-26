# file: docs/TROUBLESHOOTING.md
# Troubleshooting — cloudctl v2.8.1

## 1. Common Issues

### 1.1 Shell wrapper not loaded
**Symptom:** `cloudctl switch` runs but env vars don't change.
**Check:** Run `type cloudctl`.
* *Good:* `cloudctl is a function`
* *Bad:* `cloudctl is /usr/local/bin/cloudctl`

**Fix:**

> source ~/.zshrc
> # or
> source ~/.bashrc

### 1.2 Corrupted wrapper (Dirty Edit)
**Symptom:** `setup` says "Wrapper already present" but it doesn't work.
**Cause:** You manually edited the wrapper comment block.

**Fix:** Manually delete the `cloudctl() { ... }` block from your rc file and re-run `cloudctl setup`.

### 1.3 SSO cache invalid
**Symptom:** "Token does not exist" loops.

**Fix:**

> cloudctl cache-clear
> cloudctl login --org btavm

### 1.4 Fish shell issues
**Cause:** `setup` does not support Fish automatic injection.

**Fix:** Manually install the wrapper function (see Shell Integration doc).

---

## 2. SSL & Certificate Issues (Corporate Proxies)

### 2.1 macOS: "SSL: CERTIFICATE_VERIFY_FAILED"
**Cause:** Python does not use the macOS Keychain by default.
**Fix:** Export **all** system certs (System, Root, and Login) and configure Python to use them globally.

**Step 1: Export All Certs (The "Nuclear" Option)**
Run this block to combine all keychain sources:

> rm ~/macos_certs.pem
> security find-certificate -a -p /System/Library/Keychains/SystemRootCertificates.keychain >> ~/macos_certs.pem
> security find-certificate -a -p /Library/Keychains/System.keychain >> ~/macos_certs.pem
> security find-certificate -a -p "$HOME/Library/Keychains/login.keychain-db" >> ~/macos_certs.pem

**Step 2: Make it Permanent**
Add this to your `~/.zshrc`:

> export REQUESTS_CA_BUNDLE="$HOME/macos_certs.pem"

Then reload:

> source ~/.zshrc

### 2.2 Windows / WSL: "Self Signed Certificate"
**Cause:** WSL (Ubuntu) does not inherit trusted certs from Windows.

**Fix:**
1. **Export:** In Windows, export your Corporate Root CA to a Base-64 `.cer` file.
2. **Copy:** Move it into WSL (e.g., `~/corp-root.crt`).
3. **Configure:** Add to your `~/.bashrc`:

> export REQUESTS_CA_BUNDLE="$HOME/corp-root.crt"

---

## 3. Installation Issues

### 3.1 `pipx install` fails
**Fix:** Ensure `git` is installed via your OS package manager (`brew`, `apt`, `yum`).

---

## 4. Diagnostic Tools

### 4.1 `cloudctl doctor`
**Purpose:** Validates config, permissions, and dependencies.

**Usage:**

> cloudctl doctor

### 4.2 `cloudctl status`
**Purpose:** Shows current in-memory context.

**Usage:**

> cloudctl status
