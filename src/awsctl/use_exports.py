import json
import shlex
import sys
from typing import Any, Dict, List

from .aws import run_aws
from .sso_cache import load_active_sso_token


def _redact_args(args: List[str]) -> List[str]:
    """Scrub sensitive tokens from argument list."""
    result = []
    SENSITIVE_KEYS = ["token", "secret", "password", "credential"]
    for arg in args:
        if any(k in arg.lower() for k in SENSITIVE_KEYS):
            result.append("REDACTED")
        else:
            result.append(arg)
    return result


# Re-export required for monkeypatching in tests
load_active_sso_token = load_active_sso_token


def _aws_json(args: List[str]) -> Dict[str, Any]:
    import subprocess

    try:
        res = run_aws(args)
    except (subprocess.TimeoutExpired, RuntimeError):
        sys.stderr.write("AWS CLI failed\n")
        sys.exit(1)
    if res.get("returncode") != 0:
        sys.stderr.write("AWS CLI failed\n")
        sys.exit(1)
    try:
        return json.loads(res.get("stdout", "{}"))
    except (json.JSONDecodeError, ValueError):
        sys.stderr.write("AWS CLI failed\n")
        sys.exit(1)


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
    """
    Return shell 'export K=V' lines for the given org/account/role/region.

    For non-AWS providers (Azure, GCP), delegates to the CloudProvider so
    the correct credential variables are emitted.

    For AWS orgs (or legacy callers that pass a bare org object), uses the
    original _aws_json / get_credentials code path so existing tests that
    monkeypatch awsctl.use_exports._aws_json remain valid.
    """
    # Determine provider — default to "aws" for backwards compat
    if isinstance(org, dict):
        provider_name = org.get("provider", "aws")
        org_name = org.get("name", "base")
    else:
        provider_name = "aws"
        org_name = getattr(org, "name", "base")

    # Non-AWS: delegate entirely to the cloud provider
    if provider_name != "aws":
        try:
            from .providers import get_provider

            org_dict = (
                org
                if isinstance(org, dict)
                else {
                    "name": org_name,
                    "provider": provider_name,
                }
            )
            provider = get_provider(org_dict)
            return provider.get_exports(org_dict, account, role, region)
        except SystemExit:
            raise
        except Exception as e:
            sys.stdout.write(f"Failed to get credentials: {e}\n")
            sys.exit(1)

    # AWS legacy path — preserves monkeypatching contracts for existing tests
    # Check token FIRST to give a helpful message before attempting credentials
    if not load_active_sso_token(org):
        sys.stdout.write("No valid SSO token\n")
        sys.exit(1)
    try:
        c = get_credentials(account, role, region)
        lines = [f"export {k}={shlex.quote(v)}" for k, v in c.items()]
        lines.append(
            f"export AWS_PROFILE={shlex.quote(f'{org_name}-{account}-{role}')}"
        )
        return "\n".join(lines)
    except Exception:
        sys.stdout.write("No role credentials\n")
        sys.exit(1)
