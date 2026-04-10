# Claude Instructions — awsctl Context Safety

## CRITICAL: Always Switch Context Before Running Commands

**You MUST run `awsctl switch` before executing ANY AWS command in this repository.**

Multiple Claude sessions can be active simultaneously. Each session may have a different AWS account and role loaded into the shell environment. Running a command intended for account A while the context is set to account B causes unintended changes in the wrong account.

### Rule: Switch First, Always

```bash
# ALWAYS do this first — never skip it
awsctl switch <org> <account-id> <role>

# Verify the context before running anything
awsctl env

# THEN run your command
terraform plan
aws s3 ls
```

### Configured Organisations

| Alias   | Partition     | SSO Region     | Description                              |
|---------|---------------|----------------|------------------------------------------|
| bt-avm  | aws           | us-east-1      | BeyondTrust AVM — Commercial AWS         |
| fdr-gvc | aws-us-gov    | us-gov-east-1  | FedRAMP GovCloud — AWS GovCloud (US)     |

### Example: Switching to BeyondTrust Commercial

```bash
awsctl switch bt-avm
awsctl env  # confirm context before proceeding
```

### Example: Switching to FedRAMP GovCloud

```bash
awsctl switch fdr-gvc
awsctl env  # confirm context before proceeding
```

## Why This Matters

- `awsctl` stores the active org/account/role/region in `~/.config/awsctl/context.json`
- The shell function `awsctl` exports credentials into the current shell session
- If two Claude sessions are running: Session A may have `bt-avm` loaded, Session B may have `fdr-gvc` loaded
- Without explicit switching, the **wrong credentials are used silently** — there is no warning
- GovCloud (`fdr-gvc`) commands run in Commercial (`bt-avm`) context will fail with `InvalidClientTokenId` or worse, operate on the wrong partition

## Checklist Before Any AWS/Terraform Operation

1. `awsctl switch <org>` — set the correct org context
2. `awsctl env` — verify account ID, role, region match your intent
3. If using Terraform: confirm `AWS_PROFILE` or `AWS_ACCESS_KEY_ID` point to the right account
4. Never assume the previous Claude session left the correct context active

## Shell Wrapper Architecture

- `awsctl` — shell function that captures `export K=V` output and applies it to the current shell
- `_awsctl_bin` — raw Python binary; does NOT modify parent shell environment
- Always use the `awsctl` shell function (not `_awsctl_bin`) to switch contexts

## Useful Commands

```bash
awsctl list              # show configured orgs
awsctl env               # show active context (org, account, role, region)
awsctl switch <org>      # interactive account/role picker for an org
awsctl login <org>       # (re)authenticate with SSO
awsctl cache-clear       # clear cached credentials and SSO tokens
awsctl doctor            # check installation and config health
```
