# file: tests/test_strategy.py
# SPDX-License-Identifier: MIT
"""
Tests for the 'Context Bridge' strategy router in awsctl.cli.
Ensures the shell wrapper knows when to EVAL output vs EXEC commands.
"""

import pytest

from awsctl.cli import determine_strategy


@pytest.mark.parametrize(
    "argv,expected",
    [
        # --- EVAL Strategies (Modify Shell) ---
        (["switch"], "EVAL"),
        (["switch", "my-account"], "EVAL"),
        (["switch", "-"], "EVAL"),
        (["use"], "EVAL"),
        (["logout"], "EVAL"),
        # Login Chaining (The "Dream Workflow")
        (["login", "--account", "123"], "EVAL"),
        (["login", "--role", "Admin"], "EVAL"),
        (["login", "--region", "us-east-1"], "EVAL"),
        (["login", "--org", "foo", "--account", "123"], "EVAL"),
        # --- EXEC Strategies (Passthrough) ---
        ([], "EXEC"),  # No args -> Help
        (["login"], "EXEC"),  # Plain login is just auth
        (["login", "--org", "engineering"], "EXEC"),  # Just auth
        (["status"], "EXEC"),
        (["doctor"], "EXEC"),
        (["list", "accounts"], "EXEC"),
        (["setup"], "EXEC"),
        (["console"], "EXEC"),
        (
            ["exec", "123", "--", "ls"],
            "EXEC",
        ),  # Subprocess handles vars, not shell eval
        (["env"], "EXEC"),  # Prints to stdout, doesn't need eval
        (["cache-clear"], "EXEC"),
        (["--version"], "EXEC"),
        (["--help"], "EXEC"),
    ],
)
def test_strategy_router(argv, expected):
    assert determine_strategy(argv) == expected
