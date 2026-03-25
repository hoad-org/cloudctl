import sys
from pathlib import Path
from typing import Any, List, Optional
from . import core, utils, _version

stdout_console = utils.stdout_console
CONTEXT_FILE = Path.home() / ".awsctl" / "context.json"


def _resolved_version() -> str:
    return _version.__version__


def load_context() -> dict:
    return core.context_manager.load_context()


def determine_strategy(argv: List[str]) -> str:
    if not argv:
        return "EXEC"
    eval_cmds = ["switch", "use", "logout"]
    if argv[0] in eval_cmds:
        return "EVAL"
    if argv[0] == "login" and any(
        x in argv for x in ["--account", "-a", "--role", "-r", "--region", "-R"]
    ):
        return "EVAL"
    return "EXEC"


def cmd_setup(args: Any) -> int:
    return core.cmd_setup()


def main(argv: Optional[List[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if "--version" in argv:
        utils.console.print(_resolved_version())
        return 0
    return 0
