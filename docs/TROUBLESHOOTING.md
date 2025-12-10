# file: docs/TROUBLESHOOTING.md
# Troubleshooting — awsctl v2.8.0

## 1. Common Issues

### 1.1 Shell wrapper not loaded
**Symptom:** `awsctl switch` runs but env vars don't change.

**Check:** Run `type awsctl`.
* *Good:* `awsctl is a function`
* *Bad:* `awsctl is /usr/local/bin/awsctl`

**Fix:**

> source ~/.zshrc
> # or
> source ~/.bashrc

### 1.2 Corrupted wrapper (Dirty Edit)
**Symptom:** `setup` says "Wrapper already present" but it doesn't work.

**Cause:** You manually edited the wrapper comment block.

**Fix:** Manually delete the `awsctl() { ... }` block from your rc file and re-run `awsctl setup`.

### 1.3 SSO cache invalid
**Symptom:** "Token does not exist" loops.

**Fix:**

> awsctl cache-clear
> awsctl login --org btavm

### 1.4 Fish shell issues
**Cause:** `setup` does not support Fish automatic injection.

**Fix:** Manually install the wrapper function (see Shell Integration doc).

---

## 2. SSL & Certificate Issues

### 2.1 macOS: "SSL: CERTIFICATE_VERIFY_FAILED"
**Fix:** Export system certs to PEM and set `REQUESTS_CA_BUNDLE`.

> security find-certificate -a -p /Library/Keychains/System.keychain > ~/macos_certs.pem
> export REQUESTS_CA_BUNDLE="$HOME/macos_certs.pem"

### 2.2 Windows / WSL: "Self Signed Certificate"
**Fix:** Import the corporate root CA into the WSL trust store (`/usr/local/share/ca-certificates/`) and run `update-ca-certificates`.

---

## 3. Installation Issues

### 3.1 `pipx install` fails
**Fix:** Ensure `git` is installed via your OS package manager (`brew`, `apt`, `yum`).

---

## 4. Diagnostic Tools

### 4.1 `awsctl doctor`
**Purpose:** Validates config, permissions, and dependencies.

**Usage:**

> awsctl doctor

### 4.2 `awsctl status`
**Purpose:** Shows current in-memory context.

**Usage:**

> awsctl status
