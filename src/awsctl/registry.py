# file: src/awsctl/registry.py
# SPDX-License-Identifier: MIT
"""
The Corporate Registry.
Single source of truth for Organization definitions, Guardrails, and Policies.
"""

from typing import Any, Dict, List, Optional, cast

from awsctl import config

# ---------------------------------------------------------------------------
# Tier 1: Embedded Defaults (Immutable Policy Source)
# ---------------------------------------------------------------------------

_EMBEDDED_ORGS: List[Dict[str, Any]] = [
    {
        "name": "bt-avm",
        "label": "bt-avm",
        "description": "AVM Org for MVP.",
        "sso_start_url": "https://d-9067dbbf5a.awsapps.com/start",
        "sso_region": "us-east-1",
        "default_region": "us-east-1",
        # Guardrails
        "allowed_regions": ["us-east-1", "us-east-2"],
        "preferred_roles": ["SecurityAuditor"],
        # [FIX] Added AdministratorAccess explicitly here
        "sensitive_roles": ["Admin", "DBAdmin", "AdministratorAccess"],
        "min_client_version": "2.7.0",
        # [FIX] Disabled Okta plugin to prevent SSL issues on MacOS
        "plugins": [],
        "role_aliases": {
            "AWSReservedSSO_DatabaseAdministrator_.*": "DBAdmin",
            "AWSReservedSSO_AdministratorAccess_.*": "Admin",
            "AWSReservedSSO_SecurityAuditor_.*": "SecurityAuditor",
        },
    },
    {
        "name": "bt-dev",
        "label": "BT-DEV",
        "description": "BT Development org.",
        "sso_start_url": "https://d-9067b5b44d.awsapps.com/start",
        "sso_region": "us-east-1",
        "default_region": "us-east-1",
        # Guardrails
        "allowed_regions": ["us-east-1", "us-east-2"],
        "preferred_roles": ["org_it-auditor"],
        "sensitive_roles": [
            "AdministratorAccess",
            "AccountAdmin",
        ],
        "plugins": [],
        "role_aliases": {
            "AWSReservedSSO_AccountAdmin_.*": "AccountAdmin",
            "AWSReservedSSO_AdministratorAccess_.*": "AdministratorAccess",
            "AWSReservedSSO_org_it-auditor_.*": "OrgITAuditor",
        },
    },
]

# ---------------------------------------------------------------------------
# Registry Loader
# ---------------------------------------------------------------------------


def get_registry() -> List[Dict[str, Any]]:
    try:
        raw_cfg = config.load_raw_config()
        reg_conf = raw_cfg.get("registry", {})
        url: Optional[str] = cast(Optional[str], reg_conf.get("url"))
        pub_key: Optional[str] = cast(Optional[str], reg_conf.get("public_key"))

        if url:
            from awsctl.registry_loader import fetch_remote_registry

            return cast(List[Dict[str, Any]], fetch_remote_registry(url, pub_key))

    except Exception:  # nosec
        pass

    return _EMBEDDED_ORGS


KNOWN_ORGS = get_registry()


def get_choices() -> List[Dict[str, Any]]:
    choices: List[Dict[str, Any]] = []
    for o in KNOWN_ORGS:
        display = o.get("label", o["name"])
        desc = o.get("description")
        if desc:
            display = f"{display} — [dim]{desc}[/]"
        choices.append({"name": display, "value": o})
    return choices
