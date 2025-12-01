# awsctl User Guide (v2.0.0)

`awsctl` is a security-focused helper for AWS IAM Identity Center (SSO).  
It allows you to obtain short-lived credentials for your shell without ever storing sensitive keys on your disk.

---

## 1. Installation

The recommended method is `pipx`, which installs the tool in an isolated environment and links the binary to your `PATH`.

    pipx install "git+https://github.com/your-org/awsctl.git@v2.0.0"

Verify installation:

    awsctl --version

---

## 2. First-Time Setup

Run the interactive wizard. This handles all configuration and shell integration for you.

    awsctl setup

⚠️ **Critical Step:** The setup wizard modifies your shell configuration (`~/.bashrc` or `~/.zshrc`).  
You must reload your shell for these changes to take effect:

    source ~/.zshrc
    # or
    source ~/.bashrc

After reloading, `awsctl` should be a function, not just a binary.

Confirm with:

    type awsctl

You should see output similar to:

    awsctl is a function

---

## 3. Daily Workflow

### Step 1: Login

Authenticate with your Identity Provider (Okta, AzureAD, etc.):

    awsctl login --org engineering

This opens your browser. Once approved, the AWS SSO token is cached securely by AWS CLI v2.

### Step 2: Switch Context

Select your Account, Role, and Region interactively:

    awsctl switch

Use the arrow keys or type to fuzzy-search.

Guardrails from the Registry enforce:

- Allowed regions.
- Preferred role ordering.

### Step 3: Work

Your shell is now populated with:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_SESSION_TOKEN`
- `AWS_DEFAULT_REGION`

You can now use the standard AWS tools:

    aws s3 ls
    terraform plan

### Step 4: Toggle Back (Smart Switching)

Need to jump back to the previous account you were working in?

    awsctl switch -

This works similarly to `cd -` in your terminal and toggles between your current and previous contexts.

---

## 4. Advanced Usage

### 4.1 Non-Interactive Switching

Useful for scripts or when you know exactly where you are going:

    awsctl switch --account 123456789012 --role AdministratorAccess --region us-east-1

### 4.2 Exec (One-Shot Commands)

Run a command in a specific context without changing your current shell variables.

Implicit (uses last known context):

    awsctl exec -- aws s3 ls

Explicit (overrides context):

    awsctl exec --account 123456789012 --role ReadOnly -- aws s3 ls

### 4.3 Dotfile Export

Generate a `.env` file for Docker or other tools:

    awsctl env > .env

---

## 5. Troubleshooting

**"Region not allowed"**

- Your organization has configured Guardrails in the Registry.
- You cannot switch to regions that are not explicitly allowed by the platform team.
- Check diagnostics:

      awsctl doctor

**"Command not found: _awsctl_bin"**

- The internal binary is missing from your `PATH`.
- Ensure `~/.local/bin` is in your `PATH`, or reinstall via:

      pipx ensurepath
      pipx install --force "git+https://github.com/your-org/awsctl.git@v2.0.0"

**"Switch doesn't change my variables"**

- The shell wrapper is not loaded.
- Check:

      type awsctl

  If it says `awsctl is /usr/bin/awsctl`, the wrapper is missing. It should say `awsctl is a function`.

- Reload:

      source ~/.zshrc
      # or
      source ~/.bashrc

**"New account not showing up"**

- AWS CLI caches account lists aggressively.
- Force a refresh:

      awsctl refresh

---

## 6. Where to Go Next

- Command details: `docs/CLI_REFERENCE.md`
- Security posture: `docs/SECURITY_APPRAISAL.md`
- Admin and guardrails: `docs/ADMIN_GUIDE.md`
- Troubleshooting: `docs/TROUBLESHOOTING.md`
