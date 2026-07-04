"""
cloudctl.exit_codes — the documented, agent-facing process exit-code scheme.

These are the SAME numbers the top-level ``--help`` epilog advertises and that
``errors.CloudCtlError`` subclasses already carry. Centralising them here lets
command handlers return semantically-meaningful codes at the obvious sites so an
agent can branch on ``$?`` without parsing prose:

    0  OK          success
    1  ERROR       general / uncategorised failure
    2  AUTH        authentication required (no/expired SSO session)
    3  NOT_FOUND   invalid org / account / role
    4  DENIED      permission / role access denied (guardrails)
    5  USAGE       invalid arguments / no-TTY-cannot-prompt

Only apply a specific code where the cause is unambiguous. When a failure is
genuinely uncategorised, ERROR (1) is the correct answer — do not force a code.
"""

OK = 0
ERROR = 1
AUTH = 2
NOT_FOUND = 3
DENIED = 4
USAGE = 5
