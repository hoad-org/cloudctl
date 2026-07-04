import sys
from typing import List, Optional


def main(argv: Optional[List[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    import cloudctl.cli as _cli

    return _cli.main(argv)
