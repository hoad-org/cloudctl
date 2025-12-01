# file: src/awsctl/accounts.py
from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Dict, List, Union

from awsctl.utils import run

from .sso_cache import OrgRef, load_active_sso_token


@dataclass(frozen=True)
class Account:
    account_id: str
    account_name: str
    email: str


def _aws_json(args: List[str]) -> Dict[str, Any]:
    # Enforce 5s timeout to prevent zombie hangs
    p = run(args, check=False, timeout=5.0)

    if p.returncode != 0:
        raise RuntimeError(f"AWS CLI failed: {' '.join(args)}\n{p.stderr.strip()}")

    # Explicitly type the result of json.loads
    try:
        result: Dict[str, Any] = json.loads(p.stdout or "{}")
        return result
    except json.JSONDecodeError:
        return {}


def _paginate(
    base: List[str],
    token_key: str = "nextToken",  # nosec B107
) -> Iterable[Dict[str, Any]]:
    token: Union[str, None] = None
    while True:
        args = list(base)
        if token:
            args += ["--next-token", token]
        data = _aws_json(args)
        yield data
        token = data.get(token_key)
        if not token:
            break


def list_accounts(org: OrgRef) -> list[Account]:
    tok = load_active_sso_token(org)

    # [FIX] Validate token before calling CLI
    if not tok or not tok.access_token:
        raise RuntimeError("No valid SSO access token found. Please login again.")

    base = [
        "aws",
        "sso",
        "list-accounts",
        "--region",
        tok.region,
        "--access-token",
        tok.access_token,
    ]
    out: list[Account] = []
    for page in _paginate(base):
        for a in page.get("accountList", []):
            out.append(
                Account(
                    a.get("accountId", ""),
                    a.get("accountName", ""),
                    a.get("emailAddress", ""),
                )
            )
    return out


def list_roles(org: OrgRef, account_id: str) -> list[str]:
    tok = load_active_sso_token(org)

    # [FIX] Validate token before calling CLI
    if not tok or not tok.access_token:
        raise RuntimeError("No valid SSO access token found. Please login again.")

    base = [
        "aws",
        "sso",
        "list-account-roles",
        "--region",
        tok.region,
        "--access-token",
        tok.access_token,
        "--account-id",
        account_id,
    ]
    roles: list[str] = []
    for page in _paginate(base):
        for r in page.get("roleList", []):
            n = r.get("roleName")
            if n:
                roles.append(n)
    return roles
