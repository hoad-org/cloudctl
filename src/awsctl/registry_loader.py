# file: src/awsctl/registry_loader.py
# SPDX-License-Identifier: MIT
"""
Remote Registry Loader.
Handles HTTPS fetching and cryptographic signature verification.
"""

from __future__ import annotations

import gzip
import io
import json
import sys
from typing import Any, Dict, List, Optional

import requests
from rich.console import Console

# Use a local console to avoid circular imports from utils
console = Console(stderr=True)

MAX_REGISTRY_SIZE = 1024 * 1024  # 1 MB Limit (Compressed)
MAX_DECOMPRESSED_SIZE = 10 * 1024 * 1024  # 10 MB Limit (Expanded)
MAX_SIG_SIZE = 1024  # 1 KB Limit for Minisign signature


def fetch_remote_registry(url: str, public_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Fetch registry from a remote URL with optional cryptographic verification.
    """
    # 🛡️ SECURITY FIX: Enforce HTTPS to prevent Man-In-The-Middle or Local File Inclusion
    if not url.lower().startswith("https://"):
        console.print(f"[bold red]Security Error: Registry URL must be HTTPS: {url}[/]")
        sys.exit(1)

    try:
        console.print(f"[dim]Fetching registry from {url}...[/]")

        # 🛡️ SECURITY FIX: Stream download to enforce size limit (DoS Prevention)
        with requests.get(url, timeout=5, stream=True) as resp:
            resp.raise_for_status()
            # Read only up to limit + 1 byte to detect overflow
            content = resp.raw.read(MAX_REGISTRY_SIZE + 1)

        if len(content) > MAX_REGISTRY_SIZE:
            console.print(f"[bold red]Error: Registry file exceeds limit ({MAX_REGISTRY_SIZE} bytes)[/]")
            sys.exit(1)

        # [FIX] PYBH-0051 & PYBH-0066: Handle Gzip with expansion limits (Zip Bomb Guard)
        if content.startswith(b"\x1f\x8b"):
            try:
                with gzip.GzipFile(fileobj=io.BytesIO(content)) as gz:
                    decompressed = bytearray()
                    # Read in chunks to check size growth
                    for chunk in iter(lambda: gz.read(4096), b""):
                        decompressed.extend(chunk)
                        if len(decompressed) > MAX_DECOMPRESSED_SIZE:
                            raise ValueError(f"Decompressed size exceeds limit ({MAX_DECOMPRESSED_SIZE} bytes)")
                content = bytes(decompressed)
            except Exception as e:
                console.print(f"[bold red]Error decompressing registry: {e}[/]")
                sys.exit(1)

        # TIER 3: Signed Mode
        if public_key:
            try:
                import minisign
            except ImportError:
                console.print("[bold red]Error: Tier 3 Security (Signed Registry) requires 'minisign' library.[/]")
                # [FIX] Better UX: Suggest correct PyPI package name
                console.print("Please install it: [green]pipx inject awsctl minisign-verify[/]")
                sys.exit(1)

            sig_url = url + ".minisig"
            console.print(f"[dim]Verifying signature from {sig_url}...[/]")

            try:
                # [FIX] PYBH-0062: Protect signature download against unlimited streams
                with requests.get(sig_url, timeout=5, stream=True) as sig_resp:
                    sig_resp.raise_for_status()
                    sig_content = sig_resp.raw.read(MAX_SIG_SIZE + 1)

                if len(sig_content) > MAX_SIG_SIZE:
                    raise ValueError("Signature file too large")

                pub = minisign.PublicKey(public_key)
                pub.verify(content, sig_content)
                console.print("[success]✓ Signature Verified[/]")
            except Exception as e:
                console.print("[bold red]CRITICAL: Registry signature mismatch![/]")
                console.print("The remote configuration may have been tampered with.")
                console.print(f"Error: {e}")
                sys.exit(1)

        # TIER 2: HTTPS Mode (Implicit trust in TLS)
        data = json.loads(content)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "orgs" in data:
            # Support wrapping dict
            return list(data["orgs"])

        raise ValueError("Invalid registry format. Expected list or dict with 'orgs'.")

    except Exception as e:
        console.print(f"[red]Failed to load remote registry: {e}[/]")
        # Fail safe: Do not fall back to local if remote was explicitly requested
        sys.exit(1)
