# file: awsctl/cli_accounts.py
"""
CLI glue: `awsctl accounts` and `awsctl roles`
"""
from __future__ import annotations

import json

from .accounts import list_accounts, list_roles
from .sso_cache import OrgRef


def _org_from_cfg(cfg: dict, name: str | None) -> OrgRef:
    if not cfg.get("orgs"):
        raise SystemExit("No orgs configured. Run `awsctl setup`.")
    if name:
        for o in cfg["orgs"]:
            if o.get("name") == name:
                return OrgRef(o["name"], o["sso_start_url"], o["sso_region"])
        raise SystemExit(f"Org not found: {name}")
    o = cfg["orgs"][0]
    return OrgRef(o["name"], o["sso_start_url"], o["sso_region"])


def cmd_accounts(cfg: dict, org: str | None, as_json: bool) -> int:
    ref = _org_from_cfg(cfg, org)
    accts = list_accounts(ref)
    if as_json:
        print(json.dumps({"accountList": [a.__dict__ for a in accts]}, indent=2))
    else:
        if not accts:
            print("No accounts found.")
        for a in accts:
            print(f"{a.account_id}\t{a.account_name}\t{a.email}")
    return 0


def cmd_roles(cfg: dict, org: str | None, account_id: str, as_json: bool) -> int:
    ref = _org_from_cfg(cfg, org)
    roles = list_roles(ref, account_id)
    if as_json:
        print(json.dumps({"roles": roles}, indent=2))
    else:
        if not roles:
            print("No roles found.")
        for r in roles:
            print(r)
    return 0
