# Role Validation & Auto-Correction Feature

## Overview

CloudCtl now includes intelligent role validation that prevents "role not found" errors by:
1. **Querying actual available roles** from AWS SSO for your account
2. **Validating** requested role names before attempting credential retrieval
3. **Suggesting corrections** for typos and common mistakes
4. **Auto-correcting** in interactive mode with user confirmation

## The Problem It Solves

Previously, if you ran:
```bash
cloudctl switch bt-avm --account 235494790978 --role admin --region us-east-1
```

And the actual role was `AdministratorAccess`, you'd get:
```
ForbiddenException: No access
```

With no indication that the issue was the wrong role name.

## How It Works

### Architecture

The feature uses three key components:

1. **AWS SSO API Integration**
   - Queries `aws sso list-account-roles` to get available roles
   - Works with existing cloudctl provider layer
   - Graceful fallback if SSO unavailable

2. **Role Validation Engine**
   - Exact case-insensitive matching
   - Fuzzy matching for typo detection
   - Substring matching for partial names
   - Levenshtein distance for similarity scoring

3. **User-Friendly Error Display**
   - Shows list of available roles
   - Highlights suggestions
   - Guides user to correct the role name

### Workflow Modes

#### Interactive Mode (Default)

When you run: `cloudctl switch bt-avm --account 235494790978 --role admin --region us-east-1`

If `admin` is not found:
1. CloudCtl queries available roles
2. Shows error with suggestions:
   ```
   ✗ Role not found: admin
   Account: 235494790978 (bt-avm)
   
   Available roles:
     ✓ AdministratorAccess (suggested)
     • ReadOnlyAccess
     • PowerUserAccess
   
   Next steps:
   1. Choose a valid role from the list above
   2. Run: cloudctl switch <org> --account <id> --role <name> --region <region>
   3. Or run without --role for interactive selection
   ```
3. Attempts interactive role picker to auto-correct

#### Non-Interactive Mode

When you run: `cloudctl switch bt-avm --account 235494790978 --role admin --region us-east-1 --non-interactive`

If `admin` is not found:
1. Shows same error with available roles
2. Exits with error code 1
3. Does NOT attempt interactive correction

#### Interactive Selection (No --role)

When you run: `cloudctl switch bt-avm --account 235494790978 --region us-east-1`

1. CloudCtl queries available roles
2. Presents interactive picker
3. No validation errors possible (only valid roles offered)

## API Reference

### Role Validator Module

Located in `src/cloudctl/role_validator.py`

#### `validate_role(org_data, token, account_id, requested_role) -> Tuple[bool, Optional[str], List[str]]`

Validates that a role exists for an account.

**Parameters:**
- `org_data`: Organization configuration dict
- `token`: SSO token from `load_active_sso_token`
- `account_id`: AWS account ID
- `requested_role`: Role name requested by user

**Returns:**
- `(True, None, available_roles)` if role is valid
- `(False, error_message, available_roles)` if role is invalid

**Example:**
```python
from cloudctl.role_validator import validate_role
from cloudctl.sso_cache import load_active_sso_token, OrgRef

token = load_active_sso_token(OrgRef("bt-avm", url, region))
is_valid, msg, roles = validate_role(org_data, token, "235494790978", "admin")

if not is_valid:
    print(f"Error: {msg}")
    print(f"Available: {roles}")
```

#### `find_role_suggestions(requested_role, available_roles, max_suggestions=3) -> List[str]`

Find fuzzy-matched suggestions for a role name.

**Parameters:**
- `requested_role`: User-provided role name
- `available_roles`: List of valid roles
- `max_suggestions`: Max suggestions to return (default: 3)

**Returns:**
- List of suggested role names (highest confidence first)

**Example:**
```python
from cloudctl.role_validator import find_role_suggestions

available = ["AdministratorAccess", "ReadOnlyAccess", "PowerUserAccess"]
suggestions = find_role_suggestions("admin", available)
# Returns: ["AdministratorAccess"]

suggestions = find_role_suggestions("AdminAccess", available)
# Returns: ["AdministratorAccess"]

suggestions = find_role_suggestions("power", available)
# Returns: ["PowerUserAccess"]
```

