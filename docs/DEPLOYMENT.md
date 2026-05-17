# CloudCTL Deployment & Setup Guide

This guide covers installation, configuration, and post-install setup for cloudctl across all supported platforms and cloud providers.

## Prerequisites

Before beginning setup, ensure you have:

- **Python 3.12+** (required)
- **AWS CLI v2** (required for AWS orgs only)
- **Azure CLI (`az`)** (optional — required only for Azure orgs)
- **Google Cloud SDK (`gcloud`)** (optional — required only for GCP orgs)
- **Git** (for cloning the repository or using the script installer)
- **GitHub Personal Access Token (PAT)** with `read:contents` or `repo` scope (for installing from GitHub Releases)

Verify your Python version:

```bash
python3 --version  # Must be 3.12 or higher
```

---

## Installation Options

### Option A: GitHub Release (Recommended)

The simplest and most secure approach — download the pre-built wheel from GitHub Releases.

**Requirements:**
- GitHub Personal Access Token with `read:contents` scope
- `curl` and `pip3` available on your system

**Setup:**

```bash
# Set your GitHub token (replace with your actual token)
export GITHUB_TOKEN=ghp_your_token_here

# Run the installer
bash install.sh
```

The `install.sh` script will:
1. Query the GitHub Releases API for the latest version
2. Download the wheel file
3. Install it via pip
4. Inject the shell wrapper into your shell profile
5. Prompt you to restart your shell

**One-liner alternative** (without cloning the repo):

```bash
export GITHUB_TOKEN=ghp_your_token_here
RELEASE=$(curl -sf -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  https://api.github.com/repos/BT-IT-Infrastructure-CloudOps/aws-terraform-infra-cloudops-cloudctl/releases/latest)
WHEEL_URL=$(echo "${RELEASE}" | python3 -c \
  "import sys,json; d=json.load(sys.stdin); print(next(a['url'] for a in d['assets'] if a['name'].endswith('.whl')))")
curl -sf -L -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "Accept: application/octet-stream" "${WHEEL_URL}" -o /tmp/cloudctl.whl
pip3 install --user /tmp/cloudctl.whl --extra-index-url "https://pypi.org/simple/"
cloudctl init --shell-only
```

---

### Option B: Script Install (macOS / Linux / WSL)

Clone the repository and run the installer script, which automates the GitHub Release download.

**Requirements:**
- Git installed
- GitHub Personal Access Token (for wheel download)

**Setup:**

```bash
export GITHUB_TOKEN=ghp_your_token_here

git clone https://github.com/BT-IT-Infrastructure-CloudOps/aws-terraform-infra-cloudops-cloudctl.git
cd aws-terraform-infra-cloudops-cloudctl
bash install.sh
```

This approach lets you see the installation code before running it, and makes it easy to contribute fixes if needed.

---

### Option C: Windows PowerShell (Native)

Install on Windows without WSL using PowerShell.

**Requirements:**
- PowerShell 5.1+ or pwsh (PowerShell Core)
- GitHub Personal Access Token
- Python 3.12+ already on PATH

**Setup:**

```powershell
$env:GITHUB_TOKEN = "ghp_your_token_here"

git clone https://github.com/BT-IT-Infrastructure-CloudOps/aws-terraform-infra-cloudops-cloudctl.git
cd aws-terraform-infra-cloudops-cloudctl
.\install.ps1
```

The `install.ps1` script will:
1. Validate Python version (3.12+)
2. Download the wheel from GitHub Releases
3. Install it via pip
4. Inject the PowerShell wrapper function into your `$PROFILE`
5. Reload your profile

---

### Option D: Artifactory (Internal PyPI)

If your organization hosts cloudctl on JFrog Artifactory, you can install without a GitHub token.

**Setup (One-time):**

Add the Artifactory URL to your shell profile:

```bash
# Add to ~/.zshrc or ~/.bashrc
export AWSCTL_INDEX_URL=https://your-org.jfrog.io/artifactory/api/pypi/cloudctl-pypi/simple/
```

**Installation:**

```bash
# With the env var set, the installer will use Artifactory
bash install.sh
```

**Manual installation:**

```bash
pip3 install cloudctl --index-url https://your-org.jfrog.io/artifactory/api/pypi/cloudctl-pypi/simple/ --user
cloudctl init --shell-only
```

