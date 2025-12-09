# file: src/awsctl/plugins/__init__.py
from __future__ import annotations

import inspect
import sys
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from importlib import import_module
from typing import Any, Optional

from awsctl.utils import console

PLUGIN_TIMEOUT_SEC = 10


def load_plugins(enabled: Optional[Iterable[str]]) -> list[object]:
    """Import and return plugin modules listed in `enabled`."""
    mods: list[object] = []
    for name in enabled or []:
        if not name.startswith("awsctl.plugins.") and not name.startswith("myorg.plugins."):
            console.print(f"[bold red][SECURITY] Blocked illegal plugin load attempt: {name}[/]")
            sys.exit(1)

        try:
            mods.append(import_module(name))
        except ImportError as e:
            console.print(f"[bold red][ERROR] Critical: Failed to load required plugin '{name}': {e}[/]")
            sys.exit(1)
    return mods


def _safe_exec(fn: Any, *args: Any, **kwargs: Any) -> None:
    """Execute a single hook with signature inspection fallback."""
    try:
        sig = inspect.signature(fn)
        if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
            fn(*args, **kwargs)
        else:
            try:
                bound = sig.bind(*args, **kwargs)
                bound.apply_defaults()
                fn(*bound.args, **bound.kwargs)
            except TypeError:
                try:
                    fn(*args)
                except TypeError:
                    console.print("[yellow][WARNING] Plugin hook signature mismatch. Skipping.[/]")
    except Exception as e:
        console.print(f"[bold red][ERROR] Plugin hook failed: {e}[/]")
        sys.exit(1)


def call_hook(mods: list[object], hook: str, *args: Any, **kwargs: Any) -> None:
    """
    Call `hook` on each module in `mods` if present.
    [FIX] PYBH-0065: Use wait=False on shutdown to prevent hanging on stuck threads.
    """
    if not mods:
        return

    # We instantiate the executor manually to control shutdown behavior
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        for m in mods:
            fn = getattr(m, hook, None)
            if callable(fn):
                future = executor.submit(_safe_exec, fn, *args, **kwargs)
                try:
                    future.result(timeout=PLUGIN_TIMEOUT_SEC)
                except TimeoutError:
                    console.print(f"\n[bold red][ERROR] Plugin hook '{hook}' timed out after {PLUGIN_TIMEOUT_SEC}s.[/]")
                    sys.exit(1)
    finally:
        # Do not wait for hanging threads; cancel them if possible and proceed
        executor.shutdown(wait=False, cancel_futures=True)
