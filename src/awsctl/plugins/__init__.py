import concurrent.futures
import importlib
import sys
from typing import Any, Callable, Dict, List, Optional

import awsctl.utils as utils

ILLEGAL_PLUGIN_PREFIXES = ("evil.",)


def load_plugins(plugin_names: Optional[List[str]]) -> Dict[str, Any]:
    """Load plugin modules. Returns dict of {name: module}."""
    if not plugin_names:
        return {}

    plugins = {}

    for name in plugin_names:
        if name.startswith(ILLEGAL_PLUGIN_PREFIXES):
            utils.console.print("Blocked illegal plugin")
            sys.exit(1)

        try:
            mod = importlib.import_module(name)
            plugins[name] = mod
        except Exception:
            utils.console.print(f"Failed to load plugin {name}")
            sys.exit(1)

    return plugins


def _safe_exec(fn: Callable, *args, **kwargs) -> Any:
    """Execute hook. Returns result of fn(*args, **kwargs)."""
    try:
        return fn(*args, **kwargs)
    except TypeError as e:
        utils.console.print(f"Plugin hook failed: {e}")
        sys.exit(1)
    except Exception as e:
        utils.console.print(f"Plugin hook failed: {e}")
        sys.exit(1)


def call_hook(mods: List[Any], hook_name: str, *args, **kwargs) -> List[Any]:
    """Orchestrate hooks. Returns list of results from each hook invocation."""
    results = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []

        for mod in mods:
            if not hasattr(mod, hook_name):
                continue
            fn = getattr(mod, hook_name)
            futures.append(executor.submit(_safe_exec, fn, *args, **kwargs))

        for fut in futures:
            try:
                result = fut.result(timeout=5)
                results.append(result)
            except (concurrent.futures.TimeoutError, TimeoutError):
                # Raw stdout for shell bridge
                print("timed out")
                # Interceptable console for tests
                utils.console.print("timed out")
                sys.exit(1)
            except Exception as e:
                utils.console.print(f"Plugin hook failed: {e}")
                sys.exit(1)

    return results
