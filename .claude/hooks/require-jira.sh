#!/bin/bash

# MANDATORY: Issues tracked in Jira, not TODO comments
# All TODO/FIXME must reference a Jira ticket

echo "🎫 Checking for untracked issues (TODO/FIXME without Jira refs)..."

TODO_FOUND=0

# Check for TODO/FIXME in staged files
if git diff --cached | grep -E "TODO|FIXME" > /tmp/todos.txt 2>/dev/null; then
  TODO_FOUND=1
fi

if [ "$TODO_FOUND" -eq 1 ]; then
  # Check if any TODO has a Jira reference (e.g., TODO(PROJ-123))
  if grep -E "TODO.*\([A-Z]+-[0-9]+\)|FIXME.*\([A-Z]+-[0-9]+\)" /tmp/todos.txt > /dev/null 2>&1; then
    echo "✅ Found Jira references in TODOs"
  else
    echo "⚠️  TODO/FIXME comments found without Jira references"
    echo ""
    echo "MANDATORY: Link all TODOs to Jira tickets"
    echo ""
    echo "Examples:"
    echo "  ❌ TODO: Fix database connection timeout"
    echo "  ✅ TODO(PROJ-123): Fix database connection timeout"
    echo ""
    echo "SOLUTION:"
    echo "  1. Create Jira issue: /jira-create --project PROJ --type Bug --summary '...' "
    echo "  2. Get the issue key (e.g., PROJ-123)"
    echo "  3. Add to comment: TODO(PROJ-123): ..."
    echo ""
    exit 1
  fi
fi

exit 0