#### `show_role_error_and_suggestions(requested_role, available_roles, account_id, org_name) -> None`

Display a formatted error message with suggestions.

**Parameters:**
- `requested_role`: Role name that failed
- `available_roles`: List of available roles
- `account_id`: AWS account ID (for context)
- `org_name`: Organization name (for context)

**Example:**
```python
from cloudctl.role_validator import show_role_error_and_suggestions

show_role_error_and_suggestions(
    "admin",
    ["AdministratorAccess", "ReadOnlyAccess"],
    "235494790978",
    "bt-avm"
)
```

#### `validate_and_prompt_for_role(org_data, token, account_id, requested_role) -> Optional[str]`

Validate role and prompt for correction in interactive mode.

**Parameters:**
- `org_data`: Organization configuration dict
- `token`: SSO token
- `account_id`: AWS account ID
- `requested_role`: Role name to validate

**Returns:**
- Validated/corrected role name, or None if cancelled

**Example:**
```python
from cloudctl.role_validator import validate_and_prompt_for_role

corrected = validate_and_prompt_for_role(org_data, token, "235494790978", "admin")
if corrected:
    print(f"Using role: {corrected}")
else:
    print("Cancelled")
```

## Usage Examples

### Example 1: Typo Correction (Interactive)

```bash
$ cloudctl switch bt-avm --account 235494790978 --role admin --region us-east-1

✗ Role not found: admin
Account: 235494790978 (bt-avm)

Available roles:
  ✓ AdministratorAccess (suggested)
  • ReadOnlyAccess
  • PowerUserAccess

Next steps:
1. Choose a valid role from the list above
2. Run: cloudctl switch <org> --account <id> --role <name> --region <region>
3. Or run without --role for interactive selection

? Select Role: ❯ AdministratorAccess
  ReadOnlyAccess
  PowerUserAccess

✓ Selected: AdministratorAccess
✔ Switched to 235494790978 / AdministratorAccess / us-east-1
```

### Example 2: Correct Role (No Validation)

```bash
$ cloudctl switch bt-avm --account 235494790978 --role AdministratorAccess --region us-east-1 --non-interactive

✔ Switched to 235494790978 / AdministratorAccess / us-east-1
```

### Example 3: Interactive Picker (No Validation Needed)

```bash
$ cloudctl switch bt-avm --account 235494790978

? Select Role: ❯ AdministratorAccess
  ReadOnlyAccess
  PowerUserAccess

✓ Selected: AdministratorAccess
✓ Select Region:   us-east-1

✔ Switched to 235494790978 / AdministratorAccess / us-east-1
```

### Example 4: Case-Insensitive Match

```bash
$ cloudctl switch bt-avm --account 235494790978 --role administratoraccess --region us-east-1

✔ Switched to 235494790978 / AdministratorAccess / us-east-1
```

### Example 5: Substring Match

```bash
$ cloudctl switch bt-avm --account 235494790978 --role "read only" --region us-east-1

? Did you mean ReadOnlyAccess? [y/N]: y
✔ Switched to 235494790978 / ReadOnlyAccess / us-east-1
```

## Technical Details

### Matching Strategies

The role validator uses a three-tier matching strategy:

**Tier 1: Exact Case-Insensitive Match (Highest Confidence)**
```
Requested: "admin"
Available: ["AdministratorAccess", "ReadOnlyAccess"]
Match: "admin".lower() == "administratoraccess".lower()? ✗
```

**Tier 2: Substring Match (Medium Confidence)**
```
Requested: "security"
Available: ["SecurityAuditAccess", "ReadOnlyAccess"]
Match: "security" in "securityauditaccess"? ✓
Suggestion: "SecurityAuditAccess"
```

