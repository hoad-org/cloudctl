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
    try:
        c = get_credentials(account, role, region)
        lines = [f"export {k}={v}" for k, v in c.items()]
        lines.append(f"export AWS_PROFILE={org_name}-{account}-{role}")
        return "\n".join(lines)
    except Exception:
        if not load_active_sso_token(org):
            sys.stdout.write("No valid SSO token\n")
        else:
            sys.stdout.write("No role credentials\n")
        sys.exit(1)
