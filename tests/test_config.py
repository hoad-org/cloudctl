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
from typing import Any, Dict, List, Union, cast

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
    # Use a safe default if registry access triggers recursion
    try:
        from awsctl import registry

        if registry.KNOWN_ORGS:
            example_org = registry.KNOWN_ORGS[0]["name"]
        else:
            example_org = "example-org"
    except Exception:
        example_org = "example-org"

    return (
        "# awsctl user configuration\n"
        f"enabled_orgs:\n  - {example_org}\n"
        "plugins:\n  enabled: []\n\n"
        "# Remote Registry (Tier 2/3)\n"
        "# registry:\n"
        "#   url: https://internal.corp/registry.json\n\n"
        "# Aliases allow quick switching: awsctl switch @prod\n"
        "# aliases:\n"
        "#   prod:\n"
        "#     org: production\n"
        "#     account: '123456789012'\n"
        "#     role: ViewOnlyAccess\n"
        "#     region: eu-west-1\n"
    )


def _hydrate_orgs(user_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    enabled_names = set(user_data.get("enabled_orgs", []))
    hydrated_list: List[Dict[str, Any]] = []

    # [FIX] Local import to break cycle
    from awsctl import registry

    unique_registry = {}
    for o in registry.KNOWN_ORGS:
        if "name" not in o:
            continue
        if o["name"] not in unique_registry:
            unique_registry[o["name"]] = o

    for name, reg_org in unique_registry.items():
        if name in enabled_names:
            item = cast(Dict[str, Any], copy.deepcopy(reg_org))
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
    """
    Public API for registry.py to read config WITHOUT triggering recursion.
    Returns the raw content of orgs.yaml.
    """
    return _load_raw_file()


def load_orgs_config() -> Dict[str, Any]:
    """
    Full config load with Registry Hydration.
    """
    # [FIX] MyPy: Removed redundant cast
    raw_data = _load_raw_file()

    final_orgs = _hydrate_orgs(raw_data)

    # Plugins
    raw_plugins = raw_data.get("plugins")
    plugins_conf: Dict[str, Any] = {"enabled": []}
    if isinstance(raw_plugins, dict):
        plugins_conf = raw_plugins

    # Aliases
    aliases = raw_data.get("aliases", {})
    if not isinstance(aliases, dict):
        aliases = {}

    # Registry config
    reg_conf = raw_data.get("registry", {})
    if not isinstance(reg_conf, dict):
        reg_conf = {}

    return cast(
        Dict[str, Any],
        {
            "orgs": final_orgs,
            "plugins": plugins_conf,
            "aliases": aliases,
            "registry": reg_conf,
        },
    )


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
