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
    return yaml.safe_load(path.read_text()) or {}


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
    config = load_config()
    for org in config.get("orgs", []):
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
# awsctl orgs.yaml — multi-cloud example
# ----------------------------------------
# AWS (default — provider field optional)
orgs:
  - name: engineering
    provider: aws          # optional; defaults to "aws"
    sso_start_url: https://d-xxxxxxxxxx.awsapps.com/start
    sso_region: us-east-1
    default_region: us-east-1
    allowed_regions: [us-east-1, us-west-2]

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
"""
