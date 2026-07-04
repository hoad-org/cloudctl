# cloudctl Security Notes

`cloudctl` is a personal multi-cloud credential runner. This describes its actual
security posture — no compliance claims are made.

## Credential model

- **Short-lived only.** cloudctl vends short-lived credentials on demand (AWS STS
  keys via IAM Identity Center; a GCP access token; Azure `ARM_*` env). It does
  **not** manage or store long-lived static credentials.
- **Injected into a child process, not your shell.** `exec` sets the credential
  environment only for the child command it spawns:

  ```bash
  cloudctl exec --org myorg --account 123456789012 --role ReadOnly \
    --region eu-west-2 -- aws s3 ls
  ```

- **No `AWS_PROFILE` is ever set.** The injected STS keys are self-contained; a
  profile name would shadow them.
- **SSO portal calls use the org's `sso_region`.** Command execution uses your
  `--region`. The two are independent.

## What is stored on disk

| Path | Contents |
|------|----------|
| `~/.config/cloudctl/orgs.yaml` | Org config: SSO start URLs (public), regions, provider settings. **No secrets.** |
| `~/.config/cloudctl/current_context.json` | Active org/account/role/region pointer. **No credentials.** |
| `~/.aws/sso/cache/` | Standard AWS SSO token cache (managed by AWS tooling). |

`orgs.yaml` is written with `0o600` permissions. cloudctl never writes STS keys
or access tokens to its own files.

> Note: an earlier `encryption.py` that AES-encrypted the (public) SSO start URLs
> was removed — it was security theatre that could silently swallow config on a
> decrypt failure.

## Guardrails and break-glass

- **Never hangs.** In a non-TTY / CI / agent context the tool fails fast instead
  of prompting.
- **Sensitive roles** can be gated by `guardrails.py`. In a non-interactive
  context, the justification for a sensitive-role assumption is read from the
  `CLOUDCTL_BREAK_GLASS_REASON` environment variable rather than a prompt.

## Good practice

- Use `cloudctl exec` so credentials stay in the child process and out of your
  shell history.
- Don't export STS keys into your interactive shell or write them to files.
- `cloudctl logout` / `cloudctl cache-clear` when you're done on a shared host.

## Reporting

This is a personal repo; report issues via the repository's GitHub issues
(`hoad-org/cloudctl`). Do not include real credentials in a report.

## Next steps

- [Configuration](CONFIGURATION.md)
- [Command Reference](COMMAND_REFERENCE.md)
