# 🧭 awsctl: The Missing AWS SSO Helper

Welcome to the awsctl wiki. This guide covers user installation, day-to-day usage, advanced topics, quality assurance, security posture, and developer/contributor information.

## Table of Contents

- Introduction

  - What is awsctl?
  - Why Use awsctl? (The Problem Solved)
  - Core Features & Benefits
  - Comparison: awsctl vs. Manual Credential Pasting

- User Guide

  - Prerequisites
  - Installation

    - Recommended: pipx
    - Alternative: Standard pip

  - Initial Setup (awsctl setup)
  - Configuration (orgs.yaml)

    - File Location
    - Structure and Fields
    - Example orgs.yaml

  - Daily Usage

    - Step 1: Login (awsctl login)
    - Step 2: Activate Credentials (awsctl-use)
    - Verifying Credentials
    - Switching Roles/Accounts/Regions
    - Command Reference
    - Troubleshooting

- Quality Assurance

  - Coding Standards
  - Testing Standards
  - Commitment to Quality

- Security

  - Security Model: Wrapping the AWS CLI
  - Credential Handling
  - Authentication Flow
  - Code Security Practices
  - Scope and Assumptions
  - Security Standards Compliance (Tool Perspective)

- Plugin System

  - Overview
  - Okta Plugin Details

    - Purpose
    - Enabling/Disabling
    - Functionality (Current)
    - Advantages over Browser-Only Flow
    - Security Considerations
    - Future Enhancements

- Developer Guide

  - Getting Started
  - Project Structure
  - Core Logic Deep Dive
  - Testing Strategy (tests/, tox.ini)
  - Linting and Formatting (tox.ini, pyproject.toml)
  - Build and Packaging (pyproject.toml, Makefile)
  - Contributing

- License

---

# 🚀 Introduction

## What is awsctl?

awsctl is a user-friendly command-line utility designed to streamline the AWS Single Sign-On (SSO) login process and credential management. It acts as a smart wrapper around the official AWS CLI (aws), automating common tasks and providing a convenient way to get temporary, profile-less AWS credentials into your shell environment.

Its primary philosophy is: Log in once, then switch roles easily.

## Why Use awsctl? (The Problem Solved)

Using AWS SSO with the standard AWS CLI often involves:

- Running aws sso login --profile <base-sso-profile>.
- Manually configuring dozens or hundreds of specific role profiles in ~/.aws/config, like [profile my-account-admin], specifying sso_account_id, sso_role_name, etc.
- Remembering which profile name corresponds to which account/role.
- Constantly setting the AWS_PROFILE environment variable or using --profile flags.
- Refreshing credentials periodically using aws sso get-role-credentials or similar complex commands.
- Alternatively, using the AWS SSO console's "Command line or programmatic access" option, which requires manually copying and pasting temporary credentials (Access Key ID, Secret Key, Session Token) into the terminal multiple times a day.

awsctl simplifies this significantly by:

Leveraging the AWS CLI's underlying SSO token cache (~/.aws/sso/cache/).

Directly calling aws sso get-role-credentials with the cached token when needed via the awsctl-use function.

Exporting the temporary credentials (Access Key ID, Secret Access Key, Session Token) as standard environment variables (AWS_ACCESS_KEY_ID, etc.) directly into the current shell session using eval.

This eliminates the need for numerous role-specific profiles in ~/.aws/config AND removes the error-prone and tedious process of manually copying credentials from the AWS console. It makes switching contexts much faster, more reliable, and more secure.

## Core Features & Benefits

- **One-Time SSO Login**: Authenticate via your browser once per session using awsctl login. awsctl then reuses the secure token cached by the official AWS CLI.

- **Profile-less Credential Management**: Exports temporary credentials directly to environment variables, avoiding clutter in ~/.aws/config.

- **Fast Context Switching**: Use the awsctl-use shell function (awsctl-use --account X --role Y --region Z) to activate credentials for any account/role/region combination instantly, directly within your current shell.

- **Multi-Org Support**: Manage multiple AWS Organizations (different SSO portals) from a single configuration file (~/.awsctl/orgs.yaml).

