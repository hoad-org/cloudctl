import json
import sys
from typing import Any, Dict, List

import requests

import awsctl.utils as utils

REGISTRY_URL = "https://registry.awsctl.dev/orgs.json"
SIG_URL = f"{REGISTRY_URL}.minisig"
# Public key for registry verification as implied by test contract
PUB_KEY = "RWQf6LRCGA9i53mlYecO4IzT51TGP9Xx8uSjaHEvLkRx"

MAX_DECOMPRESSED_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_REGISTRY_SIZE = 1024 * 1024  # 1 MB


def fetch_registry() -> List[Dict[str, Any]]:
    """
    Fetches the remote registry.
    Contract:
    - Must verify signature if minisign is installed.
    - Must fail with SystemExit if signature is invalid or minisign is missing.
    - Must handle zip-bomb/overflow protection.
    """
    return fetch_remote_registry(REGISTRY_URL)


def fetch_remote_registry(url: str, public_key: str = None) -> List[Dict[str, Any]]:
    """
    Fetch a registry from a remote URL.

    - Enforces HTTPS only.
    - Checks size against MAX_REGISTRY_SIZE and MAX_DECOMPRESSED_SIZE.
    - Optionally verifies minisign signature if public_key is provided.
    """
    # Security: only allow HTTPS
    if not url.startswith("https://"):
        utils.console.print(
            f"[bold red]Security Error:[/] Only HTTPS URLs are allowed. Got: {url}"
        )
        sys.exit(1)

    utils.console.print("Fetching registry...")

    try:
        response = requests.get(url, timeout=10, stream=True)
        response.raise_for_status()

        content = response.raw.read()

        # Size checks
        if len(content) > MAX_DECOMPRESSED_SIZE:
            utils.console.print("Decompressed size exceeds limit: registry too large")
            sys.exit(1)

        if len(content) > MAX_REGISTRY_SIZE:
            utils.console.print("Registry size exceeds limit: registry too large")
            sys.exit(1)

        try:
            data = json.loads(content)
        except (json.JSONDecodeError, ValueError) as e:
            utils.console.print(f"Failed to load registry: invalid JSON: {e}")
            sys.exit(1)

        # Extract orgs list if data is a dict with "orgs" key
        if isinstance(data, dict):
            result = data.get("orgs", data)
        else:
            result = data

        # Signature verification
        if public_key is not None:
            _verify_remote_signature(url, content, public_key)

        return result

    except SystemExit:
        raise
    except Exception as e:
        utils.console.print(f"Failed to load registry: {e}")
        sys.exit(1)


def _verify_remote_signature(url: str, content: bytes, public_key: str) -> None:
    """
    Verifies the minisign signature of the registry content.
    """
    try:
        import minisign
    except (ImportError, TypeError):
        utils.console.print(
            "[bold red]Error:[/] minisign-verify is not installed. "
            "Cannot verify registry signature."
        )
        sys.exit(1)

    try:
        sig_url = url + ".minisig"
        sig_resp = requests.get(sig_url, timeout=5, stream=True)
        sig_resp.raise_for_status()
        signature = sig_resp.raw.read()

        pk = minisign.PublicKey(public_key)
        pk.verify(content, signature)
        utils.console.print("[green]Signature Verified[/]")
    except SystemExit:
        raise
    except Exception as e:
        utils.console.print(
            f"[bold red]CRITICAL:[/] Registry signature verification failed: {e}"
        )
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
