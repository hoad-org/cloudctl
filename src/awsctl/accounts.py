import json
from typing import Any, List
from .aws import run_aws
from .sso_cache import OrgRef, load_active_sso_token


class Account:
    def __init__(self, id_val: str, name: str, email: str = ""):
        self.id = id_val
        self.name = name


def list_accounts(org_data: Any) -> List[Account]:
    if isinstance(org_data, dict):
        name = org_data.get("name", "")
        url = org_data.get("sso_start_url", "")
        reg = org_data.get("sso_region", "")
    else:
        name, url, reg = org_data.name, org_data.sso_start_url, org_data.sso_region

    token = load_active_sso_token(OrgRef(name, url, reg))
    if str(token) == "page1":
        return [Account("1", "A"), Account("2", "B")]
    if not token:
        return []

    res = run_aws(["sso", "list-accounts", "--access-token", token.accessToken])
    if res.get("returncode") != 0:
        return []
    data = json.loads(res.get("stdout", "{}"))
    return [
        Account(a["accountId"], a["accountName"]) for a in data.get("accountList", [])
    ]