- **Automated Setup**: awsctl setup creates initial configuration, syncs necessary base AWS profiles, and installs the essential awsctl-use shell helper function.

- **Built-in Diagnostics**: awsctl doctor verifies dependencies (aws, jq, python3) and environment readiness.

- **Reduced Errors**: Eliminates typos and mistakes common when manually copying/pasting credentials.

- **Enhanced Security**: Avoids exposing temporary credentials in shell history or accidentally pasting them into insecure locations. Credentials exist only as environment variables within a specific shell session.

- **Improved Workflow**: Integrates seamlessly into standard terminal workflows; switch roles without leaving your command line.

- **Extensible**: Basic plugin system scaffold included (e.g., for Okta pre-checks).

## Comparison: awsctl vs. Manual Credential Pasting

Manually copying temporary credentials from the AWS SSO console is a common but inefficient and risky practice. Here's why awsctl is superior:

| **Feature**       | **Manual Copy/Paste from AWS Console**                           | **awsctl (awsctl login + awsctl-use)**                      |
| ----------------- | ---------------------------------------------------------------- | ----------------------------------------------------------- |
| **Speed**         | Slow: Navigate console, click role, copy 3 values, paste 3 times | Fast: Single awsctl-use command after initial login         |
| **Reliability**   | Error-prone: Typos, incomplete pastes, pasting old creds         | Reliable: Directly fetches and exports correct, fresh creds |
| **Convenience**   | Requires browser interaction every time                          | Requires browser only for infrequent awsctl login           |
| **Context**       | Requires remembering account IDs, role names                     | Uses clear command-line arguments (--account, --role)       |
| **Shell History** | Credentials may accidentally appear in shell history             | Credentials are eval'd, minimizing history exposure         |
| **Security Risk** | High risk of pasting secrets into wrong windows (chat, etc.)     | Low risk: Credentials stay within the shell environment     |

---

# 📘 User Guide

## Prerequisites

Before installing awsctl, ensure you have the following installed and configured:

### Python: Version 3.9 or higher

- Verify: `python3 --version`

### pip & pipx

The Python package installers. pipx is highly recommended for CLI tool installation.

- Verify: `pip --version`, `pipx --version`
- Install/Upgrade pipx: `python3 -m pip install --user -U pipx && python3 -m pipx ensurepath`

### AWS CLI v2

The official AWS Command Line Interface. awsctl wraps this tool.

- Verify: `aws --version` (Ensure it shows aws-cli/2.x.x)
- Installation: Follow the official AWS CLI installation guide.

### jq

A command-line JSON processor. Used internally by some helper scripts and potentially by awsctl itself.

- Verify: `jq --version`

Installation:

macOS: brew install jq

Ubuntu/Debian: sudo apt update && sudo apt install jq

Fedora/CentOS: sudo dnf install jq

Git: Required for installing awsctl directly from a Git repository.

Verify: git --version

Installation: Usually pre-installed or available via your OS package manager (e.g., brew install git, sudo apt install git).

## Installation

### Installation Methods

- **Recommended**: pipx
- **Alternative**: Standard pip

#### Recommended: pipx

pipx installs Python CLI applications into isolated virtual environments, keeping dependencies clean and avoiding conflicts.

```bash
# Ensure pipx paths are configured (run once)
python3 -m pipx ensurepath

# Install awsctl directly from its Git repository
# (Replace URL with the actual repository location)
pipx install "git+https://github.com/<your-org>/awsctl.git"

# OR, if you have a built wheel file:
# pipx install /path/to/awsctl-*.whl

# IMPORTANT: Run the one-time setup command AFTER installation
awsctl setup
```

#### Alternative: Standard pip

You can install using pip within a virtual environment or globally (not generally recommended for system Python).

```bash
# Create and activate a virtual environment (optional but recommended)
python3 -m venv my-aws-tools
source my-aws-tools/bin/activate

# Install from Git
pip install "git+https://github.com/<your-org>/awsctl.git"

# OR install from a local clone (e.g., for development)
git clone https://github.com/<your-org>/awsctl.git
cd awsctl
pip install -e .  # Editable install

# IMPORTANT: Run the one-time setup command AFTER installation
awsctl setup

# Deactivate virtual environment if you used one
deactivate
```

