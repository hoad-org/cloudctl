# ⚙️ Configuration Model

This document defines the **hierarchical configuration model** for `awsctl`. It explains how the tool resolves settings, where configurations are stored, and how `awsctl` maintains a stateless profile.

This document is authoritative.

---

## 🏗️ Configuration Philosophy

`awsctl` configuration is designed to be **explicit and deterministic**. 

* **Stateless by Default:** The core binary does not maintain a local database of state. 
* **Version Controlled:** Configurations should be treated as code (GitOps).
* **No Implicit Defaults:** `awsctl` avoids "guessing" settings if they are missing from the hierarchy.

---

## 📊 Configuration Hierarchy

`awsctl` resolves configuration using a strict order of precedence. Higher levels override lower levels.



1.  **Command Line Flags:** (e.g., `--region`, `--account`) - Highest precedence.
2.  **Environment Variables:** (e.g., `AWSCTL_REGION`).
3.  **Local Workspace Config:** `.awsctl.yaml` in the current working directory.
4.  **User Global Config:** `~/.config/awsctl/config.yaml`.
5.  **Policy Registry:** Centralized organizational constraints (Read-only).

---

## 📂 Configuration Sources

### 1. The Policy Registry (Centralized)
The Registry is the **authoritative list** of allowed accounts and roles. It is usually managed by a Platform/Security team and synced to the local machine.
* **Purpose:** Defines the "boundaries of the possible."
* **Mutability:** Immutable for the end-user.

### 2. User Configuration (Local)
Stored in the user's home directory, this file handles personalization that does not affect security boundaries.
* **Examples:** Default output formats, UI/UX preferences (e.g., color toggles), or plugin aliases.

### 3. Execution Context (Transient)
The "active" configuration derived during a `switch` operation. This exists only in memory or is emitted to the shell as environment variables.

---

## 📝 Schema and Validation

All configuration files must adhere to a strict YAML schema. `awsctl` performs a **Pre-flight Schema Validation** every time it starts.



* **Strict Typing:** Account IDs must be strings, ARNs must follow standard patterns.
* **No Unknown Keys:** Extraneous keys in the config file will cause `awsctl` to abort to prevent "configuration drift" or typos from being ignored.

---

## 🐚 Environment Variable Mapping

`awsctl` maps internal settings to environment variables using a consistent `AWSCTL_` prefix.

| Variable | Description |
| :--- | :--- |
| `AWSCTL_CONFIG` | Path to a specific configuration file. |
| `AWSCTL_REGISTRY_URL` | The upstream source for the policy registry. |
| `AWSCTL_LOG_LEVEL` | Verbosity of the execution core (`DEBUG`, `INFO`, `WARN`). |
| `AWSCTL_SKIP_PROMPT` | Used to trigger Non-Interactive mode. |

---

## 🛡️ Security Invariants for Configuration

* **No Secret Storage:** `awsctl` configuration files **must never** contain static AWS Access Keys or Secrets.
* **Path Integrity:** `awsctl` ignores configuration files with insecure permissions (e.g., world-writable).
* **Registry over Local:** A local configuration cannot "unlock" an account or role that is not present in the Policy Registry.

---

## 🔄 Interaction with AWS Profiles

`awsctl` does not use standard `~/.aws/credentials` or `~/.aws/config` files for its internal logic. It interacts with AWS exclusively via the **Identity Broker Pattern**, using the Registry to determine which roles can be assumed via STS.



---

## 📝 Summary

The configuration model ensures that `awsctl` remains a transparent broker. By separating **User Preference** (local config) from **Organizational Policy** (registry), `awsctl` maintains a high-trust environment where intent is always validated against authority.
