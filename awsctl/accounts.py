# file: awsctl/accounts.py  (types only; logic unchanged)
from __future__ import annotations

import json
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass

from .sso_cache import OrgRef, load_active_sso_token


@dataclass(frozen=True)
class Account:
    account_id: str
    account_name: str
    email: str


def _aws_json(args: list[str]) -> dict:
    p = subprocess.run(args, check=False, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"AWS CLI failed: {' '.join(args)}\n{p.stderr.strip()}")
    return json.loads(p.stdout or "{}")


def _paginate(base: list[str], token_key: str = "nextToken") -> Iterable[dict]:
    token: str | None = None
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
                Account(a.get("accountId", ""), a.get("accountName", ""), a.get("emailAddress", ""))
            )
    return out


def list_roles(org: OrgRef, account_id: str) -> list[str]:
    tok = load_active_sso_token(org)
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