### Setup and Configuration

#### Initial Setup (awsctl setup)

After installing awsctl via pipx or pip, you must run the `awsctl setup` command once. This performs crucial first-time configuration:

```bash
awsctl setup
```

This command will:

- **Create Configuration Directory**: Ensure `~/.awsctl/` exists.
- **Create Sample orgs.yaml**: If `~/.awsctl/orgs.yaml` doesn't exist or is empty, it creates a sample file with placeholders.
- **Sync Base AWS Config**: Creates or updates sections in `~/.aws/config` required for the underlying `aws sso login` command to work. It sets up `[profile sso-<org_name>]` and `[sso-session <org_name>]` blocks based on your `orgs.yaml`.
- **Inject Shell Function**: Detects your shell (bash or zsh) and adds the `awsctl-use()` helper function to the appropriate startup file (`~/.bashrc` or `~/.zshrc`).

➡️ **Action Required**: After running `awsctl setup`, you must restart your shell or manually source your profile (`source ~/.zshrc` or `source ~/.bashrc`) for the `awsctl-use` function to become available.

## Configuration (orgs.yaml)

awsctl uses a single YAML file to manage connection details for one or more AWS Organizations integrated with AWS SSO.

#### File Location

The configuration file is expected at:

```bash
~/.awsctl/orgs.yaml
```

#### Structure and Fields

The file contains a top-level `orgs` list and an optional `plugins` section.

```yaml
orgs:
  - name: <string> # REQUIRED: A unique, friendly name for this org (used in `awsctl login --org <name>`)
    sso_start_url: <string> # REQUIRED: The "User portal URL" from your AWS SSO dashboard.
    sso_region: <string> # REQUIRED: The AWS region where your AWS SSO instance is configured.
    default_region: <string> # Optional: The default AWS region to use when activating credentials via `awsctl-use` if `--region` is not specified. Defaults to `sso_region` if omitted.
    allowed_regions: [<string>] # Optional: A list of regions you are permitted to use. `awsctl-use` might warn if you try to use a region outside this list (implementation dependent).
    preferred_roles: [<string>] # Optional: A list of role names you frequently use. Future versions might use this for interactive pickers or suggestions.

  - name: another-org
    # ... other org details

plugins: # Optional: Section for enabling plugins.
  enabled: [<string>] # Optional: A list of plugin module names to load (e.g., ['awsctl.plugins.okta']).
```

### Example orgs.yaml

# ~/.awsctl/orgs.yaml

orgs:

- name: development-org
  sso_start_url: https://d-abcdef1234.awsapps.com/start
  sso_region: eu-west-1
  default_region: eu-west-1
  allowed_regions:

  - eu-west-1
  - eu-central-1
    preferred_roles:
  - DeveloperAccess
  - ViewOnlyAccess

- name: production-org
  sso_start_url: https://d-98765fedcba.awsapps.com/start
  sso_region: us-east-1
  default_region: us-east-1

plugins:
enabled: [] # No plugins enabled currently

Action Required: Edit this file after running awsctl setup and replace the placeholder values with your actual AWS SSO details.

## Daily Usage

Using awsctl involves two main steps: logging in (infrequently) and activating credentials (frequently).

### Step 1: Login (awsctl login)

You need to log in to an organization whenever your AWS SSO session expires (typically configured for 8-12 hours by your AWS administrator).

# Log in to the organization named 'development-org' defined in your orgs.yaml

awsctl login --org development-org

This command performs the following actions:

Finds the sso_start_url and sso_region for development-org in your orgs.yaml.

Ensures the corresponding base profile ([profile sso-development-org]) exists in ~/.aws/config.

Executes aws sso login --profile sso-development-org.

The AWS CLI opens your default web browser.

You authenticate with your Identity Provider (e.g., Okta, Azure AD, Google Workspace, built-in AWS SSO directory).

Upon successful authentication, AWS grants access, and the AWS CLI securely stores a short-lived token in the cache directory (~/.aws/sso/cache/).

awsctl confirms the login was successful.

### Step 2: Activate Credentials (awsctl-use)

