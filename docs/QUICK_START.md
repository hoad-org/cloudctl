# cloudctl Quick Start

Get running in a few minutes. This describes the tool as it actually behaves
(version `1.0.0b0`, beta).

## 1. Install

Editable install from a clone of this repo:

```bash
python3.12 -m pip install -e .
cloudctl doctor        # sanity-check the install and config
```

## 2. Configure

Config lives at `~/.config/cloudctl/orgs.yaml`. Create or merge it:

```bash
cloudctl init          # create / merge orgs.yaml
```

Configured orgs on a typical setup:

| Org | Provider | Notes |
|-----|----------|-------|
| `myorg` | AWS | IAM Identity Center, SSO region `eu-west-2` |
| `gcp-terrorgems` | GCP | ADC auth |
| `azure-craighoad` | Azure | subscription/tenant configured |

## 3. Authenticate

```bash
cloudctl login myorg          # opens a browser to complete SSO
```

## 4. Discover accounts and roles

```bash
cloudctl accounts myorg --format json
cloudctl list-roles myorg --account 123456789012 --format json
```

## 5. Run a command with credentials injected

`exec` is the canonical, stateless form for automation. It needs a literal `--`
before the child command:

```bash
cloudctl exec --org myorg --account 123456789012 --role ReadOnly \
  --region eu-west-2 -- aws sts get-caller-identity
```

More examples:

```bash
# List S3 buckets
cloudctl exec --org myorg --account 123456789012 --role ReadOnly \
  --region eu-west-2 -- aws s3 ls

# Terraform plan with injected short-lived creds
cloudctl exec --org myorg --account 123456789012 --role AdministratorAccess \
  --region eu-west-2 -- terraform plan
```

## Things to know (the agent contract)

1. **`exec` needs a literal `--`** before the child command, or argparse will
   consume flags like `--query`/`--output` meant for the child.
2. **`--region` is the region the child command runs in.** It is injected as
   `AWS_REGION`/`AWS_DEFAULT_REGION`. The SSO portal call internally uses the
   org's own `sso_region` (e.g. `eu-west-2`) — the two are not the same value.
3. **No `AWS_PROFILE` is ever set.** Injected STS keys are self-contained.
4. **Never hangs.** In a non-TTY / CI / agent context, `switch` fails fast
   asking for explicit `--account/--role/--region` instead of showing a picker.

## Next steps

- [Installation](INSTALLATION.md) — full install guide
- [Command Reference](COMMAND_REFERENCE.md) — all commands
- [Configuration](CONFIGURATION.md) — orgs.yaml and context
- [Exit Codes](EXIT_CODES.md) — agent-facing exit codes
- [Troubleshooting](TROUBLESHOOTING.md) — common problems
