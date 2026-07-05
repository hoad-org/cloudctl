# Role Validation

`cloudctl` validates a requested role against the roles actually available for an
account, and suggests close matches when the name is wrong. Implementation:
`src/cloudctl/role_validator.py`.

## What it does

1. **Queries available roles** for the account via the provider
   (`get_available_roles`).
2. **Validates** the requested role (case-insensitive) before attempting
   credential retrieval (`validate_role`).
3. **Suggests corrections** for typos and partial names
   (`find_role_suggestions`).
4. In interactive mode, can prompt you to pick from the available roles
   (`validate_and_prompt_for_role`).

## The problem it solves

If the real role is `AdministratorAccess` but you request `admin`, the raw
provider error (e.g. `ForbiddenException`) doesn't tell you the role name was
wrong. Role validation catches this up front and shows the valid options.

## Matching strategy

`find_role_suggestions` ranks candidates in this order:

1. **Exact, case-insensitive** match (confidence 1.0).
2. **Substring** match in either direction (confidence 0.8).
3. **Fuzzy** match via `difflib.SequenceMatcher` for typos (ratio > 0.6).

The top few suggestions (highest confidence first) are returned.

## Error output

When a role isn't found, `show_role_error_and_suggestions` prints the account
context, lists the available roles (marking suggested ones), and points you at
the corrective command:

```
✗ Role not found: admin
Account: 123456789012 (myorg)

Available roles:
  ✓ AdministratorAccess (suggested)
  • ReadOnly
```

## Discovering roles yourself

```bash
cloudctl list-roles myorg --account 123456789012 --format json
```

## Notes

- Role validation is meaningful for AWS SSO. On GCP `--role` is not a functional
  credential selector (static IAM).
- If the tool cannot query roles (e.g. no session), it says so rather than
  guessing.

## See also

- [Command Reference](COMMAND_REFERENCE.md) — `list-roles`
- [Error Reference](ERROR_REFERENCE.md) — "Role not found"
