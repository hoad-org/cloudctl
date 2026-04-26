#!/bin/bash

# Automatically update Confluence with any new ADRs created

# Check if ADR was added
NEW_ADRS=$(git diff --cached --name-only | grep "^docs/adr/ADR-.*\.md$")

if [ -z "$NEW_ADRS" ]; then
  exit 0
fi

echo "📋 New ADRs detected. Should sync to Confluence:"
echo "$NEW_ADRS"
echo ""
echo "After commit, run:"
echo "  /confluence-create --title <ADR-title> --space ARCH --body <content>"
echo ""
exit 0