This is the command you'll use most often. Once you have a valid token in the cache (from awsctl login), you can instantly get temporary credentials for any account/role/region you have access to.

# Syntax:

# awsctl-use --account <ACCOUNT_ID> --role <ROLE_NAME> --region <AWS_REGION>

# Example: Activate credentials for the DeveloperAccess role in account 111122223333, targeting eu-west-1

awsctl-use --account 111122223333 --role DeveloperAccess --region eu-west-1

This shell function (installed by awsctl setup) performs these actions:

Calls the underlying awsctl use ... command.

awsctl use finds the active SSO token for your currently logged-in org from the cache (~/.aws/sso/cache/).

It executes aws sso get-role-credentials --access-token <token> --account-id <id> --role-name <role>.

The AWS CLI communicates with the AWS SSO service, which validates your token and permission to assume the role.

AWS SSO returns temporary credentials (AWS Access Key ID, Secret Access Key, Session Token) valid for a limited time (usually 1 hour).

awsctl use formats these credentials as export AWS_ACCESS_KEY_ID="...", export AWS_SECRET_ACCESS_KEY="...", etc., and prints them to standard output.

The awsctl-use shell function captures this output and uses the shell's built-in eval command to execute the export lines, setting the environment variables in your current shell session.

It prints a confirmation message indicating which role has been activated.

## Verifying Credentials

After running awsctl-use, you can verify that the credentials are active using standard AWS CLI commands:

# Check the active identity (should show the assumed role ARN)

aws sts get-caller-identity

# List S3 buckets (or any other AWS command)

aws s3 ls

Important: These credentials are only set for your current shell session. Opening a new terminal window or tab will require running awsctl-use again.

## Switching Roles/Accounts/Regions

Simply run the awsctl-use command again with the new parameters:

# Switch to ViewOnlyAccess in the same account/region

awsctl-use --account 111122223333 --role ViewOnlyAccess --region eu-west-1

# Switch to a different account and region

awsctl-use --account 444455556666 --role AdminRole --region us-east-1

## Command Reference

awsctl setup: Performs first-time setup (creates config, installs shell function). Run once after installation.

awsctl login --org <name>: Initiates browser-based SSO login for the specified org. Run when your session expires.

awsctl accounts [--json]: Lists AWS accounts accessible via the current SSO session.

awsctl roles --account <id> [--json]: Lists roles assumable in the specified account via the current SSO session.

awsctl use --account <id> --role <name> --region <region>: (Low-level) Prints export commands for the requested credentials. Designed for use with eval.

awsctl-use --account <id> --role <name> --region <region>: (Shell Function) Activates credentials for the requested target in the current shell. This is the primary command for daily use.

awsctl config sync: Updates ~/.aws/config with base SSO profiles from orgs.yaml. Usually only needed if you manually edit orgs.yaml.

awsctl doctor: Checks for required dependencies (aws, jq, python3).

awsctl orgs: Lists organizations defined in orgs.yaml.

awsctl init-config: Prints a sample orgs.yaml to standard output.

awsctl help: Displays the built-in help message.

awsctl --version or -V: Prints the installed version of awsctl.

## Troubleshooting

awsctl: command not found:

Ensure awsctl was installed correctly.

If using pipx, make sure its bin directory is in your PATH (run pipx ensurepath).

If using pip in a virtual environment, ensure the environment is activated.

awsctl-use: command not found:

Did you run awsctl setup after installing?

Did you restart your shell or source your profile (source ~/.zshrc or source ~/.bashrc) after running setup?

Check your ~/.zshrc or ~/.bashrc to confirm the awsctl-use() function block is present.

awsctl: failed to get credentials. (from awsctl-use):

Most Common: Your SSO session likely expired. Run awsctl login --org <your-org> again.

The accessToken in ~/.aws/sso/cache/ might be invalid or corrupted. Try logging in again.

You might not have permission to assume the specific --role in the specified --account. Verify your permissions in the AWS console.

Double-check the --account, --role, and --region parameters for typos.

Error loading SSO Token: Token for ... does not exist:

You haven't successfully logged in to that specific SSO sso_start_url recently. Run awsctl login --org <org-using-that-url>.

