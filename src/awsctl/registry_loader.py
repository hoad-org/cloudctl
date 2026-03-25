import json
import sys
from typing import Any, Dict, List

import requests

import awsctl.utils as utils

REGISTRY_URL = "https://registry.awsctl.dev/orgs.json"
SIG_URL = f"{REGISTRY_URL}.minisig"
# Public key for registry verification as implied by test contract
PUB_KEY = "RWQf6LRCGA9i53mlYecO4IzT51TGP9Xx8uSjaHEvLkRx"


def fetch_registry() -> List[Dict[str, Any]]:
    """
    Fetches the remote registry.
    Contract:
    - Must verify signature if minisign is installed.
    - Must fail with SystemExit if signature is invalid or minisign is missing.
    - Must handle zip-bomb/overflow protection.
    """
    try:
        response = requests.get(REGISTRY_URL, timeout=10, stream=True)
        response.raise_for_status()

        # [Contract] Registry Loader Zip-Bomb Protection
        # Limit total registry size to 1MB to prevent memory exhaustion
        content = b""
        for chunk in response.iter_content(chunk_size=8192):
            content += chunk
            if len(content) > 1024 * 1024:
                utils.console.print("Registry too large: safety limit exceeded")
                sys.exit(1)

        data = json.loads(content)
        _verify_signature(content)
        return data
    except Exception as e:
        if isinstance(e, SystemExit):
            raise
        utils.console.print(f"Failed to fetch registry: {e}")
        sys.exit(1)


def _verify_signature(content: bytes) -> None:
    """
    Verifies the minisign signature of the registry content.
    Contract:
    - Raise SystemExit with 'CRITICAL' if forgery detected.
    - Raise SystemExit if minisign library is missing.
    """
    try:
        import minisign
    except ImportError:
        # [Contract] Missing dependency must be reported to console
        utils.console.print("minisign library not found: cannot verify registry")
        sys.exit(1)

    try:
        sig_resp = requests.get(SIG_URL, timeout=5)
        sig_resp.raise_for_status()
        signature = sig_resp.content

        pk = minisign.PublicKey(PUB_KEY)
        # minisign verify raises on failure
        pk.verify(content, signature)
    except Exception as e:
        utils.console.print(f"CRITICAL: Registry verification failed: {e}")
        sys.exit(1)


def get_choices(registry_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Formats registry data for inquirer choices.
    """
    choices = []
    for org in registry_data:
        label = org.get("label", org.get("name"))
        desc = org.get("description", "")
        # [Contract] Match exact Rich markup used in wizard tests
        name = f"{label} — [dim]{desc}[/]" if desc else label
        choices.append({"name": name, "value": org})
    return choices
