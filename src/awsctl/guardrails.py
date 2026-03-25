import sys
from pathlib import Path
from typing import Any, Dict, List
from . import _version, utils

__version__ = _version.__version__
MAX_LOG_SIZE = 10 * 1024 * 1024
AUDIT_LOG = Path.home() / ".awsctl" / "audit.log"


def validate_region(org: Dict[str, Any], region: str) -> None:
    allowed = org.get("allowed_regions", [])
    if allowed and region not in allowed:
        utils.console.print(f"Region {region} denied")
        sys.exit(1)


def sort_roles(org: Dict[str, Any], roles: List[str]) -> List[str]:
    pref = org.get("preferred_roles", [])
    out = [r for r in pref if r in roles]
    out.extend(sorted([r for r in roles if r not in pref]))
    return out
