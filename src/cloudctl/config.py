import os
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional

HOME = Path.home()
CONFIG_DIR = HOME / ".config" / "cloudctl"
CONFIG_FILE = CONFIG_DIR / "config.yaml"
ORGS_USER = CONFIG_DIR / "orgs.yaml"


def get_orgs_path(ensure=True) -> Path:
    env_override = os.environ.get("ORGS_USER")
    if env_override:
        return Path(env_override)
    if ensure:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return ORGS_USER


def load_orgs_config() -> List[Dict[str, Any]]:
    if not ORGS_USER.exists():
        return []
    try:
        return yaml.safe_load(ORGS_USER.read_text()) or []
    except Exception:
        return []


def load_raw_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load orgs.yaml configuration.

    Args:
        config_path: Path to orgs.yaml. If None, uses default location.

    Returns:
        Configuration dict
    """
    if config_path is None:
        config_path = get_orgs_path(ensure=False)

    if not config_path.exists():
        return {}

    # Let YAMLError propagate — callers that want {} on error must catch it.
    data = yaml.safe_load(config_path.read_text()) or {}

    # Validate and warn — do not abort so existing configs continue to work.
    if data:
        from . import schema as _schema

        errors = _schema.validate_orgs_config(data)
        if errors:
            try:
                from . import utils as _utils
                import sys

                for err in errors:
                    # Print warnings to stderr to avoid polluting stdout (e.g., JSON output)
                    _utils.console.print(
                        f"[yellow]Config warning:[/] {err}", file=sys.stderr
                    )
            except Exception:
                pass
    return data


def load_config() -> Dict[str, Any]:
    if not CONFIG_FILE.exists():
        return {"orgs": []}
    try:
        data = yaml.safe_load(CONFIG_FILE.read_text())
        if not data:
            return {"orgs": []}
        return data
    except Exception:
        return {"orgs": []}


_VALID_PROVIDERS = {"aws", "azure", "gcp"}


def get_org(name: str) -> Dict[str, Any]:
    # Orgs live in orgs.yaml (load_raw_config), not config.yaml (load_config).
    data = load_raw_config()

    # Support both old list format (orgs: [...]) and new dict format (organizations: {...})
    orgs_data = data.get("organizations", {}) or data.get("orgs", [])

    # If organizations is a dict (new format), look up by key
    if isinstance(orgs_data, dict):
        if name in orgs_data:
            org = orgs_data[name]
            # Ensure the organization dict has a 'name' field for compatibility
            org_with_name = {**org, "name": name}
            provider = org_with_name.get("provider", "aws")
            if provider not in _VALID_PROVIDERS:
                raise ValueError(
                    f"Organization '{name}' has unknown provider '{provider}'. "
                    f"Valid providers: {', '.join(sorted(_VALID_PROVIDERS))}."
                )
            return org_with_name
    # If organizations is a list (legacy format), iterate through it
    elif isinstance(orgs_data, list):
        for org in orgs_data:
            if org.get("name") == name:
                provider = org.get("provider", "aws")
                if provider not in _VALID_PROVIDERS:
                    raise ValueError(
                        f"Organization '{name}' has unknown provider '{provider}'. "
                        f"Valid providers: {', '.join(sorted(_VALID_PROVIDERS))}."
                    )
                return org

    raise ValueError(f"Organization '{name}' not found in configuration.")


def get_approval_gates(org: Dict[str, Any]) -> Dict[str, int]:
    """Get approval gate configuration for an org.

    Returns a dict mapping role names to number of required approvers.
    Secure default: empty dict (no approval gates).

    Args:
        org: Organization config dict

    Returns:
        {"admin": 2, "devops": 1, ...}
    """
    return org.get("approval_gate_roles", {})


def get_mfa_required_roles(org: Dict[str, Any]) -> List[str]:
    """Get list of roles that require MFA for an org.

    Secure default: empty list (no MFA required).

    Args:
        org: Organization config dict

    Returns:
        ["admin", "security", ...]
    """
    return org.get("mfa_required_roles", [])


def get_sensitive_roles(org: Dict[str, Any]) -> List[str]:
    """Get list of sensitive roles for an org (requires break-glass justification).

    Secure default: empty list (no sensitive roles).

    Args:
        org: Organization config dict

    Returns:
        ["admin", "security", ...]
    """
    return org.get("sensitive_roles", [])


def get_approval_timeout_seconds(org: Dict[str, Any]) -> int:
    """Get approval timeout in seconds for an org.

    Secure default: 300 seconds (5 minutes).

    Args:
        org: Organization config dict

    Returns:
        Timeout in seconds (integer)
    """
    return org.get("approval_timeout_seconds", 300)


def _hydrate_orgs(enabled_names: List[Any]) -> None:
    """Validate enabled org names against registry; warn on missing."""
    from . import registry, utils

    known = {o.get("name") for o in registry.get_registry()}
    for name in enabled_names:
        if name not in known:
            utils.console.print(
                f"[yellow]Warning:[/] org '{name}' not found in registry"
            )


def sample_orgs_yaml() -> str:
    """Returns sample configuration for tests."""
    return "enabled_orgs: [default]\nplugins: {enabled: []}"


def save_orgs_yaml(
    config: Dict[str, Any],
    config_path: Optional[Path] = None,
) -> None:
    """Save configuration to orgs.yaml as plain YAML.

    Sets file permissions to 0o600 (read/write owner only).

    Args:
        config: Configuration dict to save
        config_path: Path to orgs.yaml. If None, uses default location.

    Raises:
        OSError: If file cannot be written
    """
    if config_path is None:
        config_path = get_orgs_path(ensure=True)

    # Write configuration to file
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    # Set secure file permissions (owner read/write only)
    config_path.chmod(0o600)


MULTI_CLOUD_EXAMPLE = """\
# cloudctl orgs.yaml — multi-cloud / multi-partition example
# ---------------------------------------------------------
# AWS Commercial (partition: aws — default, field is optional)
orgs:
  - name: engineering
    provider: aws
    partition: aws                        # aws | aws-us-gov | aws-cn
    sso_start_url: https://d-xxxxxxxxxx.awsapps.com/start
    sso_region: us-east-1
    default_region: us-east-1
    allowed_regions: [us-east-1, us-west-2]

  # AWS GovCloud — separate partition, separate SSO endpoint
  - name: engineering-gov
    provider: aws
    partition: aws-us-gov
    sso_start_url: https://d-yyyyyyyyyy.awsapps-us-gov.com/start
    sso_region: us-gov-west-1
    default_region: us-gov-west-1
    allowed_regions: [us-gov-east-1, us-gov-west-1]

  # Azure — uses 'az' CLI for auth
  - name: azure-prod
    provider: azure
    tenant_id: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    default_subscription: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    roles:                 # optional static role list shown in picker
      - Contributor
      - Reader

  # GCP — uses 'gcloud' CLI for auth
  - name: gcp-prod
    provider: gcp
    default_project: my-project-id
    roles:                 # optional; defaults to viewer/editor/owner
      - roles/viewer
      - roles/editor

enabled_orgs: [engineering, azure-prod, gcp-prod]
plugins:
  enabled: []

# Aliases — use 'cloudctl switch @prod' to jump to a saved context
# aliases:
#   prod:
#     org: engineering
#     account: "123456789012"
#     role: AdministratorAccess
#     region: us-east-1
"""
