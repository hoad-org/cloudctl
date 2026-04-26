# Project Configuration

## Confluence Integration

This repository is configured for automatic documentation to Confluence.

**Target Space**: `Hoad-cloud-platforms`  
**Jira Project**: `HCP`  
**Instance**: darkmothcreative.atlassian.net

### When to Document

Use the Confluence skill to generate docs for:
- New API endpoints or backend changes
- Architecture decisions (ADR)
- Infrastructure changes or deployments
- Runbooks and operational guides
- Feature specifications
- Troubleshooting guides

### How Claude Should Use the Confluence Skill

**Always**:
1. Use the Confluence skill when user asks to document anything
2. Pass `repo_path="."` to automatically use this repo's configuration
3. Set `dry_run=False` only after user approval

**Example**:
```python
skill.document(
    task="Document the new payment API",
    repo_path=".",
    dry_run=False
)
```

The skill will automatically:
- Create/update pages in the `Hoad-cloud-platforms` space
- Link related issues in the `HCP` Jira project
- Validate all inputs and permissions
- Create tasks for undocumented APIs
