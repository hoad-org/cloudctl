import sys

from .cli import main as cli_main


def main() -> int:
    return cli_main(sys.argv[1:])
