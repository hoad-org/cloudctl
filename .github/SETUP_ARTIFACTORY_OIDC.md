# Artifactory OIDC Setup for awsctl Publish Workflow

This guide configures JFrog Artifactory to trust GitHub Actions via OpenID Connect (OIDC), eliminating the need for static API tokens.

## Prerequisites

- Access to JFrog Artifactory as an Admin
- Write access to the `aws-terraform-infra-cloudops-awsctl` GitHub repository
- A PyPI local repository named `awsctl-pypi` already created

## Step 1: Configure OIDC Provider in Artifactory

1. **Login** to Artifactory: https://beyondtrust.jfrog.io
2. **Admin** (gear icon) → **Integrations** → **OIDC Integrations**
3. Click **Add OIDC Provider**
4. Select **GitHub** from the provider list
5. Fill in:
   - **Name:** `github`
   - **Provider URL:** `https://token.actions.githubusercontent.com`
   - **Audience:** Leave as default (will auto-populate)
6. Click **Create**

Artifactory will generate a configuration snippet. You'll use this next.

## Step 2: Add Identity Mapping

Still in **OIDC Integrations** → **github** provider:

1. Click **Identity Mapping** tab
2. Add a new mapping:
   - **Mapping Name:** `awsctl-publish`
   - **Subject Pattern:**
     ```
     repo:BT-IT-Infrastructure-CloudOps/aws-terraform-infra-cloudops-awsctl:ref:refs/tags/v*
     ```
     (This restricts OIDC auth to semver tags in this repo only)
   - **User:** Create or select a service account (or use `oidc-github-ci`)
   - **Groups:** Assign groups that have write access to `awsctl-pypi`
3. Click **Save**

## Step 3: Grant Repository Permissions

Ensure the service account/user from Step 2 has **Deploy** permissions on `awsctl-pypi`:

1. **Admin** → **Repositories** → **awsctl-pypi**
2. **Permissions** tab
3. Add the service account with **Deploy** and **Manage** permissions
4. Save

## Step 4: Verify the Workflow

Push a test tag:

```bash
git tag v0.0.0-test
git push origin v0.0.0-test
```

Monitor the **Actions** tab → **Publish - Artifactory** workflow. It should:
1. Request an OIDC token from GitHub
2. Exchange it with Artifactory
3. Publish the package without storing any secrets

Check Artifactory **Artifacts** → **awsctl-pypi** to confirm the package arrived.

Clean up the test tag:

```bash
git tag -d v0.0.0-test
git push origin :v0.0.0-test
```

## Step 5: Normal Release Process

Once verified, release new versions:

```bash
# Bump version in pyproject.toml
vi pyproject.toml
git add pyproject.toml
git commit -m "Bump awsctl to 3.2.0"

# Create semver tag
git tag v3.2.0
git push origin main --tags

# GitHub Actions automatically publishes to Artifactory
```

No secrets, no token management, no rotation needed.

---

## Troubleshooting

### "401 Unauthorized" on publish

**Cause:** OIDC token not properly exchanged.

**Fix:**
- Verify the subject pattern in Identity Mapping matches the tag format exactly
- Ensure the service account has write permissions on `awsctl-pypi`
- Check Artifactory audit logs: **Admin** → **Logs** → **Audit**

### Package not appearing in PyPI

**Cause:** Indexing delay or `awsctl-pypi` repo misconfigured.

**Fix:**
- Wait 30 seconds and check **Artifacts** → **awsctl-pypi**
- Verify the wheel filename matches the repo's PyPI format expectations
- Manually upload a test wheel to confirm the repo works: `jf rt u dist/*.whl awsctl-pypi/`

### Workflow silently skips the publish job

**Cause:** The `if:` condition failed (repo name doesn't match).

**Fix:**
- Check the actual repository path: `Settings` → copy the full repo slug
- Verify it matches the hardcoded check in the workflow: `if: github.repository == 'BT-IT-Infrastructure-CloudOps/aws-terraform-infra-cloudops-awsctl'`

---

## References

- [JFrog OIDC Setup Guide](https://jfrog.com/help/jfrog/oidc-integration)
- [GitHub OIDC Token Documentation](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect)
- [JFrog CLI Python Plugin](https://docs.jfrog-applications.jfrog.io/jfrog-cli/cli-for-jfrog-artifactory/python-repositories)
