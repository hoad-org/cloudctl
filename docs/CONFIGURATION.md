# cloudctl Configuration

## Files

| Path | Purpose |
|------|---------|
| `~/.config/cloudctl/orgs.yaml` | Org configuration |
| `~/.config/cloudctl/current_context.json` | Active context (single source of truth) |
| `~/.aws/sso/cache/` | Standard AWS SSO token cache |

Create or merge `orgs.yaml` with `cloudctl init` (or `cloudctl setup` to merge
sample defaults).

## Schema

The top-level `orgs:` key is a **list** of org objects, each with a `name`.
`enabled_orgs` lists which orgs are active.

```yaml
orgs:
  - name: myorg
    provider: aws
    partition: aws                 # aws | aws-us-gov | aws-cn (optional, default aws)
    sso_start_url: https://d-xxxxxxxxxx.awsapps.com/start
    sso_region: eu-west-2          # region used for the SSO portal call
    default_region: eu-west-2
    allowed_regions: [eu-west-1, eu-west-2, us-east-1]

  - name: gcp-terrorgems
    provider: gcp
    default_project: asatst-gemini-api-v2
    default_region: us-central1
    auth_method: adc               # Application Default Credentials

  - name: azure-craighoad
    provider: azure
    subscription_id: 00000000-0000-0000-0000-000000000000
    tenant_id: 00000000-0000-0000-0000-000000000000
    default_region: eastus

enabled_orgs:
  - myorg
  - gcp-terrorgems
  - azure-craighoad
```

## Field reference

### Org fields (all providers)

| Field | Required | Notes |
|-------|----------|-------|
| `name` | yes | Org identifier used on the command line |
| `provider` | yes | `aws`, `gcp`, or `azure` |
| `default_region` | no | Default `--region` for the org |
| `allowed_regions` | no | Regions offered in pickers / validated |

### AWS-specific

| Field | Required | Notes |
|-------|----------|-------|
| `sso_start_url` | yes | IAM Identity Center start URL |
| `sso_region` | yes | Region for the SSO `get-role-credentials` portal call — **not** the command's `--region` |
| `partition` | no | `aws` (default), `aws-us-gov`, or `aws-cn` |

### GCP-specific

| Field | Notes |
|-------|-------|
| `default_project` | Project id (also injected as `CLOUDSDK_CORE_PROJECT`) |
| `auth_method` | e.g. `adc` (Application Default Credentials) |

`--role` is **not** a functional credential selector on GCP (static IAM).

### Azure-specific

| Field | Notes |
|-------|-------|
| `subscription_id` / `default_subscription` | Target subscription |
| `tenant_id` | Entra tenant |

## `sso_region` vs `--region`

This distinction matters and was the cause of a real "session token not found"
bug:

- **`sso_region`** (org config) is where the SSO portal `get-role-credentials`
  call is made.
- **`--region`** (passed to `exec`/`switch`) is where the *child command* runs;
  it is injected as `AWS_REGION`/`AWS_DEFAULT_REGION`.

They are independent values and are no longer conflated.

## Validate

```bash
cloudctl doctor
```

## Reset

```bash
rm ~/.config/cloudctl/orgs.yaml
cloudctl init
```

## Next steps

- [Quick Start](QUICK_START.md)
- [Command Reference](COMMAND_REFERENCE.md)
- [Troubleshooting](TROUBLESHOOTING.md)
