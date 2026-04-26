# file: tests/test_strategy.py
# SPDX-License-Identifier: MIT
"""
Tests for the 'Context Bridge' strategy router in cloudctl.cli.
Ensures the shell wrapper knows when to EVAL output vs EXEC commands.
"""

import pytest
from cloudctl.cli import determine_strategy


@pytest.mark.parametrize(
    "argv,expected",
    [
        # --- EVAL Strategies (Modify Shell) ---
        # These commands emit export/unset strings for the shell to evaluate.
        (["switch"], "EVAL"),
        (["switch", "my-account"], "EVAL"),
        (["switch", "-"], "EVAL"),
        (["use"], "EVAL"),
        (["logout"], "EVAL"),
        # Login Chaining (The "Dream Workflow")
        # Login only needs EVAL if it's jumping straight to an account/role/region.
        (["login", "--account", "123"], "EVAL"),
        (["login", "-a", "123"], "EVAL"),  # Shorthand
        (["login", "--role", "Admin"], "EVAL"),
        (["login", "-r", "Admin"], "EVAL"),  # Shorthand
        (["login", "--region", "us-east-1"], "EVAL"),
        (["login", "-R", "us-east-1"], "EVAL"),  # Shorthand
        (["login", "--org", "foo", "--account", "123"], "EVAL"),
        # --- EXEC Strategies (Passthrough) ---
        # These commands are either interactive or just print status to console.
        ([], "EXEC"),  # No args -> Defaults to help/status
        (["login"], "EXEC"),  # Plain login is just SSO auth flow
        (["login", "--org", "engineering"], "EXEC"),  # SSO auth for specific org
        (["status"], "EXEC"),
        (["doctor"], "EXEC"),
        (["list", "accounts"], "EXEC"),
        (["setup"], "EXEC"),
        (["console"], "EXEC"),
        (
            ["exec", "123", "--", "ls"],
            "EXEC",
        ),  # The 'exec' command runs its own subprocess
        (["env"], "EXEC"),  # Prints vars for display, doesn't eval them
        (["cache-clear"], "EXEC"),
        (["--version"], "EXEC"),
        (["--help"], "EXEC"),
    ],
)
def test_strategy_router(argv, expected):
    """
    Validates that the strategy router correctly identifies shell-modifying commands.
    """
    assert determine_strategy(argv) == expected