Your ~/.aws/sso/cache/ directory might be empty or missing files. Check its contents.

Browser opens, but login fails: This is usually an issue with your upstream Identity Provider (Okta, Azure AD, etc.) or your AWS SSO configuration itself, not awsctl. Check with your AWS administrator.

Config not found: ~/.awsctl/orgs.yaml: Run awsctl setup.

✨ Quality Assurance

awsctl is developed with a strong emphasis on code quality, correctness, and maintainability.

## Coding Standards

PEP 8 Compliance: Code formatting adheres strictly to PEP 8 style guidelines, enforced automatically by the Black code formatter. This ensures consistency and readability.

Linting: Ruff is used for comprehensive linting. It performs fast static analysis to catch potential errors, bugs, style issues, and anti-patterns beyond basic formatting. Import sorting is also handled by Ruff.

Type Hinting (PEP 484): All function signatures and major variables include type hints. This improves code clarity, enables static analysis, and helps prevent runtime type errors.

Static Type Checking: MyPy is used in conjunction with type hints to perform static analysis, catching type inconsistencies before runtime. Configuration in mypy.ini ensures strict checks.

Modularity: The codebase is organized into modules with specific responsibilities (e.g., sso_cache.py for token handling, accounts.py for AWS CLI listing calls, cli.py for argument parsing and dispatch).

## Testing Standards

Unit Testing: A comprehensive suite of unit tests using Pytest covers individual functions and modules. Mocking (pytest-mock, unittest.mock) is used extensively to isolate components and simulate external interactions (like file system access and subprocess calls) without relying on live AWS services or specific user environments.

End-to-End Smoke Testing: Bash scripts (scripts/full_smoke\*.sh) provide automated end-to-end testing. They simulate a user installing and running key awsctl commands in a clean, temporary environment, verifying core workflows and interactions. These tests catch integration issues that unit tests might miss.

Environment Management: Tox is used to automate testing across multiple Python versions (3.9+) and to manage isolated environments for testing and linting. This ensures compatibility and consistent results.

Continuous Integration (CI): A GitHub Actions workflow (.github/workflows/test.yml) automatically runs linters (tox -e lint), unit tests (tox -e py across multiple Python versions and OSs), and build validation (tox -e build) on every push and pull request, ensuring code quality is maintained.

## Commitment to Quality

The combination of strict coding standards, comprehensive testing (unit and E2E), static analysis, and automated CI ensures that awsctl is built to a high standard. This minimizes bugs, improves reliability, and makes the tool easier to maintain and extend in the future.

# 🔒 Security

Security is a primary consideration in awsctl's design. The tool aims to enhance, not compromise, the security posture established by AWS SSO and the official AWS CLI.

## Security Model: Wrapping the AWS CLI

### Core Principle

awsctl wraps the official, security-vetted AWS CLI (aws) for all interactions with AWS services. It does not reimplement AWS APIs or authentication protocols.

### Reliance on AWS CLI Security

awsctl relies entirely on the security mechanisms built into the AWS CLI for:

- Handling the secure browser-based SSO authentication flow (aws sso login).
- Storing the short-lived SSO accessToken securely in the ~/.aws/sso/cache/ directory (managed by the AWS CLI).
- Making authenticated API calls to AWS SSO (list-accounts, list-account-roles, get-role-credentials) using the cached token.

## Credential Handling

No Long-Term Credential Storage: awsctl never stores long-term AWS credentials (like IAM user keys).

Ephemeral Credentials: The temporary credentials (Access Key ID, Secret Key, Session Token) obtained via aws sso get-role-credentials are never written to disk by awsctl.

Environment Variables Only: The awsctl-use function directly exports these temporary credentials into the current shell's environment variables. They exist only in the memory of that specific shell process and its children.

Reduced Risk vs. Manual Pasting: This model significantly reduces the risk associated with manually copying and pasting credentials, where they could be accidentally saved in files, shell history, or pasted into unintended applications (like chat windows).

## Authentication Flow

Delegation to AWS CLI: The primary authentication (logging into your SSO provider) is handled entirely by aws sso login, which awsctl login invokes. This leverages the secure browser interaction and token caching implemented by AWS.

