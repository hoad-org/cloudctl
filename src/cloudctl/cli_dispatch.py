from typing import List

from .utils import console


def dispatch(module, args: List[str]) -> int:
    if not hasattr(module, "main"):
        console.print("Invalid command module")
        return 1

    try:
        return module.main(args)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        console.print(f"Command failed: {exc}")
        return 1
