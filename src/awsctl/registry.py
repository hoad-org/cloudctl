# file: src/awsctl/registry.py
# SPDX-License-Identifier: MIT
"""
The Corporate Registry.
Single source of truth for Organization definitions, Guardrails, and Policies.
"""

from typing import Any, Dict, List, Optional, cast

from awsctl import config

# ---------------------------------------------------------------------------
# Tier 3: Signed Registry Trust Anchor
# ---------------------------------------------------------------------------
# [SECURITY] Hardcoded Public Key (Placeholder for future Tier 3)
_TRUSTED_ROOT_KEY = "RWQf6LRCGA9i53mlYec++jCqiotM3TRmxKv2kj/..."


# ---------------------------------------------------------------------------
# Tier 1: Embedded Defaults
# ---------------------------------------------------------------------------

# [VANILLA] No internal orgs defined.
_EMBEDDED_ORGS: List[Dict[str, Any]] = [
    {
        "name": "manual-setup-required",
        "label": "⚠️ Setup Required",
        "description": "Please configure your organizations in ~/.awsctl/orgs.yaml",
        "sso_start_url": "https://example.com/start",
        "sso_region": "us-east-1",
        "default_region": "us-east-1",
        "allowed_regions": ["*"],
        "preferred_roles": [],
        "sensitive_roles": [],
        "min_client_version": "0.0.0",
        "plugins": [],
        "role_aliases": {},
    }
]

# ---------------------------------------------------------------------------
# Registry Loader
# ---------------------------------------------------------------------------


def get_registry() -> List[Dict[str, Any]]:
    try:
        raw_cfg = config.load_raw_config()

        # [FEATURE] Manual Mode: Allow 'orgs' block in orgs.yaml to override defaults
        user_orgs = raw_cfg.get("orgs")
        if user_orgs and isinstance(user_orgs, list):
            # [FIX] Cast to explicit type to satisfy Mypy strict mode
            return cast(List[Dict[str, Any]], user_orgs)

        # Remote Registry Support
        reg_conf = raw_cfg.get("registry", {})
        url: Optional[str] = cast(Optional[str], reg_conf.get("url"))

        if url:
            from awsctl.registry_loader import fetch_remote_registry

            return fetch_remote_registry(url, public_key=_TRUSTED_ROOT_KEY)

    except Exception:  # nosec
        pass

    return _EMBEDDED_ORGS


KNOWN_ORGS = get_registry()


def get_choices() -> List[Dict[str, Any]]:
    choices: List[Dict[str, Any]] = []
    # Always refresh to pick up manual edits
    for o in get_registry():
        display = o.get("label", o["name"])
        desc = o.get("description")
        if desc:
            display = f"{display} — [dim]{desc}[/]"
        choices.append({"name": display, "value": o})
    return choices
