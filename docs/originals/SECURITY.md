# Security Policy

**Classification:** Internal Only
**Audience:** Platform Engineering & Security

## 🤖 AI Usage Declaration
This project utilizes AI assistance for boilerplate generation, unit test creation, and bug fixing.
- **Audit Status:** Code logic has been reviewed by human maintainers.
- **Data Safety:** No private cryptographic keys or live credentials were shared during the generation process.

## 🛡️ Trust Model & Architecture

### 1. Zero Trust Credential Handling
* **In-Memory Only:** `cloudctl` never writes long-term credentials (`AWS_SECRET_ACCESS_KEY`) to disk. They are held in process memory and exported directly to the shell environment via the "Context Bridge".
* **TTY Guard:** The binary detects interactive terminals and refuses to print credentials to `stdout`, preventing accidental leakage into shell history files.

### 2. Corporate Proxy & TLS Trust
To support corporate inspection proxies (Zscaler, Netskope), `cloudctl` (via Python's `requests`) must trust the system certificate store.
* **Mitigation:** We instruct macOS/Linux users to explicitly export their System Keychain certificates to a PEM file (`REQUESTS_CA_BUNDLE`).
* **Risk Acceptance:** This is a standard requirement for Python tools in enterprise environments. It does **not** disable SSL verification; it simply expands the trust store to include the corporate Root CA.

### 3. Registry Integrity (Tier 3)
When using the Remote Registry (future state), integrity is guaranteed via **Ed25519 signatures (Minisign)**.
* The Public Key is pinned in the binary (`src/cloudctl/registry.py`).
* The Private Key is stored in a secured CI/CD Secrets vault.
* Use of the "Manual Configuration" mode (Pilot Phase) transfers the integrity responsibility to the user (verifying the Confluence source).
