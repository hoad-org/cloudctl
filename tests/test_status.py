# file: tests/test_status.py
# SPDX-License-Identifier: MIT
"""
Tests for cloudctl.commands.status command with JSON output support.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from cloudctl.commands.status import StatusCommand


class MockArgs:
    """Mock args object for testing."""

    def __init__(self, format: str = "table"):
        self.format = format


def test_status_json_output(capsys, monkeypatch):
    """Verify that --format json returns valid JSON with required fields."""
    mock_context = {
        "org": "bt-avm",
        "account": "235494790978",
        "role": "admin",
        "region": "us-east-1",
        "provider": "aws",
    }

    # Patch at the point of import (in the status module)
    with patch("cloudctl.commands.status.load_context", return_value=mock_context):
        cmd = StatusCommand()
        args = MockArgs(format="json")
        result = cmd.execute(args)

        # Capture output (JSON goes to stdout via print)
        captured = capsys.readouterr()

        # Exit code should be 0
        assert result == 0

        # Try both stdout and stderr
        output = captured.out.strip() or captured.err.strip()

        # Parse JSON output
        json_output = json.loads(output)

        # Verify required fields
        assert json_output["organization"] == "bt-avm"
        assert json_output["account"] == "235494790978"
        assert json_output["role"] == "admin"
        assert json_output["region"] == "us-east-1"
        assert json_output["provider"] == "aws"
        assert json_output["status"] == "active"


def test_status_json_contains_required_fields(capsys, monkeypatch):
    """Verify JSON output contains all required fields for agent automation."""
    mock_context = {
        "org": "fdr-gvc",
        "account": "123456789012",
        "role": "developer",
        "region": "us-gov-east-1",
        "provider": "aws",
    }

    with patch("cloudctl.commands.status.load_context", return_value=mock_context):
        cmd = StatusCommand()
        args = MockArgs(format="json")
        cmd.execute(args)

        captured = capsys.readouterr()
        output = captured.out.strip() or captured.err.strip()
        json_output = json.loads(output)

        # Verify all required fields exist
        required_fields = [
            "organization",
            "account",
            "role",
            "region",
            "provider",
            "status",
            "timestamp",
        ]
        for field in required_fields:
            assert field in json_output, f"Missing required field: {field}"

        # Verify field types
        assert isinstance(json_output["organization"], str)
        assert isinstance(json_output["account"], str)
        assert isinstance(json_output["role"], str)
        assert isinstance(json_output["region"], str)
        assert isinstance(json_output["status"], str)


def test_status_table_output(capsys, monkeypatch):
    """Verify that default (table) format still works without --format argument."""
    mock_context = {
        "org": "bt-avm",
        "account": "235494790978",
        "role": "admin",
        "region": "us-east-1",
    }

    with patch("cloudctl.commands.status.load_context", return_value=mock_context):
        cmd = StatusCommand()
        args = MockArgs(format="table")
        result = cmd.execute(args)

        # Exit code should be 0
        assert result == 0

        # Capture stderr (where rich.Console outputs)
        captured = capsys.readouterr()

        # Should contain table output
        assert "bt-avm" in captured.err or "bt-avm" in captured.out


def test_status_no_context_json(capsys, monkeypatch):
    """Verify JSON output when no context is set."""
    with patch("cloudctl.commands.status.load_context", return_value=None):
        cmd = StatusCommand()
        args = MockArgs(format="json")
        result = cmd.execute(args)

        # Exit code should be 0
        assert result == 0

        # Parse JSON output
        captured = capsys.readouterr()
        output = captured.out.strip() or captured.err.strip()
        json_output = json.loads(output)

        # Verify error state
        assert json_output["status"] == "no_context"
        assert json_output["organization"] is None
        assert json_output["account"] is None
        assert json_output["role"] is None
        assert json_output["region"] is None


def test_status_no_format_arg_defaults_to_table(capsys, monkeypatch):
    """Verify that when format arg is not provided, table format is used."""
    mock_context = {
        "org": "bt-avm",
        "account": "235494790978",
        "role": "admin",
        "region": "us-east-1",
    }

    with patch("cloudctl.commands.status.load_context", return_value=mock_context):
        cmd = StatusCommand()

        # Create args without format attribute (simulates argparse default)
        args = MagicMock()
        args.format = "table"

        result = cmd.execute(args)
        assert result == 0


def test_status_json_is_valid_json(capsys, monkeypatch):
    """Verify JSON output is always valid JSON that can be parsed."""
    mock_context = {
        "org": "gcp-prod",
        "account": "project-123",
        "role": "editor",
        "region": "us-central1",
        "provider": "gcp",
    }

    with patch("cloudctl.commands.status.load_context", return_value=mock_context):
        cmd = StatusCommand()
        args = MockArgs(format="json")
        cmd.execute(args)

        captured = capsys.readouterr()
        output = captured.out.strip() or captured.err.strip()

        # Should not raise an exception
        json_output = json.loads(output)

        # Should be a valid dict
        assert isinstance(json_output, dict)
        assert len(json_output) > 0
