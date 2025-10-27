# file: awsctl/cli_use.py
"""
CLI glue: `awsctl use` prints export lines for eval
"""
from __future__ import annotations

from .sso_cache import OrgRef
from .use_exports import emit_exports


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


def cmd_use(cfg: dict, org: str | None, account: str, role: str, region: str) -> int:
    ref = _org_from_cfg(cfg, org)
    print(emit_exports(ref, account, role, region), end="")
    return 0
