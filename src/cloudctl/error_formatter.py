"""
cloudctl.error_formatter — Format CloudCtlError for display to users.

This module provides:
- Consistent, colorized error formatting for terminal display
- Context information display (without secrets)
- Actionable suggestion display
- Recovery command suggestions
"""

from typing import Dict, Any, List
from .errors import CloudCtlError


def format_error(error: CloudCtlError) -> str:
    """
    Format a CloudCtlError for display to stderr.

    Returns a multi-line formatted error with error type, message, context,
    suggestions, and recovery command (if available).

    Args:
        error: The CloudCtlError to format

    Returns:
        Formatted error string ready for stderr output
    """
    lines = []

    # Error header with type
    error_type_display = error.error_type.value.upper().replace("_", " ")
    lines.append(f"\n✗ {error_type_display}")

    # Error message
    lines.append(f"  {error.message}\n")

    # Context (if available)
    if error.context:
        context_str = format_context(error.context)
        if context_str:
            lines.append("Context:")
            lines.append(context_str)
            lines.append("")

    # Suggestions (if available)
    if error.suggestions:
        suggestions_str = format_suggestions(error.suggestions)
        if suggestions_str:
            lines.append("What you can do:")
            lines.append(suggestions_str)
            lines.append("")

    # Recovery command (if available)
    if error.recovery_command:
        recovery_str = format_recovery(error.recovery_command)
        if recovery_str:
            lines.append(recovery_str)
            lines.append("")

    return "\n".join(lines).rstrip()


def format_context(context: Dict[str, Any]) -> str:
    """
    Format context dictionary for display.

    Secrets (passwords, tokens, keys) are filtered out.
    Returns pretty-printed context with indentation.

    Args:
        context: Dict with diagnostic context

    Returns:
        Formatted context string or empty string if no safe context
    """
    if not context:
        return ""

    # Filter out secrets
    safe_context = _filter_secrets(context)
    if not safe_context:
        return ""

    lines = []
    for key, value in safe_context.items():
        # Format key with proper indentation
        key_display = key.replace("_", " ").title()

        # Format value based on type
        if isinstance(value, list):
            if len(value) <= 3:
                value_str = ", ".join(str(v) for v in value)
            else:
                value_str = (
                    ", ".join(str(v) for v in value[:3]) + f", ... ({len(value)} total)"
                )
        else:
            value_str = str(value)

        lines.append(f"  {key_display}: {value_str}")

    return "\n".join(lines)


def format_suggestions(suggestions: List[str]) -> str:
    """
    Format a list of suggestions as a numbered list.

    Args:
        suggestions: List of suggestion strings

    Returns:
        Formatted suggestions string or empty string if no suggestions
    """
    if not suggestions:
        return ""

    lines = []
    for i, suggestion in enumerate(suggestions, 1):
        # Wrap long suggestions to fit in terminal
        wrapped = _wrap_text(suggestion, width=70, initial_indent="  ")
        lines.append(f"  {i}. {wrapped}")

    return "\n".join(lines)


def format_recovery(recovery_command: str) -> str:
    """
    Format a recovery command suggestion.

    Args:
        recovery_command: The command to run to recover from error

    Returns:
        Formatted recovery command string
    """
    if not recovery_command:
        return ""

    lines = [
        "Try this command:",
        f"  {recovery_command}",
    ]
    return "\n".join(lines)


def _filter_secrets(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Filter out sensitive information from context dict.

    Removes or masks any keys that look like secrets.

    Args:
        context: The context dict to filter

    Returns:
        Filtered context dict with secrets removed
    """
    secret_keywords = {
        "password",
        "token",
        "secret",
        "key",
        "credential",
        "access_key",
        "secret_key",
        "aws_secret",
        "api_key",
        "private_key",
    }

    safe_context = {}
    for key, value in context.items():
        key_lower = key.lower()
        # Skip keys that look like secrets
        if any(secret in key_lower for secret in secret_keywords):
            continue
        safe_context[key] = value

    return safe_context


def _wrap_text(text: str, width: int = 70, initial_indent: str = "") -> str:
    """
    Wrap text to fit in terminal width.

    Simple word-wrap implementation that preserves formatting.

    Args:
        text: Text to wrap
        width: Maximum line width (default 70)
        initial_indent: Indentation for first line (default empty)

    Returns:
        Wrapped text string
    """
    # For simplicity, if text fits, return as-is
    indent_width = len(initial_indent)
    if len(text) + indent_width <= width:
        return text

    # Otherwise, split on word boundaries
    words = text.split()
    lines = []
    current_line = []
    current_length = indent_width

    for word in words:
        word_len = len(word) + 1  # +1 for space
        if current_length + word_len > width and current_line:
            # Start new line
            lines.append(" ".join(current_line))
            current_line = [word]
            current_length = len(word) + 1 + indent_width
        else:
            current_line.append(word)
            current_length += word_len

    if current_line:
        lines.append(" ".join(current_line))

    return "\n".join(lines)
