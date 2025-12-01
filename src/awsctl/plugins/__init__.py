# file: src/awsctl/plugins/__init__.py
from __future__ import annotations

from collections.abc import Iterable
from importlib import import_module
from typing import Any, Optional


def load_plugins(enabled: Optional[Iterable[str]]) -> list[object]:
    """Import and return plugin modules listed in `enabled`."""
    mods: list[object] = []
    for name in enabled or []:
        try:
            mods.append(import_module(name))
        except ImportError:
            # Best-effort load. Skip broken or missing plugins.
            continue
    return mods


def call_hook(
    mods: list[object], hook: str, *args: Any, **kwargs: Any
) -> None:  # [FIX] Add type hints
    """Call `hook` on each module in `mods` if present."""
    for m in mods:
        fn = getattr(m, hook, None)
        if callable(fn):
            fn(*args, **kwargs)
