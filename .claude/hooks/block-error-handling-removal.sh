#!/bin/bash

echo "🛡️  Checking for error handling removal..."

if git diff --cached | grep -q "^-.*\(err\|Error\)"; then
  if git diff --cached | grep -iE "(database|sql\.|os\.|http\.|json\.|file\.|client\.|net\.)" | grep -q "^-"; then
    echo "⚠️  Error handling removal detected near I/O operation"
    echo ""
    echo "RULE: All I/O operations MUST have error handling."
    echo ""
    exit 2
  fi
fi

exit 0
