import json
import sys
from typing import Any, Dict, List
from .aws import run_aws
from .sso_cache import load_active_sso_token

# Re-export required for monkeypatching in tests
load_active_sso_token = load_active_sso_token


def _aws_json(args: List[str]) -> Dict[str, Any]:
    res = run_aws(args)
    if res.get("returncode") != 0:
        sys.stderr.write("AWS CLI failed\n")
        sys.exit(1)
    return json.loads(res.get("stdout", "{}"))


def get_credentials(account: str, role: str, region: str) -> Dict[str, str]:
    args = [
        "sso",
        "get-role-credentials",
        "--account-id",
        account,
        "--role-name",
        role,
        "--region",
        region,
    ]
    data = _aws_json(args)
    creds = data.get("roleCredentials", {})
    if not creds:
        raise RuntimeError("No credentials returned")
    return {
        "AWS_ACCESS_KEY_ID": creds["accessKeyId"],
        "AWS_SECRET_ACCESS_KEY": creds["secretAccessKey"],
        "AWS_SESSION_TOKEN": creds["sessionToken"],
    }


def emit_exports(org: Any, account: str, role: str, region: str) -> str:
    try:
        c = get_credentials(account, role, region)
        lines = [f"export {k}={v}" for k, v in c.items()]
        name = getattr(org, "name", "base")
        lines.append(f"export AWS_PROFILE={name}-{account}-{role}")
        return "\n".join(lines)
    except Exception:
        if not load_active_sso_token(org):
            sys.stdout.write("No valid SSO token\n")
        else:
            sys.stdout.write("No role credentials\n")
        sys.exit(1)
