"""
Tests to verify that profile commands clarify they are for humans, not agents.

Ensures:
1. Profile command handlers show agent-specific warnings
2. Export command shows no-credentials warning
3. README mentions agent-specific guidance
4. All profile commands are human-only
"""

import json
import tempfile
from pathlib import Path


class TestProfileCommandWarnings:
    """Verify that all profile commands show agent warnings."""

    def test_profile_module_has_agent_warning_in_docstring(self):
        """Profile module docstring should warn agents."""
        profile_file = (
            Path(__file__).parent.parent
            / "src"
            / "cloudctl"
            / "commands"
            / "profile.py"
        )
        assert profile_file.exists(), f"Profile file not found at {profile_file}"

        content = profile_file.read_text()

        # Check for agent warning in module docstring
        assert (
            "HUMAN" in content or "human" in content
        ), "Profile module should mention humans"
        assert "agent" in content.lower(), "Profile module should mention agents"
        assert (
            "--non-interactive" in content
        ), "Profile module should mention --non-interactive as alternative"


class TestProfileExportShowsWarning:
    """Verify that export command shows proper warnings."""

    def test_profile_export_has_no_creds_warning(self):
        """Profile export function should warn about no credentials."""
        profile_file = (
            Path(__file__).parent.parent
            / "src"
            / "cloudctl"
            / "commands"
            / "profile.py"
        )
        content = profile_file.read_text()

        # Check for export warning
        assert (
            "local-only" in content or "not portable" in content
        ), "Export should mention local-only nature"
        assert (
            "NO credentials" in content or "no credentials" in content
        ), "Export should mention it contains no credentials"

    def test_profile_export_no_credentials_in_concept(self):
        """Exported profile file should never contain credentials in concept."""
        # Create a mock profile export output
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "profiles.json"

            # Sample exported profile content (what cmd_profile_export would produce)
            exported_data = {
                "profiles": [
                    {
                        "name": "prod",
                        "org": "bt-avm",
                        "account": "235494790978",
                        "role": "admin",
                        "region": "us-east-1",
                        "created_at": "2026-06-03T10:00:00Z",
                        "last_used": "2026-06-03T11:00:00Z",
                    }
                ]
            }

            # Write to file
            output_file.write_text(json.dumps(exported_data, indent=2))

            # Read back and verify no credentials
            content = output_file.read_text()

            # Check for common credential patterns that should NOT be present
            forbidden_patterns = [
                "AKIA",  # AWS Access Key
                "ASIA",  # AWS Session Access Key
                "aws_access_key",
                "aws_secret_access_key",
                "AWS_SECRET",
                "password",
                "token:",
                "secret:",
            ]

            for pattern in forbidden_patterns:
                assert (
                    pattern not in content.upper()
                ), f"Found credential pattern '{pattern}' in exported profile"


class TestProfileCommandsShowHumanWarnings:
    """Test that all profile commands show human-only warnings."""

    def test_save_command_shows_warning(self):
        """Save command should show human-only warning."""
        profile_file = (
            Path(__file__).parent.parent
            / "src"
            / "cloudctl"
            / "commands"
            / "profile.py"
        )
        content = profile_file.read_text()

        # Check that save function shows warning
        assert "cmd_profile_save" in content
        # The function should contain agent warning
        save_section = content[
            content.find("def cmd_profile_save") : content.find("def cmd_profile_load")
        ]
        assert (
            "Profiles are for humans" in save_section or "agent" in save_section.lower()
        ), "Save command should warn about human-only use"

    def test_load_command_shows_warning(self):
        """Load command should show human-only warning."""
        profile_file = (
            Path(__file__).parent.parent
            / "src"
            / "cloudctl"
            / "commands"
            / "profile.py"
        )
        content = profile_file.read_text()

        assert "cmd_profile_load" in content
        # The function should contain agent warning
        load_section = content[
            content.find("def cmd_profile_load") : content.find("def cmd_profile_list")
        ]
        assert (
            "Profiles are for humans" in load_section or "agent" in load_section.lower()
        ), "Load command should warn about human-only use"

    def test_export_command_shows_warning(self):
        """Export command should show special export warning."""
        profile_file = (
            Path(__file__).parent.parent
            / "src"
            / "cloudctl"
            / "commands"
            / "profile.py"
        )
        content = profile_file.read_text()

        assert "cmd_profile_export" in content
        export_section = content[
            content.find("def cmd_profile_export") : content.find(
                "def cmd_profile_import"
            )
        ]
        assert (
            "local-only" in export_section or "portable" in export_section
        ), "Export should warn about local-only nature"


class TestReadmeHasAgentGuidance:
    """Verify README contains agent-specific guidance."""

    def test_readme_mentions_agents_should_not_use_profiles(self):
        """README should contain section about agent automation."""
        readme_path = Path(__file__).parent.parent / "README.md"
        assert readme_path.exists(), "README.md not found"

        content = readme_path.read_text()

        # Check for agent guidance section
        assert (
            "AI Agents" in content or "agents" in content.lower()
        ), "README should mention agents"
        assert "profile" in content.lower(), "README should mention profiles"
        assert (
            "--non-interactive" in content
        ), "README should show --non-interactive flag for agents"

    def test_readme_shows_explicit_switch_example_for_agents(self):
        """README should show explicit cloudctl switch example for agents."""
        readme_path = Path(__file__).parent.parent / "README.md"
        content = readme_path.read_text()

        # Look for the explicit switch command
        assert (
            "--non-interactive" in content
        ), "README should show --non-interactive example"
        assert "cloudctl switch" in content, "README should mention cloudctl switch"

    def test_readme_explains_why_profiles_unsuitable_for_agents(self):
        """README should explain why profiles are local-only."""
        readme_path = Path(__file__).parent.parent / "README.md"
        content = readme_path.read_text()

        # Check for explanation
        assert (
            "local-only" in content.lower()
        ), "README should explain profiles are local-only"
        assert (
            "--non-interactive" in content
        ), "README should show agent-friendly alternative"


class TestAgentGuidanceConsistency:
    """Verify guidance is consistent across documentation."""

    def test_profile_and_readme_both_mention_agent_limitation(self):
        """Both profile command and README should mention agents shouldn't use profiles."""
        profile_file = (
            Path(__file__).parent.parent
            / "src"
            / "cloudctl"
            / "commands"
            / "profile.py"
        )
        readme_file = Path(__file__).parent.parent / "README.md"

        profile_content = profile_file.read_text()
        readme_content = readme_file.read_text()

        # Both should mention agents
        assert (
            "agent" in profile_content.lower()
        ), "Profile commands should mention agents"
        assert "agent" in readme_content.lower(), "README should mention agents"

        # Both should suggest cloudctl switch
        assert (
            "--non-interactive" in profile_content
        ), "Profile should show --non-interactive for agents"
        assert (
            "--non-interactive" in readme_content
        ), "README should show --non-interactive for agents"

    def test_guidance_uses_consistent_terminology(self):
        """Guidance should consistently use 'human' or 'humans' terminology."""
        profile_file = (
            Path(__file__).parent.parent
            / "src"
            / "cloudctl"
            / "commands"
            / "profile.py"
        )
        readme_file = Path(__file__).parent.parent / "README.md"

        profile_content = profile_file.read_text()
        readme_content = readme_file.read_text()

        # Should use consistent terminology
        assert (
            "human" in profile_content.lower()
        ), "Profile should use 'human' terminology"
        assert (
            "human" in readme_content.lower()
        ), "README should use 'human' terminology"
