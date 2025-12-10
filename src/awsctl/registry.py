# file: src/awsctl/registry.py
# SPDX-License-Identifier: MIT
"""
The Corporate Registry.
Single source of truth for Organization definitions, Guardrails, and Policies.
"""

import os
from typing import Any, Dict, List, Optional, cast

from awsctl import config

# ---------------------------------------------------------------------------
# Tier 3: Signed Registry Trust Anchor
# ---------------------------------------------------------------------------
# [SECURITY] Hardcoded Public Key to prevent Trust Downgrade attacks.
# This ensures that even if a user modifies orgs.yaml to point to a malicious
# URL, the client will reject the payload unless it is signed by this specific key.
# Replace this with your organization's actual Minisign public key.
_TRUSTED_ROOT_KEY = "RWQf6LRCGA9i53mlYec++jCqiotM3TRmxKv2kj/..."


# ---------------------------------------------------------------------------
# Tier 1: Embedded Defaults (Immutable Policy Source)
# ---------------------------------------------------------------------------

_EMBEDDED_ORGS: List[Dict[str, Any]] = [
    {
        "name": "btavm",
        "label": "btavm",
        "description": "AVM Org for MVP.",
        # [SECURITY] Read URL from environment to prevent source code leakage.
        # Fallback to a safe placeholder for local dev/testing.
        "sso_start_url": os.environ.get(
            "AWSCTL_BTAVM_URL", "https://dev-placeholder.awsapps.com/start"
        ),
        "sso_region": "us-east-1",
        "default_region": "us-east-1",
        # Guardrails
        "allowed_regions": ["us-east-1", "us-east-2"],
        "preferred_roles": ["SecurityAuditor"],
        # [FIX] Added AdministratorAccess explicitly here
        "sensitive_roles": ["Admin", "DBAdmin", "AdministratorAccess"],
        "min_client_version": "2.8.0",
        # [FIX] Activated Okta plugin for pre-flight security checks
        "plugins": ["awsctl.plugins.okta"],
        "role_aliases": {
            "AWSReservedSSO_DatabaseAdministrator_.*": "DBAdmin",
            "AWSReservedSSO_AdministratorAccess_.*": "Admin",
            "AWSReservedSSO_SecurityAuditor_.*": "SecurityAuditor",
        },
    },
    {
        "name": "btdev",
        "label": "btdev",
        "description": "BT Development org.",
        # [SECURITY] Read URL from environment
        "sso_start_url": os.environ.get(
            "AWSCTL_BTDEV_URL", "https://dev-placeholder.awsapps.com/start"
        ),
        "sso_region": "us-east-1",
        "default_region": "us-east-1",
        # Guardrails
        "allowed_regions": ["us-east-1", "us-east-2"],
        "preferred_roles": ["org_it-auditor"],
        "sensitive_roles": [
            "AdministratorAccess",
            "AccountAdmin",
        ],
        # [FIX] Activated Okta plugin for pre-flight security checks
        "plugins": ["awsctl.plugins.okta"],
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

        if url:
            from awsctl.registry_loader import fetch_remote_registry

            # [SECURITY] Use the pinned Trust Anchor, ignoring any user-provided key.
            # This forces all remote configs to be signed by the corporate private key.
            return fetch_remote_registry(url, public_key=_TRUSTED_ROOT_KEY)

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
