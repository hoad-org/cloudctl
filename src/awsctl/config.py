# file: src/awsctl/config.py
# SPDX-License-Identifier: MIT
"""
awsctl.config
"""

from __future__ import annotations

import copy
import os
import stat
from pathlib import Path
from typing import Any, Dict, List, Set, Union, cast

import yaml

from awsctl.utils import console

# Paths
HOME = Path.home()
ORGS_USER = HOME / ".awsctl" / "orgs.yaml"


def get_orgs_path(ensure: bool = True) -> Path:
    if ensure:
        parent = ORGS_USER.parent
        parent.mkdir(parents=True, exist_ok=True)

        if os.name == "posix":
            parent.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

    return ORGS_USER


def sample_orgs_yaml() -> str:
    # [VANILLA] Template directs users to internal docs
    return (
        "# awsctl user configuration\n"
        "# ------------------------------------------------------------------\n"
        "# ⚠️  MANUAL CONFIGURATION REQUIRED (Pilot Phase)\n"
        "# Please paste the configuration block from the internal Confluence page:\n"
        "# https://beyondtrust.atlassian.net/wiki/x/CgD9qw\n"
        "# ------------------------------------------------------------------\n\n"
        "# enabled_orgs:\n"
        "#   - my-org\n\n"
        "# orgs:\n"
        "#   - name: my-org\n"
        "#     ...\n"
    )


def _hydrate_orgs(enabled_names: Set[str]) -> List[Dict[str, Any]]:
    hydrated_list: List[Dict[str, Any]] = []

    # Local import to break cycle
    from awsctl import registry

    # Force reload registry to pick up manual edits in orgs.yaml
    registry_orgs = registry.get_registry()

    unique_registry = {}
    for o in registry_orgs:
        if "name" not in o:
            continue
        if o["name"] not in unique_registry:
            unique_registry[o["name"]] = o

    for name, reg_org in unique_registry.items():
        if name in enabled_names:
            item = copy.deepcopy(reg_org)
            hydrated_list.append(item)

    for name in enabled_names:
        if name not in unique_registry:
            console.print(f"[warning]Warning: Org '{name}' not found in registry.[/]")

    return hydrated_list


def _load_raw_file() -> Dict[str, Any]:
    """Low-level YAML read without hydration logic."""
    p = get_orgs_path(ensure=False)
    if not p.exists():
        return {}
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        raise yaml.YAMLError(f"Failed to parse {p}") from None


def load_raw_config() -> Dict[str, Any]:
    """Public API for registry.py to read config."""
    return _load_raw_file()


def load_orgs_config() -> Dict[str, Any]:
    raw_data = _load_raw_file()

    enabled_set = set(raw_data.get("enabled_orgs", []))
    final_orgs = _hydrate_orgs(enabled_set)

    raw_plugins = raw_data.get("plugins")
    plugins_conf: Dict[str, Any] = {"enabled": []}
    if isinstance(raw_plugins, dict):
        plugins_conf = raw_plugins

    aliases = raw_data.get("aliases", {})
    if not isinstance(aliases, dict):
        aliases = {}

    reg_conf = raw_data.get("registry", {})
    if not isinstance(reg_conf, dict):
        reg_conf = {}

    return {
        "orgs": final_orgs,
        "plugins": plugins_conf,
        "aliases": aliases,
        "registry": reg_conf,
    }


def load_user_config() -> Dict[str, Any]:
    p = get_orgs_path(ensure=False)
    if not p.exists():
        raise SystemExit(f"Config not found: {p}. Run `awsctl setup`.")

    data = load_orgs_config()
    if not data["orgs"]:
        raise SystemExit("No enabled orgs found in orgs.yaml. Run `awsctl setup`.")
    return data


def get_org(name: Union[str, None]) -> Dict[str, Any]:
    data = load_orgs_config()
    orgs = cast(List[Dict[str, Any]], data.get("orgs", []))

    if not orgs:
        raise ValueError("No enabled orgs found. Run `awsctl setup`.")

    if name:
        for o in orgs:
            if o.get("name") == name:
                return o
        raise ValueError(f"Org not found (or not enabled): {name}")

    return orgs[0]