---

## AWS SSO Configuration

For organizations using AWS (commercial or GovCloud), you must configure AWS IAM Identity Center (formerly AWS Single Sign-On).

### Gathering Required Information

Before running `cloudctl init`, you need:

1. **SSO Start URL** — Found in AWS IAM Identity Center console
   - Navigate to: AWS IAM Identity Center → Settings → Instances → Instance Details
   - Copy the "Identity Center instance URL" (format: `https://d-xxxxxxxxxx.awsapps.com/start`)

2. **SSO Region** — The AWS region where your SSO instance is deployed
   - Examples: `us-east-1`, `us-gov-west-1`, `cn-north-1`
   - For GovCloud, use `us-gov-west-1` or `us-gov-east-1`
   - For China, use `cn-north-1` or `cn-northwest-1`

3. **Partition** (optional, defaults to `aws`)
   - `aws` — AWS Commercial
   - `aws-us-gov` — AWS GovCloud
   - `aws-cn` — AWS China (requires long-term IAM keys; SSO not supported)

4. **Allowed Regions** (optional) — Restrict which regions users can switch to
   - Example: `[us-east-1, us-west-2]`
   - If omitted, all regions in the partition are available

### Example Configuration (Multi-Partition)

`cloudctl` supports multiple AWS partitions in a single configuration:

```yaml
orgs:
  # AWS Commercial
  - name: bt-avm
    provider: aws
    partition: aws              # optional; defaults to aws
    sso_start_url: https://d-xxxxxxxxxx.awsapps.com/start
    sso_region: us-east-1
    allowed_regions: [us-east-1, us-west-2, eu-west-1]

  # AWS GovCloud
  - name: fdr-gvc
    provider: aws
    partition: aws-us-gov
    sso_start_url: https://d-yyyyyyyyyy.awsapps-us-gov.com/start
    sso_region: us-gov-west-1
    allowed_regions: [us-gov-east-1, us-gov-west-1]
```

### Partition Notes

- **AWS Commercial (`aws`):** All commercial AWS regions (us-east-1, eu-west-1, ap-southeast-1, etc.)
- **AWS GovCloud (`aws-us-gov`):** US government regions only (us-gov-east-1, us-gov-west-1)
- **AWS China (`aws-cn`):** China regions (cn-north-1, cn-northwest-1) — **does not support IAM Identity Center**
  - For China, configure long-term IAM access keys instead:
    ```bash
    export AWS_ACCESS_KEY_ID=<your-key>
    export AWS_SECRET_ACCESS_KEY=<your-secret>
    export AWS_DEFAULT_REGION=cn-north-1
    ```

---

## GitHub Token Configuration

CloudCTL requires a GitHub Personal Access Token (PAT) to download releases from the private repository.

### Creating a GitHub Token

1. Go to https://github.com/settings/tokens
2. Click **"Generate new token"** → **"Generate new token (classic)"**
3. Give it a descriptive name, e.g., "cloudctl-install"
4. Set expiration (90 days recommended for security)
5. Select scope: **`read:contents`** (minimal scope required)
   - Alternatively, select **`repo`** for full repository access
