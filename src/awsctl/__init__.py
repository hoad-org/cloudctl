# src/awsctl/__init__.py
"""awsctl: Enterprise AWS Identity & Context Manager."""

import importlib

try:
    from awsctl._version import __version__
except ImportError:
    __version__ = "1.1.0"


def __getattr__(name):
    """
    Lazy module loader to prevent circular dependency crashes.
    """
    modules = [
        "accounts",
        "aws",
        "cli",
        "cli_accounts",
        "config",
        "context_manager",
        "core",
        "doctor",
        "guardrails",
        "help_text",
        "interactive",
        "main",
        "registry",
        "registry_loader",
        "shell",
        "sso_cache",
        "use_exports",
        "utils",
        "wizard",
    ]
    if name in modules:
        return importlib.import_module(f"awsctl.{name}")
    if name == "main":
        mod = importlib.import_module("awsctl.main")
        return mod.main
    raise AttributeError(f"module 'awsctl' has no attribute '{name}'")


__all__ = ["main"]