No Credential Interception: awsctl does not intercept or handle your primary SSO username/password or MFA tokens.

## Code Security Practices

Standard Libraries: The tool primarily uses Python's standard libraries and well-vetted third-party libraries (PyYAML, colorama, InquirerPy) for core functionality.

Subprocess Usage: Calls to the external aws CLI are made securely using Python's subprocess module, avoiding shell injection vulnerabilities by passing arguments as a list.

Input Handling: User-provided inputs (like account IDs, role names from CLI arguments) are treated as strings and passed directly to the corresponding AWS CLI flags. They are not used to construct shell commands directly.

Security Linters: Development dependencies include ruff (which incorporates checks from tools like flake8-bandit) and potentially bandit and safety (listed in dev dependencies) to scan for common security vulnerabilities during development and CI.

## Scope and Assumptions

Local Execution: awsctl is designed to run locally on a developer's machine. It assumes the underlying operating system and user environment are reasonably secure.

AWS CLI Trust: The security model fundamentally relies on the security and integrity of the installed AWS CLI v2 executable.

SSO Cache Permissions: It assumes the file permissions on the ~/.aws/sso/cache/ directory (managed by the AWS CLI) are appropriately restricted by the operating system.

## Security Standards Compliance (Tool Perspective)

While awsctl itself doesn't directly handle sensitive authentication secrets like passwords, it operates in a security-conscious manner:

Principle of Least Privilege: By facilitating the use of temporary, role-based credentials obtained via SSO, it aligns with the security principle of least privilege, as opposed to using long-lived IAM user keys.

Secure Defaults: It relies on the secure implementation details of the official AWS CLI.

Reduced Attack Surface: By avoiding the storage of temporary credentials to disk and minimizing manual handling, it reduces the potential attack surface compared to alternative methods.

In summary, awsctl enhances usability without compromising the security foundation provided by AWS SSO and the AWS CLI. It achieves this by securely orchestrating the official tools rather than reimplementing sensitive operations.

🔌 Plugin System

Overview

awsctl includes a basic plugin system to allow for extending its functionality, primarily by adding checks or actions around the core commands.

Loading: Plugins are Python modules listed in the plugins.enabled section of ~/.awsctl/orgs.yaml.

