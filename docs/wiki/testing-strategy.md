# testing-strategy.md

# 🧪 Testing Strategy: Identity Armor

This document defines the **testing philosophy, levels, and quality gates** for the Identity Armor bootstrap framework. Because this tool manages the **Root of Trust**, the testing strategy prioritizes correctness, idempotency, and security validation over simple feature coverage.

---

## 🏛️ Testing Philosophy

We adhere to a **"Shift-Left"** security and testing model. Every change must be validated for:
1.  **Determinism:** The same configuration must always produce the same AWS resources.
2.  **Idempotency:** Re-running the tool against an existing environment must result in a "No-op."
3.  **Security Invariants:** Permission boundaries and OIDC trust conditions must never be weakened.



---

## 📊 Testing Levels

### 1. Unit Testing (Local)
Focuses on internal logic without requiring AWS connectivity.
* **Target:** Configuration parsing (`src/config.py`), OIDC claim validation logic, and tagging engines.
* **Tooling:** `pytest` with `pytest-mock`.
* **Gate:** ≥80% code coverage required for all logic modules.

### 2. Contract & Schema Validation
Ensures the YAML configuration remains the single source of truth.
* **Target:** `configs/*.yaml`
* **Validation:** JSON Schema validation to enforce required fields (`mgmt_account_id`, `org_id`, etc.) and prevent secret leakage.

### 3. Policy Simulation (IAM Linting)
Validates that generated IAM policies are syntactically correct and security-compliant before deployment.
* **Target:** Terraform-generated JSON and StackSet templates.
* **Tooling:** `cfn-lint`, `checkov`, and `terraform validate`.

### 4. Integration & Integration Testing (Sandbox)
Validates the full orchestration flow against a "Sandbox" AWS Organization.
* **Target:** The **Identity Broker** handshake and cross-account Role assumption.
* **Flow:**
    1.  Deploy to a disposable Spoke account.
    2.  Verify the `AssumeRole` trust policy includes the correct OIDC claims.
    3.  Assert the existence of the Terraform state bucket and DynamoDB lock table.



---

## 🔄 Idempotency Verification

A critical component of our strategy is the **"Two-Run Test"**:
* **Run 1:** Deploy the bootstrap to a fresh account. Capture the resource state.
* **Run 2:** Execute the bootstrap again with no configuration changes.
* **Success Condition:** The execution log must show **"No changes detected"** or **"✅ Verified existing resource"** for all components.

---

## 🛡️ Security Quality Gates

Documentation and code will not be merged if they fail any of the following gates:

| Gate | Tool | Failure Condition |
| :--- | :--- | :--- |
| **Linting** | `ruff` / `flake8` | Any PEP8 or logic errors. |
| **Doc Linting** | `make lint-docs` | Broken Mermaid syntax or missing images. |
| **Security Scan** | `bandit` | Potential SQLi, insecure imports, or hardcoded secrets. |
| **Infrastructure Scan** | `checkov` | IAM policies with `Action: "*"` or missing boundaries. |

---

## 🛠️ Local Verification Commands

Operators and developers should run the following suite before opening a Pull Request:

```bash
# Run unit tests and coverage
make check

# Validate documentation and diagrams
make lint-docs

# Run local security scanning
poetry run bandit -r src/
```

---

## 📝 Continuous Integration (CI)

The GitHub Actions pipeline replicates the local check suite but adds **Cross-Account Simulation**:
* **Branch Protection:** All tests must pass before merging to `main`.
* **Audit Check:** Every CI run is logged as a "Test Run" in the central Audit S3 bucket to maintain a record of testing history.

> [!IMPORTANT]
> **No Mocking the Cloud:** While unit tests use mocks, the final integration gate always runs against a real AWS environment to account for eventual consistency and API behavior.
