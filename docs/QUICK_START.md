# CloudCtl Quick Start Guide

Get up and running with CloudCtl in 5 minutes.

## 1. Install CloudCtl

```bash
python3.12 -m pip install cloudctl
```

## 2. Initialize Configuration

```bash
python3.12 -m cloudctl init
```

This creates `~/.config/cloudctl/orgs.yaml` with prompts for your organization.

## 3. Verify Setup

```bash
python3.12 -m cloudctl doctor
```

All checks should show ✅.

## 4. Your First Command

### List Available Accounts

```bash
python3.12 -m cloudctl accounts --org bt-avm
```

Output:
```
Account ID       Account Name
235494790978     production
123456789012     staging
```

### List Your Roles

```bash
python3.12 -m cloudctl list-roles --org bt-avm --assigned
```

Output:
```
✓ Your assigned roles in bt-avm:
  - administrator
  - developer
  - read-only
```

## 5. Execute AWS Commands

```bash
python3.12 -m cloudctl exec \
  --org bt-avm \
  --account 235494790978 \
  --role read-only \
  --region us-east-1 \
  --non-interactive \
  -- aws s3 ls
```

## Common First Tasks

### List S3 Buckets
```bash
python3.12 -m cloudctl exec \
  --org bt-avm \
  --account 235494790978 \
  --role read-only \
  --region us-east-1 \
  --non-interactive \
  -- aws s3 ls
```

### Describe EC2 Instances
```bash
python3.12 -m cloudctl exec \
  --org bt-avm \
  --account 235494790978 \
  --role read-only \
  --region us-east-1 \
  --non-interactive \
  -- aws ec2 describe-instances
```

### Run Terraform
```bash
python3.12 -m cloudctl exec \
  --org bt-avm \
  --account 235494790978 \
  --role administrator \
  --region us-east-1 \
  --non-interactive \
  -- terraform plan
```

## Critical Rules

1. **Use `--non-interactive`** — Required for automation
2. **Put everything in ONE command** — Don't split across multiple calls
3. **Discover roles first** — Always run `list-roles` before exec
4. **Check `doctor` output** — All checks must pass

## Next Steps

- [Configuration](CONFIGURATION.md) — Advanced setup
- [Command Reference](COMMAND_REFERENCE.md) — All commands
- [Troubleshooting](TROUBLESHOOTING.md) — Error solutions
