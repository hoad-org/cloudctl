# CloudCtl v1.0.0-beta — Ephemeral Cloud Credential Manager

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![FedRAMP Ready](https://img.shields.io/badge/FedRAMP-Ready-005288)](docs/SECURITY.md)

**Securely manage ephemeral credentials for AWS, Azure, and GCP with built-in safety gates, approval workflows, and complete audit trails.**

CloudCtl is an enterprise-grade credential manager that:
- ✅ **Multi-cloud support** — AWS, Azure, GCP with consistent CLI
- ✅ **Ephemeral credentials** — Temporary tokens, automatic cleanup, zero long-lived keys
- ✅ **Safety gates** — Approval workflows, MFA enforcement, rate limiting
- ✅ **Zero-trust design** — Credentials never stored on disk or exported
- ✅ **Complete audit trail** — Every operation logged and immutable
- ✅ **Agent-native** — Designed for autonomous/agentic use (see *AI Agents & Automation*)

---

## Quick Start

### Installation

```bash
python3.12 -m pip install cloudctl
```

### Verify Setup

```bash
python3.12 -m cloudctl doctor
```

### Your First Command

List available accounts:
```bash
python3.12 -m cloudctl accounts --org bt-avm
```

Execute AWS commands with assumed role:
```bash
python3.12 -m cloudctl exec \
  --org bt-avm \
  --account 235494790978 \
  --role read-only \
  --region us-east-1 \
  --non-interactive \
  -- aws s3 ls
```

---

## Documentation

All documentation is available in the `docs/` directory:

### 🔧 Planning & Architecture

| Guide | Purpose |
|-------|---------|
| **[Installation & Registration Improvement Report](docs/INSTALLATION_REGISTRATION_IMPROVEMENT_REPORT.md)** | **[STRATEGIC]** Comprehensive analysis of installation improvements, borrowing patterns from production MCP servers. Roadmap for OAuth wizard, keyring integration, binary distribution, and Docker containerization. 7-week implementation plan. |

### 📚 User Documentation

| Guide | Purpose |
|-------|---------|
| **[Installation](docs/INSTALLATION.md)** | Install and verify CloudCtl |
| **[Quick Start](docs/QUICK_START.md)** | Get up and running in 5 minutes |
| **[Configuration](docs/CONFIGURATION.md)** | Set up orgs.yaml and approval gates |
| **[Command Reference](docs/COMMAND_REFERENCE.md)** | Complete reference for all commands |
| **[Error Reference](docs/ERROR_REFERENCE.md)** | Quick lookup for error messages |
| **[Troubleshooting](docs/TROUBLESHOOTING.md)** | Detailed troubleshooting procedures |
| **[Security](docs/SECURITY.md)** | Security best practices and compliance |
| **[Development](docs/DEVELOPMENT.md)** | Contributing and development setup |

---

## Key Features

### Ephemeral Credentials
- Temporary tokens generated on-demand
- Automatic cleanup when expired (1-12 hours)
- Never stored on disk
- Perfect audit trail

### Safety Gates
- **Approval Gates** — Sensitive roles require human review (1-2 approvers, 30-second timeout)
- **MFA Enforcement** — TOTP, SMS, WebAuthn for high-risk operations
- **Rate Limiting** — 5 logins/hour, 10 role switches/minute
- **Ownership Verification** — Only authorized users can perform operations

### Multi-Cloud Support
- **AWS** — Commercial and GovCloud with separate partitions
- **Azure** — Entra ID with token-based authentication
- **GCP** — Service accounts with OIDC federation

### Enterprise Ready
- **Audit Logging** — Immutable record of all operations
- **FedRAMP Compliant** — For government and regulated workloads
- **Zero-Trust Model** — Credentials never accessible to users
- **Encryption** — Field-level encryption for sensitive configuration

---

## Core Commands

```bash
# Verify setup
python3.12 -m cloudctl doctor

# List organizations
python3.12 -m cloudctl list

# List accounts in organization
python3.12 -m cloudctl accounts --org bt-avm

# List available roles
python3.12 -m cloudctl list-roles --org bt-avm --assigned

# Execute AWS commands (primary command for automation)
# Provide --org/--account/--role/--region explicitly so exec never needs a picker.
python3.12 -m cloudctl exec \
  --org bt-avm \
  --account 235494790978 \
  --role read-only \
  --region us-east-1 \
  -- aws s3 ls

# Logout
python3.12 -m cloudctl logout
```

**Critical Rule:** Put all operations in ONE command. `exec` takes **no**
`--non-interactive` flag — it is non-interactive by nature and, given full
`--org/--account/--role/--region`, never prompts (with incomplete args in a
non-TTY context it fails fast rather than hanging on a picker). The
`--non-interactive` flag belongs to `login`/`switch` (see *AI Agents & Automation*).

---

## AI Agents & Automation

CloudCtl is built for autonomous, agentic use. The login step is the one
human-in-the-loop control your security team needs: a browser window opens and a
human clicks **Approve** (AWS IAM Identity Center / `gcloud auth login` /
`az login`). Everything else runs unattended on the resulting short-lived,
on-disk-free credentials.

**Agents should set context explicitly with `cloudctl switch --non-interactive`,
not with profiles.** The `--non-interactive` flag (valid on `login` and `switch`)
makes the command require every argument and fail fast with a clear error instead
of showing an interactive account/role picker:

```bash
# Agent-friendly: fully explicit, no prompts, fails fast if anything is missing
python3.12 -m cloudctl switch bt-avm \
  --account 235494790978 \
  --role read-only \
  --region us-east-1 \
  --non-interactive

# Then run commands on the active context (exec needs no --non-interactive flag)
python3.12 -m cloudctl exec -- aws s3 ls
```

**Why not profiles?** Profiles (`cloudctl profile save/load`) are a **local-only**
convenience for **humans** working interactively at one machine — they are not
synced, not shared, and carry no credentials. An agent (or any automation) must
not rely on a profile existing; it should pass `--org/--account/--role/--region`
explicitly (or use `cloudctl switch ... --non-interactive`) so the same command
is reproducible on any host.

---

## Real-World Example

### List and Filter S3 Buckets

```bash
python3.12 -m cloudctl exec \
  --org bt-avm \
  --account 235494790978 \
  --role read-only \
  --region us-east-1 \
  --non-interactive \
  -- bash -c "aws s3 ls | grep -i 'prod'"
```

### Run Terraform

```bash
python3.12 -m cloudctl exec \
  --org bt-avm \
  --account 235494790978 \
  --role administrator \
  --region us-east-1 \
  --non-interactive \
  -- terraform apply -auto-approve
```

### Use with GitHub Actions

```yaml
name: Deploy
on: [workflow_dispatch]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Deploy Infrastructure
        run: |
          python3.12 -m cloudctl exec \
            --org bt-avm \
            --account ${{ secrets.AWS_ACCOUNT }} \
            --role administrator \
            --region us-east-1 \
            --non-interactive \
            -- terraform apply
```

---

## Critical Usage Rules

1. **Use `--non-interactive`** — Required for automation
2. **Everything in ONE command** — Each Bash call is independent; credentials don't persist
3. **Discover roles first** — Always run `list-roles` before assuming a role
4. **Verify operations completed** — CloudCtl success ≠ operation success (check logs/resources)

Violating these rules leads to credential loss, failed operations, or security violations.

---

## Training

Complete usage and command reference lives in this README and the `docs/`
directory (see *Documentation* above).

**37 critical gaps covered:**
- Exact package and field names
- Approval gates and MFA
- Error diagnosis (20+ scenarios)
- Known issues and workarounds
- Monitoring patterns

---

## Version

**v1.0.0-beta** (June 2026)

- ✅ Multi-cloud support (AWS, Azure, GCP)
- ✅ Ephemeral credential management
- ✅ Approval gates and safety workflows
- ✅ Complete audit trail
- ✅ Agent-native (autonomous/agentic use)

**Status:** Production-grade features, still hardening from recent bug fixes. Use with confidence; expect improvements.

---

## Getting Help

1. **Quick errors?** Check [Error Reference](docs/ERROR_REFERENCE.md)
2. **Stuck?** Read [Troubleshooting](docs/TROUBLESHOOTING.md)
3. **How do I...?** See [Command Reference](docs/COMMAND_REFERENCE.md)
4. **Setting up?** Follow [Installation](docs/INSTALLATION.md)
5. **Still stuck?** Contact platform team with output of `cloudctl doctor`

---

## Security

CloudCtl implements:
- Zero-trust architecture (credentials never accessible to users)
- Ephemeral credentials (auto-cleanup, no long-lived keys)
- Approval gates (sensitive operations require review)
- Complete audit trail (every operation logged)
- MFA enforcement (TOTP, SMS, WebAuthn)
- FedRAMP compliance (for government workloads)

See [Security](docs/SECURITY.md) for complete details.

---

## Contributing

For developers:
1. Review [Development Guide](docs/DEVELOPMENT.md)
2. Check [CLAUDE.md](CLAUDE.md) for repo conventions
3. Submit PR with tests and documentation

---

## License

Proprietary. See [LICENSE](LICENSE) for details.

---

## Support

- **Documentation**: Start with [Quick Start](docs/QUICK_START.md)
- **Issues**: GitHub Issues on BT-IT-Infrastructure-CloudOps/cloudctl
- **Platform Team**: Contact for approval gate decisions or escalations
- **Training**: See linked training documentation above

---

Made with ❤️ by BeyondTrust IS CloudOps
