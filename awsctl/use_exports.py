# file: awsctl/use_exports.py
"""
awsctl.use_exports
Emit export lines by calling sso get-role-credentials with the access token.
Avoid profiles entirely. Works on macOS, Linux, WSL, bash, zsh.
"""
from __future__ import annotations

import json
import subprocess

from .sso_cache import OrgRef, load_active_sso_token


def _aws_json(args) -> dict:
    p = subprocess.run(args, check=False, capture_output=True, text=True)
    if p.returncode != 0:
        raise SystemExit(f"AWS CLI failed: {' '.join(args)}\n{p.stderr.strip()}")
    return json.loads(p.stdout or "{}")


def emit_exports(org: OrgRef, account_id: str, role_name: str, region: str) -> str:
    tok = load_active_sso_token(org)
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
    return (
        f'export AWS_ACCESS_KEY_ID="{ak}"\n'
        f'export AWS_SECRET_ACCESS_KEY="{sk}"\n'
        f'export AWS_SESSION_TOKEN="{st}"\n'
        f'export AWS_REGION="{region}"\n'
        f'export AWS_DEFAULT_REGION="{region}"\n'
        "unset AWS_PROFILE\n"
    )
