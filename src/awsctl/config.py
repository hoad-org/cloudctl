import yaml
from pathlib import Path
from typing import Dict, Any, List

HOME = Path.home()
CONFIG_DIR = HOME / ".config" / "awsctl"
CONFIG_FILE = CONFIG_DIR / "config.yaml"
ORGS_USER = CONFIG_DIR / "orgs.yaml"


def get_orgs_path(ensure=True) -> Path:
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
    if not CONFIG_FILE.exists():
        return {}
    try:
        return yaml.safe_load(CONFIG_FILE.read_text()) or {}
    except Exception:
        return {}


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


def _hydrate_orgs(orgs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return orgs


def sample_orgs_yaml() -> str:
    """Returns sample configuration for tests."""
    return "enabled_orgs: [default]\nplugins: {enabled: []}"
