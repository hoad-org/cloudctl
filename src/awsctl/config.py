# file: src/awsctl/config.py
# SPDX-License-Identifier: MIT
"""
awsctl.config
-------------
Configuration loading, validation, and filesystem paths.
Implements the "Hydration Model" where the Registry is the source of truth.
"""
from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Any, Dict, List, Union

import yaml

from awsctl import registry

# Paths
HOME = Path.home()
ORGS_USER = HOME / ".awsctl" / "orgs.yaml"


def get_orgs_path(ensure: bool = True) -> Path:
    """
    Return the path to orgs.yaml, creating the parent directory if needed.
    [SECURITY] Enforces 0o700 permissions on ~/.awsctl.
    """
    if ensure:
        parent = ORGS_USER.parent
        parent.mkdir(parents=True, exist_ok=True)

        if os.name == "posix":
            # Only owner can read/write/execute
            parent.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

    return ORGS_USER


def sample_orgs_yaml() -> str:
    """Generate the minimal 'enabled_orgs' config."""
    # We default to enabling the first org in the registry for the wizard
    example_org = (
        registry.KNOWN_ORGS[0]["name"] if registry.KNOWN_ORGS else "engineering"
    )
    return (
        "# awsctl user configuration\n"
        f"enabled_orgs:\n  - {example_org}\n"
        "plugins:\n  enabled: []\n"
    )


def _hydrate_orgs(user_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Core Hydration Logic.
    Merges user 'enabled_orgs' with the authoritative 'registry.KNOWN_ORGS'.
    """
    enabled_names = set(user_data.get("enabled_orgs", []))
    hydrated_list = []

    for reg_org in registry.KNOWN_ORGS:
        if reg_org["name"] in enabled_names:
            # We explicitly use the Registry definition.
            # User overrides inside 'orgs.yaml' are ignored because we don't look at them.
            hydrated_list.append(reg_org)

    return hydrated_list


def load_orgs_config() -> Dict[str, Any]:
    """
    Load orgs.yaml and hydrate against the Registry.
    Returns a structure compatible with core.py: {'orgs': [...], 'plugins': ...}
    """
    p = get_orgs_path(ensure=False)
    if not p.exists():
        # Return empty safe defaults
        return {"orgs": [], "plugins": {"enabled": []}}

    try:
        raw_data: Dict[str, Any] = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        raise yaml.YAMLError(f"Failed to parse {p}") from None

    # 1. Hydrate Orgs from Registry
    final_orgs = _hydrate_orgs(raw_data)

    # 2. Load Plugin Config (User can append optional plugins)
    # Note: Enforced plugins are inside the org definitions in the registry.
    plugins_conf = raw_data.get("plugins", {"enabled": []})

    return {"orgs": final_orgs, "plugins": plugins_conf}


def load_user_config() -> Dict[str, Any]:
    """
    Load config and validate existence.
    Used by commands that strictly require a valid config to proceed.
    """
    p = get_orgs_path(ensure=False)
    if not p.exists():
        raise SystemExit(f"Config not found: {p}. Run `awsctl setup`.")

    data = load_orgs_config()
    if not data["orgs"]:
        raise SystemExit("No enabled orgs found in orgs.yaml. Run `awsctl setup`.")
    return data


def get_org(name: Union[str, None]) -> Dict[str, Any]:
    """Retrieve a specific hydrated org block by name."""
    data = load_orgs_config()
    orgs = data.get("orgs", [])

    if not orgs:
        # [COVERAGE] This branch is technically reachable if config is empty,
        # but load_user_config usually guards it. We rely on load_user_config
        # in the CLI entrypoints, but internal calls might hit this.
        raise SystemExit("No enabled orgs found. Run `awsctl setup`.")

    if name:
        for o in orgs:
            if o.get("name") == name:
                return o  # type: ignore [no-any-return]
        raise SystemExit(f"Org not found (or not enabled): {name}")

    # Default to first enabled org
    return orgs[0]  # type: ignore [no-any-return]
