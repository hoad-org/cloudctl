#!/bin/bash

echo "📋 Checking if ADR required for security changes..."

if git diff --cached | grep -iE "^-.*auth|^-.*encrypt|^-.*validate|^-.*csrf"; then
  if ! ls docs/adr/ADR-*.md 2>/dev/null | grep -qi security; then
    echo "❌ Security pattern change detected without ADR"
    echo ""
    echo "Create: docs/adr/ADR-NNNN-security-change.md"
    echo "Then commit the ADR first, then your changes."
    echo ""
    exit 1
  fi
fi

exit 0
