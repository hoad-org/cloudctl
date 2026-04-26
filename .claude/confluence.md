# Confluence Skill Configuration

This repository is configured to use the Confluence skill for documentation.

## Configuration
- **Confluence Space**: `Hoad-cloud-platforms`
- **Jira Project**: `HCP`
- **Instance**: darkmothcreative.atlassian.net

## Usage

When using the Confluence skill in this repository, always:

1. Use the Confluence skill (Claude has it available)
2. Pass `repo_path: "."` to bind to this repository's `.confluence.yaml`
3. Documentation will automatically go to the `Hoad-cloud-platforms` space
4. Jira issues will be linked to the `HCP` project

Example usage:

```python
from skills.confluence import ConfluenceSkill
from skills.confluence.models import SkillConfig

skill = ConfluenceSkill(config)
result = skill.document(
    task="Document the payment API",
    repo_path=".",  # Uses .confluence.yaml from this repo
    dry_run=False
)
```

## Key Instructions for Claude

- **Always use the Confluence skill** when documenting code or generating docs
- **Always pass `repo_path="."** to load this repository's configuration
- The space `Hoad-cloud-platforms` is the target for all generated documentation
- The project `HCP` will be used for Jira integration

## Documentation Triggers

Generate documentation for:
- New API endpoints
- Architecture decisions (ADR)
- Runbooks and operational guides
- Infrastructure changes
- Infrastructure templates
- Feature specifications
- Troubleshooting guides

The Confluence skill will handle:
- Creating/updating pages in the correct space
- Linking related Jira issues
- Creating tasks for undocumented APIs
- Validating inputs and permissions
