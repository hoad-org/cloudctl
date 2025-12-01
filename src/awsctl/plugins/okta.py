# file: src/awsctl/plugins/okta.py
# SPDX-License-Identifier: MIT
"""
Okta plugin implementation.
Performs pre-flight connectivity checks (VPN/Internet).
"""
import sys
from typing import Any, Dict

import requests

from awsctl.utils import console


def pre_login(org: Dict[str, Any]) -> None:
    """
    Hook execution flow:
    1. Check config existence.
    2. Perform HEAD request to SSO URL to verify reachability.
    """
    name = org.get("name")
    console.print(f"[dim]Running network checks for {name}...[/]")

    # 1. Config Validation
    url = org.get("sso_start_url")
    if not url:
        console.print("[warning]⚠ 'sso_start_url' missing. Skipping checks.[/]")
        return

    # 2. Connectivity Check
    try:
        # Short timeout (3s) to detect VPN issues quickly
        resp = requests.head(url, timeout=3, allow_redirects=True)

        if resp.status_code >= 400:
            # 401/403 means reachable but unauthenticated (which is fine for pre-check)
            if resp.status_code not in (401, 403):
                console.print(f"[error]✗ SSO URL returned error {resp.status_code}[/]")
                console.print(f"  URL: {url}")
                sys.exit(1)

        console.print(f"[success]✓ SSO Endpoint reachable ({url})[/]")

    except requests.exceptions.ConnectionError:
        console.print("[error]✗ Connection Failed![/]")
        console.print(f"  Could not reach: {url}")
        console.print("  [yellow]Hint: Are you connected to the corporate VPN?[/]")
        sys.exit(1)

    except requests.exceptions.Timeout:
        console.print("[error]✗ Connection Timed Out![/]")
        console.print("  The SSO endpoint is not responding.")
        sys.exit(1)

    except Exception as e:
        console.print(f"[error]✗ Unexpected error during pre-flight: {e}[/]")
        # Fail safe
        sys.exit(1)
