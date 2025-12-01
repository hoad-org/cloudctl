# file: src/awsctl/use_exports.py
"""
awsctl.use_exports
Emit export lines by calling sso get-role-credentials with the access token.
"""
from __future__ import annotations

import json
import subprocess
from typing import Any, Dict, List

# [FIX] Re-export for core.py to use
from .sso_cache import OrgRef
from .sso_cache import load_active_sso_token as load_active_sso_token

# Explicit export for mypy
__all__ = ["emit_exports", "emit_unset", "load_active_sso_token", "_aws_json"]


def _aws_json(args: List[str]) -> Dict[str, Any]:
    p = subprocess.run(args, check=False, capture_output=True, text=True)
    if p.returncode != 0:
        raise SystemExit(f"AWS CLI failed: {' '.join(args)}\n{p.stderr.strip()}")
    result: Dict[str, Any] = json.loads(p.stdout or "{}")
    return result


def emit_exports(org: OrgRef, account_id: str, role_name: str, region: str) -> str:
    tok = load_active_sso_token(org)

    # [FIX] Mypy null check
    if not tok or not tok.access_token:
        raise SystemExit(
            f"No valid SSO token found for {org.name}. Run `awsctl login`."
        )

    data = _aws_json(
        [
            "aws",
            "sso",
            "get-role-credentials",
            "--region",
            tok.region,
            "--access-token",
            tok.access_token,
            "--account-id",
            account_id,
            "--role-name",
            role_name,
        ]
    )
    creds = data.get("roleCredentials") or {}
    ak = creds.get("accessKeyId")
    sk = creds.get("secretAccessKey")
    st = creds.get("sessionToken")
    if not (ak and sk and st):
        raise SystemExit("No role credentials returned. Check account/role assignment.")

    # Prefix with marker for the shell wrapper
    return (
        "#AWSCTL-EVAL:\n"
        f'export AWS_ACCESS_KEY_ID="{ak}"\n'
        f'export AWS_SECRET_ACCESS_KEY="{sk}"\n'
        f'export AWS_SESSION_TOKEN="{st}"\n'
        f'export AWS_REGION="{region}"\n'
        f'export AWS_DEFAULT_REGION="{region}"\n'
        "unset AWS_PROFILE\n"
    )


def emit_unset() -> str:
    """Emit commands to clear AWS environment variables."""
    return (
        "#AWSCTL-EVAL:\n"
        "unset AWS_ACCESS_KEY_ID\n"
        "unset AWS_SECRET_ACCESS_KEY\n"
        "unset AWS_SESSION_TOKEN\n"
        "unset AWS_REGION\n"
        "unset AWS_DEFAULT_REGION\n"
        "unset AWS_PROFILE\n"
        "echo '🔒 AWS session cleared from shell.'\n"
    )
