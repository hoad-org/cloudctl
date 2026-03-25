# src/awsctl/commands/base.py
from abc import ABC, abstractmethod
from typing import Any
from rich.console import Console


class BaseCommand(ABC):
    """Abstract base class for all awsctl commands."""

    def __init__(self):
        # Always output status messages to stderr to avoid polluting
        # the stdout stream used by shell hooks.
        self.console = Console(stderr=True)

    @abstractmethod
    def configure_parser(self, subparsers: Any):
        """Adds command-specific arguments to the subparser."""
        pass

    @abstractmethod
    def execute(self, args: Any) -> int:
        """Contains the core logic for command execution."""
        pass
