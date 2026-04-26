#!/bin/bash

# MANDATORY: Documentation in Confluence, not local markdown
# Exceptions: README.md, DEPLOY.md, CHANGELOG.md, CODE_OF_CONDUCT.md

DOCUMENTATION_PATTERNS=(
  "docs/"
  "architecture/"
  "decisions/"
  "runbooks/"
)

ALLOWED_FILES=(
  "README.md"
  "DEPLOY.md"
  "CHANGELOG.md"
  "CODE_OF_CONDUCT.md"
  "CONTRIBUTING.md"
  ".github/"
)

echo "📄 Checking for documentation in local markdown..."

for pattern in "${DOCUMENTATION_PATTERNS[@]}"; do
  MARKDOWN_FILES=$(git diff --cached --name-only | grep "^${pattern}.*\.md$" | wc -l)
  
  if [ "$MARKDOWN_FILES" -gt 0 ]; then
    # Check if it's an exception
    IS_EXCEPTION=0
    for file in $(git diff --cached --name-only | grep "^${pattern}.*\.md$"); do
      for allowed in "${ALLOWED_FILES[@]}"; do
        if [[ "$file" == "$allowed" ]]; then
          IS_EXCEPTION=1
          break
        fi
      done
    done
    
    if [ "$IS_EXCEPTION" -eq 0 ]; then
      echo "⚠️  Documentation files detected in local markdown"
      echo ""
      echo "MANDATORY: Documentation goes in Confluence, not git"
      echo ""
      echo "Pattern detected:"
      git diff --cached --name-only | grep "^${pattern}.*\.md$"
      echo ""
      echo "SOLUTION:"
      echo "  1. Create/update in Confluence instead"
      echo "  2. Use: /confluence-create --title <title> --space <space>"
      echo "  3. Link to Confluence in README.md: [Architecture](https://yourorg.atlassian.net/...)"
      echo "  4. Remove local markdown file from commit"
      echo ""
      exit 1
    fi
  fi
done

exit 0
