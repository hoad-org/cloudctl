# Artifactory Setup Checklist for awsctl PyPI Publishing

This checklist ensures everything is in place for the `publish-artifactory.yaml` workflow to work end-to-end.

## Phase 1: Artifactory Repository Setup

- [ ] **Create PyPI local repository**
  - Go to: https://beyondtrust.jfrog.io → Admin → Repositories → Create Repository
  - Package Type: **PyPI**
  - Repository Class: **Local**
  - Repository Key: **`awsctl-pypi`**
  - Leave all other settings as defaults
  - Click **Create**

- [ ] **Create PyPI virtual repository (optional, recommended)**
  - Same path, click Create Repository again
  - Package Type: **PyPI**
  - Repository Class: **Virtual**
  - Repository Key: **`awsctl-virtual`**
  - Default Deployment Repository: **`awsctl-pypi`**
  - Repositories tab: Add `awsctl-pypi` (and optionally public PyPI remote)
  - Click **Create**

## Phase 2: OIDC Integration Setup

- [ ] **Configure OIDC Provider in Artifactory**
  - Go to: https://beyondtrust.jfrog.io → Admin → Integrations → OIDC Integrations
  - Click **Add OIDC Provider** → Select **GitHub**
  - **Name:** `github`
  - **Provider URL:** `https://token.actions.githubusercontent.com`
  - Click **Create**

- [ ] **Add Identity Mapping for awsctl repo**
  - In the **github** OIDC provider, click **Identity Mapping** tab
  - Click **Add Mapping**
  - **Mapping Name:** `awsctl-publish`
  - **Subject Pattern:**
    ```
    repo:BT-IT-Infrastructure-CloudOps/aws-terraform-infra-cloudops-awsctl:ref:refs/tags/v*
    ```
  - **User:** Select or create a service account (e.g., `oidc-github-ci` or `github-actions`)
  - **Groups:** Assign groups with write access to `awsctl-pypi` (e.g., `developers` or `ci-publishers`)
  - Click **Save**

- [ ] **Grant repository permissions to the service account**
  - Go to: https://beyondtrust.jfrog.io → Admin → Repositories → awsctl-pypi
  - Click **Permissions** tab
  - Add the service account from above with:
    - **Deploy** permission ✓
    - **Manage** permission ✓
  - Save

## Phase 3: Test the Workflow

- [ ] **Create a test tag and verify the workflow executes**
  ```bash
  cd /Users/choad/repos/aws-terraform-infra-cloudops-awsctl
  git tag v0.0.0-test
  git push origin v0.0.0-test
  ```

- [ ] **Monitor the GitHub Actions workflow**
  - Go to: https://github.com/BT-IT-Infrastructure-CloudOps/aws-terraform-infra-cloudops-awsctl/actions
  - Look for **Publish - Artifactory** workflow
  - Watch for:
    - ✓ OIDC token obtained from GitHub
    - ✓ JFrog CLI authenticated with OIDC
    - ✓ Wheel published to Artifactory
    - ✓ Package reachability verified

- [ ] **Verify the package appears in Artifactory**
  - Go to: https://beyondtrust.jfrog.io → Artifacts → awsctl-pypi
  - Look for `awsctl-0.0.0.post0-test-*.whl` and `awsctl-0.0.0.post0-test-*.tar.gz`

- [ ] **Clean up the test tag**
  ```bash
  git tag -d v0.0.0-test
  git push origin :v0.0.0-test
  ```

## Phase 4: Production Release Process

- [ ] **Bump version in pyproject.toml**
  ```bash
  vi pyproject.toml  # change version = "3.1.0" → "3.2.0"
  git add pyproject.toml
  git commit -m "Bump awsctl to 3.2.0"
  ```

- [ ] **Create and push a semver tag**
  ```bash
  git tag v3.2.0
  git push origin main --tags
  ```

- [ ] **Wait for the workflow to complete**
  - Monitor: https://github.com/BT-IT-Infrastructure-CloudOps/aws-terraform-infra-cloudops-awsctl/actions
  - Expected duration: 2-3 minutes

- [ ] **Verify package is available for installation**
  ```bash
  pip install awsctl==3.2.0 \
    --index-url https://beyondtrust.jfrog.io/artifactory/api/pypi/awsctl-pypi/simple/ \
    --extra-index-url https://pypi.org/simple/
  ```

## Rollback / Troubleshooting

- [ ] **If a release has issues and needs to be removed:**
  - Go to: https://beyondtrust.jfrog.io → Artifacts → awsctl-pypi
  - Find the version (e.g., `awsctl-3.2.0*.whl`, `awsctl-3.2.0*.tar.gz`)
  - Right-click → **Delete**
  - Re-tag and push a fixed version

- [ ] **If OIDC authentication fails:**
  - Check Artifactory audit logs: Admin → Logs → Audit
  - Verify the subject pattern in Identity Mapping matches `repo:...:ref:refs/tags/v*`
  - Ensure the service account has Deploy permission on `awsctl-pypi`
  - See `.github/SETUP_ARTIFACTORY_OIDC.md` for detailed troubleshooting

- [ ] **If the workflow is skipped:**
  - The `if:` condition checks `github.repository == 'BT-IT-Infrastructure-CloudOps/aws-terraform-infra-cloudops-awsctl'`
  - This prevents accidental publishes from forks
  - Only tags on the canonical repo will trigger

## Once Complete

- Mark all checkboxes above ✓
- Commit this checklist as `COMPLETE` to document setup date
- Users can now install: `pip install awsctl --index-url https://beyondtrust.jfrog.io/artifactory/api/pypi/awsctl-pypi/simple/`

---

**Questions or stuck?** See `.github/SETUP_ARTIFACTORY_OIDC.md` for detailed setup instructions.
