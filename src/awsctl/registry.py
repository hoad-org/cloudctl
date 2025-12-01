# file: src/awsctl/registry.py
# SPDX-License-Identifier: MIT
"""
The Corporate Registry.
Single source of truth for Organization definitions, Guardrails, and Policies.
"""
from typing import Any, Dict

# [ACTION REQUIRED] Populate with your actual Organization details.
KNOWN_ORGS = [
    {
        "name": "myorg",
        "label": "myorg (Default)",
        "description": "Primary corporate environment.",
        "sso_start_url": "https://d-9c67661145.awsapps.com/start",
        "sso_region": "eu-west-2",
        "default_region": "eu-west-2",
        # 🛡️ GUARDRAILS: Enforced here. Users cannot change this.
        "allowed_regions": ["eu-west-1", "eu-west-2"],
        "preferred_roles": ["AdministratorAccess", "ViewOnlyAccess"],
        # Mandatory Plugins (Ops Enforced)
        "plugins": [],
        # UX: Rename ugly SSO roles to friendly names
        "role_aliases": {
            "AWSReservedSSO_ViewOnly_.*": "ViewOnly",
            "AWSReservedSSO_AdministratorAccess_.*": "Admin",
        },
    },
    {
        "name": "engineering",
        "label": "Engineering",
        "description": "Main workload accounts. Requires VPN.",
        "sso_start_url": "https://d-1234567890.awsapps.com/start",
        "sso_region": "eu-west-1",
        "default_region": "eu-west-2",
        "allowed_regions": ["eu-west-1", "eu-west-2", "us-east-1"],
        "preferred_roles": ["ViewOnlyAccess", "DeveloperAccess"],
        "plugins": [],
        "role_aliases": {
            "AWSReservedSSO_ViewOnly_.*": "ViewOnly",
            "AWSReservedSSO_AdministratorAccess_.*": "Admin",
        },
    },
    {
        "name": "production",
        "label": "Production",
        "description": "Restricted environment. Read-only by default.",
        "sso_start_url": "https://d-0987654321.awsapps.com/start",
        "sso_region": "eu-west-1",
        "default_region": "eu-west-1",
        "allowed_regions": ["eu-west-1"],
        "preferred_roles": ["ViewOnlyAccess"],
        # Mandatory Plugins: Force VPN check
        "plugins": ["awsctl.plugins.okta"],
        "role_aliases": {"AWSReservedSSO_ViewOnly_.*": "ViewOnly"},
    },
    {
        "name": "sandbox",
        "label": "Sandbox",
        "description": "Playground accounts. No PII allowed.",
        "sso_start_url": "https://d-1122334455.awsapps.com/start",
        "sso_region": "us-east-1",
        "default_region": "us-east-1",
        "allowed_regions": [],  # Empty = All regions allowed
        "plugins": [],
        "role_aliases": {},
    },
]


def get_choices() -> list[Dict[str, Any]]:
    """Format registry for InquirerPy checkboxes with descriptions."""
    choices = []
    for o in KNOWN_ORGS:
        # Format: "Engineering — Main workload accounts..."
        display = o["label"]
        if o.get("description"):
            display = f"{o['label']} — [dim]{o['description']}[/]"

        choices.append({"name": display, "value": o})

    return choices
