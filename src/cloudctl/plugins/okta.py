import sys
from typing import Any, Dict

import requests

import cloudctl.utils as utils


def pre_login(org: Dict[str, Any]) -> None:
    """
    Okta pre-login hook.
    Contract: Must resolve utils.console at runtime to avoid stale references.
    """
    utils.debug_print(f"Okta plugin: Preparing login for {org}")

    # 1. Missing URL (Contract: Warning only, no exit)
    sso_url = org.get("sso_start_url")
    if not sso_url:
        utils.console.print("Okta plugin: SSO URL is missing in configuration")
        return

    # 2. Insecure URL (Contract: Security exit)
    if sso_url.startswith("http://"):
        utils.console.print("Security Error: Insecure HTTP URL detected for SSO")
        sys.exit(1)

    # 3. Health check
    try:
        resp = requests.head(sso_url, timeout=5)
        if resp.status_code != 200:
            utils.console.print(
                f"SSO Endpoint error: Returned status {resp.status_code}"
            )
            sys.exit(1)
    except requests.exceptions.Timeout:
        utils.console.print("Timed out while checking SSO endpoint")
        sys.exit(1)
    except requests.exceptions.ConnectionError:
        utils.console.print("Failed to connect to SSO endpoint")
        sys.exit(1)
    except Exception as e:
        utils.console.print(f"Unexpected error during SSO check: {e}")
        sys.exit(1)

    # 4. Success
    utils.console.print("SSO Endpoint reachable")
