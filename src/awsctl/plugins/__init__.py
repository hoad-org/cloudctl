import concurrent.futures
import importlib
import sys
from typing import Any, Callable, List

import awsctl.utils as utils

ILLEGAL_PLUGIN_PREFIXES = ("evil.",)


def load_plugins(plugin_names: List[str]) -> List[Any]:
    """Load plugin modules. Contract: Resolution through utils module."""
    plugins = []

    for name in plugin_names:
        if name.startswith(ILLEGAL_PLUGIN_PREFIXES):
            utils.console.print("Blocked illegal plugin")
            sys.exit(1)

        try:
            mod = importlib.import_module(name)
            plugins.append(mod)
        except Exception:
            utils.console.print(f"Failed to load plugin {name}")
            sys.exit(1)

    return plugins


def _safe_exec(fn: Callable, *args) -> None:
    """Execute hook. Contract: Runtime console resolution."""
    try:
        fn(*args)
    except TypeError as e:
        utils.console.print(f"Plugin hook failed: {e}")
        sys.exit(1)
    except Exception as e:
        utils.console.print(f"Plugin hook failed: {e}")
        sys.exit(1)


def call_hook(mods: List[Any], hook_name: str, *args) -> None:
    """Orchestrate hooks. Contract: Catch multiple timeout types."""
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []

        for mod in mods:
            if not hasattr(mod, hook_name):
                continue
            fn = getattr(mod, hook_name)
            futures.append(executor.submit(_safe_exec, fn, *args))

        for fut in futures:
            try:
                fut.result(timeout=5)
            except (concurrent.futures.TimeoutError, TimeoutError):
                # Raw stdout for shell bridge
                print("timed out")
                # Interceptable console for tests
                utils.console.print("timed out")
                sys.exit(1)
            except Exception as e:
                utils.console.print(f"Plugin hook failed: {e}")
                sys.exit(1)
