import os
import yaml
from pathlib import Path
from typing import Dict, Any, List

HOME = Path.home()
CONFIG_DIR = HOME / ".config" / "awsctl"
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


def load_raw_config() -> Dict[str, Any]:
    path = get_orgs_path(ensure=False)
    if not path.exists():
        return {}
    # Let YAMLError propagate — callers that want {} on error must catch it.
    data = yaml.safe_load(path.read_text()) or {}
    # Validate and warn — do not abort so existing configs continue to work.
    if data:
        from . import schema as _schema

        errors = _schema.validate_orgs_config(data)
        if errors:
            try:
                from . import utils as _utils

                for err in errors:
                    _utils.console.print(f"[yellow]Config warning:[/] {err}")
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


def get_org(name: str) -> Dict[str, Any]:
    # Orgs live in orgs.yaml (load_raw_config), not config.yaml (load_config).
    data = load_raw_config()
    for org in data.get("orgs", []):
        if org.get("name") == name:
            return org
    raise ValueError(f"Organization '{name}' not found in configuration.")


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


MULTI_CLOUD_EXAMPLE = """\
# awsctl orgs.yaml — multi-cloud / multi-partition example
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

# Aliases — use 'awsctl switch @prod' to jump to a saved context
# aliases:
#   prod:
#     org: engineering
#     account: "123456789012"
#     role: AdministratorAccess
#     region: us-east-1
"""