6. Click **"Generate token"** and copy it immediately (you won't see it again)

### Using the Token

**One-time setup:**

```bash
export GITHUB_TOKEN=ghp_your_token_here
bash install.sh
```

**Persistent setup** (add to your shell profile):

```bash
# Add to ~/.zshrc, ~/.bashrc, or $PROFILE (PowerShell)
export GITHUB_TOKEN=ghp_your_token_here
```

### Token Security

- Never commit tokens to version control
- Store in secure password managers or `~/.config/github/token` (not checked into git)
- Regenerate tokens if exposed
- Use short expiration periods (90 days)
- Use minimal scopes (`read:contents` is sufficient)

---

## Azure Configuration

For Azure organizations, you need your **Tenant ID** (optional but recommended).

### Gathering Required Information

1. **Tenant ID** (UUID format, optional)
   - Found in Azure Portal → Azure Active Directory → Properties → Tenant ID
   - Example: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`
   - If not provided, `az login` will prompt for tenant selection

2. **Subscription IDs** (auto-discovered during `cloudctl login`)
   - You can see them with: `az account list --output table`

3. **Roles** (optional, defaults to auto-discovery)
   - If you want to restrict the role picker, specify RBAC roles:
     ```yaml
     - name: azure-prod
       provider: azure
       tenant_id: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
       roles:
         - Contributor
         - Reader
         - VM Contributor
     ```

### Example Configuration

```yaml
- name: azure-prod
  provider: azure
  tenant_id: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
  allowed_regions: [eastus, westeurope]
```

---

## GCP Configuration

For Google Cloud Platform, you need your **Project ID**.

### Gathering Required Information

1. **Project ID** (required for default context)
   - Found in Google Cloud Console → Project Info
   - Example: `my-project-id` (not the project number)

2. **Allowed Regions** (optional, defaults to all GCP regions)
   - Example: `[us-central1, europe-west1]`

3. **Roles** (optional, defaults to basic roles)
   - Specify GCP IAM roles:
     ```yaml
     roles:
       - roles/viewer
       - roles/editor
       - roles/owner
     ```

### Example Configuration

```yaml
- name: gcp-prod
  provider: gcp
  default_project: my-project-id
  allowed_regions: [us-central1, us-west1, europe-west1]
```

---

## Artifactory Setup (Optional)

If your organization publishes cloudctl to JFrog Artifactory, you can avoid the GitHub token requirement.

### Configuration

**One-time setup:**

```bash
export AWSCTL_INDEX_URL=https://your-org.jfrog.io/artifactory/api/pypi/cloudctl-pypi/simple/
bash install.sh
```

**Persistent setup:**

Add to your shell profile:

```bash
export AWSCTL_INDEX_URL=https://your-org.jfrog.io/artifactory/api/pypi/cloudctl-pypi/simple/
```

### Credentials (If Required)

If your Artifactory instance requires authentication:

```bash
export ARTIFACTORY_USER=your-username
export ARTIFACTORY_APIKEY=your-api-key
bash install.sh
```

Or add to `~/.pypirc`:

```ini
[distutils]
index-servers =
    artifactory

[artifactory]
repository: https://your-org.jfrog.io/artifactory/api/pypi/cloudctl-pypi/
username: your-username
password: your-api-key
```

---

## Post-Installation: First-Time Setup

After installation, run the setup wizard to configure your organizations.

### Interactive Wizard (Recommended)

```bash
cloudctl init
```

This will:
1. Detect your shell (bash, zsh, fish, or PowerShell)
2. Prompt for each organization (AWS, Azure, GCP)
3. Guide authentication setup
4. Validate connectivity
5. Save configuration to `~/.config/cloudctl/orgs.yaml`

### Single Organization Setup

To add a single organization without the full wizard:

```bash
cloudctl org add
```

This is auth-first — it logs you in immediately, then discovers your available accounts/subscriptions/projects.

### Manual Configuration (Advanced)

Edit `~/.config/cloudctl/orgs.yaml` directly:

```bash
mkdir -p ~/.config/cloudctl
nano ~/.config/cloudctl/orgs.yaml
```

Use the examples in this guide or `cloudctl --help` for the full schema.

---

## Verification Steps

After installation, verify everything works:

### 1. Check Installation Health

```bash
cloudctl doctor
```

This runs a comprehensive health check covering:
- Python version
- Shell integration
- File permissions
- Network connectivity
- Tool availability (aws, az, gcloud)

### 2. List Configured Organizations

```bash
cloudctl org list
```

You should see all organizations you configured.

### 3. Test Authentication

```bash
cloudctl login <org-name>
# Examples:
cloudctl login bt-avm          # AWS Commercial
cloudctl login fdr-gvc         # AWS GovCloud
cloudctl login azure-prod      # Azure
cloudctl login gcp-prod        # GCP
```

Follow the browser prompt or terminal guidance to complete authentication.

### 4. List Available Accounts/Subscriptions/Projects

```bash
cloudctl accounts <org-name>
```

Example output:

```
Organization: bt-avm (AWS)
Account ID          Account Name
─────────────────   ─────────────────
111111111111        Production
222222222222        Development
333333333333        Staging
```

### 5. Test Context Switching

```bash
cloudctl switch <org-name>
```

This opens an interactive picker. Select an account and role.

### 6. Verify Active Context

```bash
cloudctl env
```

You should see your active org, account, role, and credentials.

---

## Troubleshooting Installation

### "Python version 3.X is not supported"

**Problem:** Your system Python is older than 3.12.

**Solution:**

```bash
# Check your Python version
python3 --version

# Install Python 3.12+ via Homebrew (macOS)
brew install python@3.12

# Or use pyenv (macOS/Linux)
pyenv install 3.12.0
pyenv local 3.12.0
```

### "GITHUB_TOKEN not set or invalid"

**Problem:** Cannot download wheel from GitHub Releases.

**Solutions:**

1. Create a new token (see [GitHub Token Configuration](#github-token-configuration))
2. Verify the token has `read:contents` scope
3. Check token hasn't expired
4. Try the manual one-liner installation (see Option A)

### "AWS CLI not found"

**Problem:** AWS CLI v2 is not installed.

**Solution:**

```bash
# macOS
brew install awscli

# Linux
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Windows (via Homebrew or direct download)
# https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html
```

### "Azure CLI (az) not found"

**Problem:** Azure CLI is not installed.

**Solution:**

```bash
# macOS
brew install azure-cli

# Linux
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Windows
# https://learn.microsoft.com/en-us/cli/azure/install-azure-cli
```

### "gcloud CLI not found"

**Problem:** Google Cloud SDK is not installed.

**Solution:**

```bash
# macOS
brew install --cask google-cloud-sdk

# Linux / Windows
# https://cloud.google.com/sdk/docs/install
```

### "Wheel installation failed: permission denied"

**Problem:** Cannot write to pip user directory.

**Solutions:**

```bash
# Option 1: Use --user flag
pip3 install --user /tmp/cloudctl.whl

# Option 2: Use a virtual environment
python3 -m venv ~/cloudctl-venv
source ~/cloudctl-venv/bin/activate
pip install /tmp/cloudctl.whl

# Option 3: Use pipx (if available)
pipx install /tmp/cloudctl.whl
```

### "Shell wrapper not injected" or "cloudctl command not found"

**Problem:** Shell integration failed.

**Solutions:**

```bash
# Re-run the shell integration step
cloudctl init --shell-only

# Verify the wrapper is in your profile
grep -n "cloudctl" ~/.zshrc     # zsh
grep -n "cloudctl" ~/.bashrc    # bash
# PowerShell: check $PROFILE

# Restart your shell
exec zsh      # for zsh
exec bash     # for bash
# PowerShell: close and reopen the window
```

---

## Upgrading CloudCTL

Once installed, upgrade to the latest version without cloning:

### Via GitHub Releases

```bash
export GITHUB_TOKEN=ghp_your_token_here
cloudctl upgrade
```

### Via Artifactory

```bash
export AWSCTL_INDEX_URL=https://your-org.jfrog.io/artifactory/api/pypi/cloudctl-pypi/simple/
cloudctl upgrade
```

Or specify the URL inline:

```bash
cloudctl upgrade --index-url https://your-org.jfrog.io/artifactory/api/pypi/cloudctl-pypi/simple/
```

---

## Uninstall

To remove cloudctl completely:

### Interactive Uninstall (Recommended)

```bash
cloudctl uninstall
```

This will:
- Prompt before removing anything
- Remove the cloudctl package
- Remove the shell wrapper
- Remove configuration files (optional)

### Preview Without Making Changes

```bash
cloudctl uninstall --dry-run
```

### Selective Uninstall

```bash
# Remove only the package, keep shell integration
cloudctl uninstall --package-only

# Remove everything but keep configuration
cloudctl uninstall --keep-config
```

### Manual Uninstall

```bash
# Remove the package
pip3 uninstall cloudctl

# Remove shell integration (manually edit your profile and remove the cloudctl function/eval)

# Remove configuration
rm -rf ~/.config/cloudctl/
```

---

## Next Steps

Once installation is verified:

1. Read [docs/ARCHITECTURE.md](./ARCHITECTURE.md) for design details
2. Refer to [docs/MULTI_CLOUD.md](./MULTI_CLOUD.md) for cloud-specific information
3. Run `cloudctl --help` for command reference
4. Run `cloudctl <command> --help` for detailed command options
5. Check [README.md](../README.md) for FAQ and security considerations