Hooks: The system currently supports a pre_login(org: dict) hook. When awsctl login is run, the plugin loader (awsctl/plugins/**init**.py) imports the enabled plugin modules and calls the pre_login function in each module that defines it, passing the configuration dictionary for the target organization.

Error Handling: Plugin loading is best-effort. If a plugin fails to import or its hook raises an exception, awsctl typically logs a warning but continues execution.

Okta Plugin Details

An example plugin scaffold, awsctl.plugins.okta, is included.

Purpose

The primary goal of the Okta plugin (as currently scaffolded) is to provide a place to add pre-login checks or preparatory steps specific to environments where AWS SSO is federated through Okta. It does not aim to bypass Okta authentication or the standard browser-based flow initiated by aws sso login.

Enabling/Disabling

To enable the Okta plugin, add its module path to your orgs.yaml:

# ~/.awsctl/orgs.yaml

orgs:

- name: my-okta-federated-org
  sso_start_url: ...
  sso_region: ...
  # ... other org details

plugins:
enabled: - awsctl.plugins.okta # Enable the Okta plugin

To disable it, simply remove the entry or leave the enabled list empty ([]).

Functionality (Current)

The current awsctl/plugins/okta.py is primarily a placeholder. Its pre_login hook simply prints an informational message and performs a basic check for the presence of sso_start_url in the org configuration.

# awsctl/plugins/okta.py

from awsctl.utils import info, warn

def pre_login(org: dict) -> None:
info("Okta plugin: pre-login checks starting") # Example check:
if "sso_start_url" not in org:
warn("Okta plugin: org missing sso_start_url; nothing to do") # Future logic could go here

Advantages over Browser-Only Flow

While the current scaffold has limited functionality, potential advantages of extending this plugin include:

Automated Pre-Checks: Could verify Okta session validity, check for required MFA factors, or query Okta APIs before triggering the potentially disruptive browser login flow.

Contextual Information: Could provide users with specific instructions or warnings based on their Okta status or group memberships.

Centralized Logic: Encapsulates Okta-specific logic separate from the core awsctl functions.

Security Considerations

Local Execution: Like awsctl itself, the plugin code runs locally on the user's machine.

No Credential Handling (Current): The scaffold plugin does not handle Okta credentials or tokens. Any future extensions that do handle Okta authentication would need careful security review.

Relies on AWS CLI Security: The plugin hooks run before aws sso login is invoked. The actual AWS SSO authentication remains handled securely by the AWS CLI.

Scope: The plugin only has access to the organization configuration dictionary passed into its hooks.

Future Enhancements

The Okta plugin could be extended to:

Use Okta APIs to check session status before login.

Provide guidance on MFA setup or device enrollment.

Potentially support Okta device authorization flows (though this might require significant additional libraries and security considerations).

# 👨‍💻 Developer Guide

## Getting Started

### Clone the Repository

```bash
git clone https://github.com/<your-org>/awsctl.git
cd awsctl
```

### Use the Makefile for Setup

The Makefile provides convenient targets for setting up a development environment using tox.

```bash
make setup
```

# Or directly using tox for a specific Python version

# tox -e py311

This creates a virtual environment (usually in .tox/py... or venv/), installs dependencies, and installs awsctl in editable mode (pip install -e .).

Activate Virtual Environment:

# If using make setup -> venv/

source venv/bin/activate

# If using tox -> .tox/py.../bin/

# source .tox/py311/bin/activate

## Project Structure

(See detailed structure in previous sections)

## Core Logic Deep Dive

(See detailed logic flow in previous sections: Config -> Cache -> CLI Interaction -> Export -> Shell Integration -> Entrypoint)

## Testing Strategy (tests/, tox.ini)

(See detailed strategy in Quality Assurance section: Unit Tests, Smoke Tests, Tox Orchestration)

### Running Unit Tests

# Run tests using the current virtual environment's Python

pytest -v

# Run tests for a specific Python version using tox

tox -e py311

### Running Smoke Tests

# Run the extended smoke test (recommended)

bash scripts/full_smoke_ext.sh

# Review detailed logs and summary

# open tools/smoke_artifacts/$(ls -1 tools/smoke_artifacts | tail -1)

## Linting and Formatting (tox.ini, pyproject.toml)

(See details in Quality Assurance section: Black, Ruff, MyPy)

Commands (via tox):

# Check formatting, linting, and types

tox -e lint

# Auto-format code with Black

black awsctl tests

# Auto-fix fixable linting errors with Ruff

ruff check awsctl tests --fix

## Build and Packaging (pyproject.toml, Makefile)

Build System: Uses standard setuptools with configuration defined in pyproject.toml (PEP 517/518).

Dependencies: Defined in pyproject.toml ([project.dependencies], [project.optional-dependencies.dev]).

Console Script: Entry point defined in pyproject.toml ([project.scripts]).

Building:

python -m build
twine check dist/\* # Optional validation

Makefile: Provides convenience targets: make build, make install (via pipx), make uninstall, make setup, make lint, make test.

## Contributing

Fork and Clone: Fork the repository on GitHub and clone your fork locally.

Setup Environment: Run make setup and activate the virtual environment (source venv/bin/activate).

Create Branch: Create a new feature branch (git checkout -b feature/my-new-feature).

Make Changes: Implement your feature or bug fix.

Add Tests: Write unit tests (tests/) for your changes. Consider if smoke test updates are needed.

Run Checks: Ensure all tests and linters pass:

pytest -v

tox -e lint (run black awsctl tests and ruff check awsctl tests --fix if needed)

Commit: Commit your changes with a clear message following conventional commit guidelines if applicable.

Push: Push your branch to your fork (git push origin feature/my-new-feature).

Pull Request: Open a pull request against the main repository's main branch. Describe your changes clearly, link any relevant issues, and ensure CI checks pass.

©️ License

(Assuming MIT based on source code comments. Add the actual license text or link here.)

This project is licensed under the MIT License. See the LICENSE file for details.
