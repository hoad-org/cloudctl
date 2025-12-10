# file: src/awsctl/use_exports.py
# SPDX-License-Identifier: MIT
"""
awsctl.use_exports
Emit export lines by calling sso get-role-credentials with the access token.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from typing import Any, Dict, List

# [FIX] Import resolve helper and clean env helper
from awsctl.aws import _resolve_aws_cli, get_clean_env

from .sso_cache import OrgRef
from .sso_cache import load_active_sso_token as load_active_sso_token

__all__ = ["emit_exports", "emit_unset", "load_active_sso_token", "_aws_json"]


def _redact_args(args: List[str]) -> List[str]:
    SENSITIVE_FLAGS = {
        "--access-token",
        "--session-token",
        "aws_session_token",
        "aws_secret_access_key",
    }
    safe_args = []
    skip_next = False

    for arg in args:
        if skip_next:
            safe_args.append("REDACTED")
            skip_next = False
            continue
        if "=" in arg:
            key, val = arg.split("=", 1)
            if key in SENSITIVE_FLAGS:
                safe_args.append(f"{key}=REDACTED")
                continue
        if arg in SENSITIVE_FLAGS:
            safe_args.append(arg)
            skip_next = True
            continue
        safe_args.append(arg)

    return safe_args


def _aws_json(args: List[str]) -> Dict[str, Any]:
    try:
        # [FIX] Use get_clean_env() to ensure we don't pick up ambient credentials
        # (like AWS_ACCESS_KEY_ID from a previous run) which might confuse the CLI.
        p = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
            env=get_clean_env(),
        )
    except subprocess.TimeoutExpired:
        # [FIX B904] Chain exception
        raise SystemExit("AWS CLI timed out.") from None

    if p.returncode != 0:
        safe_args = _redact_args(args)
        raise SystemExit(f"AWS CLI failed: {' '.join(safe_args)}\n{p.stderr.strip()}")

    try:
        result: Dict[str, Any] = json.loads(p.stdout or "{}")
        return result
    except json.JSONDecodeError:
        # [SECURITY FIX] Do NOT dump p.stdout here.
        # It may contain partial credentials if the JSON is malformed.
        raise SystemExit(
            "AWS CLI returned invalid JSON. Output suppressed for security."
        ) from None


def emit_exports(
    org: OrgRef,
    account_id: str,
    role_name: str,
    region: str,
    safe_output: bool = True,
) -> str:
    """
    Generate shell export commands for the given context.
    :param safe_output: If True, enforce TTY Guard to prevent dumping credentials
                        to screen. Set to False only for explicit 'env' commands.
    """
    # 🛡️ SECURITY FIX: Prevent dumping secrets to interactive terminal (TTY).
    # [TEST FIX] Allow bypass if AWSCTL_TEST_MODE env var is set.
    is_test = os.environ.get("AWSCTL_TEST_MODE") == "1"

    # [FIX] Robust TTY check for detached processes where __stdout__ is None
    real_stdout = sys.__stdout__
    is_tty = real_stdout.isatty() if real_stdout else False

    if is_tty and safe_output and not is_test:
        sys.stderr.write("❌ Security Error: Refusing to print credentials to TTY.\n")
        sys.stderr.write(
            "   Do not run _awsctl_bin directly. Use the 'awsctl' wrapper.\n"
        )
        sys.exit(1)

    tok = load_active_sso_token(org)

    if not tok or not tok.access_token:
        raise SystemExit(
            f"No valid SSO token found for {org.name}. Run `awsctl login`."
        )

    # [FIX] Resolve binary for Windows compatibility
    aws_bin = _resolve_aws_cli()

    cmd = [
        aws_bin,
        "sso",
        "get-role-credentials",
        "--account-id",
        account_id,
        "--role-name",
        role_name,
        "--access-token",
        tok.access_token,
        "--region",
        tok.region,
    ]

    data = _aws_json(cmd)
    creds = data.get("roleCredentials")

    if not creds:
        raise SystemExit("No role credentials returned from AWS CLI.")

    # Use shlex.quote to prevent shell injection via malicious role/region names
    exports = [
        f"export AWS_ACCESS_KEY_ID={shlex.quote(creds['accessKeyId'])}",
        f"export AWS_SECRET_ACCESS_KEY={shlex.quote(creds['secretAccessKey'])}",
        f"export AWS_SESSION_TOKEN={shlex.quote(creds['sessionToken'])}",
        f"export AWS_DEFAULT_REGION={shlex.quote(region)}",
        f"export AWS_REGION={shlex.quote(region)}",
    ]

    return "\n".join(exports)


def emit_unset() -> str:
    """
    Generate shell unset commands to clear the context.
    """
    keys = [
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_DEFAULT_REGION",
        "AWS_REGION",
    ]
    return "\n".join(f"unset {k}" for k in keys)