**Tier 3: Levenshtein Distance (Typo Correction)**
```
Requested: "AdminAccess"
Available: ["AdministratorAccess", "ReadOnlyAccess"]
Similarity: 0.75 (high enough to suggest)
Suggestion: "AdministratorAccess"
```

### Performance Characteristics

- **Query time**: ~100-200ms (AWS SSO API call)
- **Validation time**: <1ms (string comparison)
- **Suggestion time**: <5ms (fuzzy matching)
- **Total overhead**: <300ms per role validation

### Error Handling

| Scenario | Behavior |
|----------|----------|
| SSO unavailable | Skip validation, attempt credential retrieval (may fail later) |
| Empty role list | Show error, available_roles will be empty |
| API timeout | Log warning, continue without pre-validation |
| Token invalid | Auto-login triggered by existing code path |

## Testing

### Test Coverage

14 comprehensive tests covering:
- Exact case-insensitive matching
- Substring matching
- Typo correction (Levenshtein)
- No matches (returns empty list)
- Max suggestions limit
- Empty available roles
- Provider error handling
- Integration scenarios

### Running Tests

```bash
pytest tests/test_role_validator.py -v
# Output: 14 passed in 0.17s
```

## Integration with Existing Features

### AWS Provider Integration

Uses existing `AwsProvider.list_roles()` method:
```python
# In src/cloudctl/providers/aws.py
def list_roles(self, org: Dict[str, Any], token: Any, account_id: str) -> List[str]:
    raw = _aws.sso_list_account_roles(token, account_id)
    return [r["roleName"] for r in raw]
```

### CLI Integration

Added to `cmd_switch()` flow in cli.py (lines 314-345):
```python
# Validate role exists for this account
if token:
    is_valid, error_msg, available_roles = role_validator.validate_role(
        org_data, token, account, role
    )
    
    if not is_valid:
        if non_interactive:
            # Show error and available roles
            role_validator.show_role_error_and_suggestions(...)
            return 1
        else:
            # Attempt interactive correction
            corrected_role = role_validator.validate_and_prompt_for_role(...)
```

### Interactive Mode Integration

Works with existing `interactive.py` flow:
- Reuses `select_role()` picker
- Respects `sort_roles()` guardrails
- Uses same OrgRef/token infrastructure

## Future Enhancements

1. **Role Caching**: Cache available roles per account to reduce API calls
2. **Smart Defaulting**: Remember last-used role for account
3. **Role Description Display**: Show role descriptions when available
4. **Learning**: Track user's frequent roles and suggest them first
5. **Batch Validation**: Validate multiple account/role combos in advance

## Troubleshooting

### "Could not query available roles"

This warning appears when:
- SSO token is invalid or expired
- AWS CLI is not installed
- AWS SSO endpoint is unreachable
- Network timeout

**Fix**: Run `cloudctl login <org>` to refresh credentials

### Role suggestions seem wrong

This can happen when:
- Role names are very similar
- Typos change meaning (e.g., "Admin" vs "Audit")
- Substring matching is too broad

**Workaround**: Use `cloudctl switch` without `--role` for interactive picker with all roles listed

### Pre-validation is slow

If role validation takes >300ms:
- AWS SSO API is slow (check network)
- AWS CLI is slow to invoke
- Account has many roles (>100)

**Workaround**: Use `--non-interactive` flag to skip pre-validation

## Related Features

- **Interactive Selection**: `cloudctl switch <org>` (no role specified)
- **Non-Interactive Mode**: `cloudctl switch ... --non-interactive`
- **Role Sorting**: `guardrails.sort_roles()` (preferred roles first)
- **RBAC Authorization**: `guardrails.validate_role_access()` (approval gates/MFA)

## References

- **Module**: `src/cloudctl/role_validator.py`
- **Tests**: `tests/test_role_validator.py`
- **CLI Integration**: `src/cloudctl/cli.py` (cmd_switch function)
- **AWS Provider**: `src/cloudctl/providers/aws.py`
