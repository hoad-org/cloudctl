#!/bin/bash

SECURITY_PATTERNS=(
  "validateToken"
  "validateJWT"
  "checkExpiry"
  "isExpired"
  "verifySignature"
  "verifyAuth"
  "authenticate"
  "authorize"
  "encryptPassword"
  "hashPassword"
  "validateInput"
  "sanitize"
  "escapeSQL"
  "HTTPS"
  "TLS"
  "SSL"
  "csrf"
  "xss"
  "sqlInjection"
)

echo "🔒 Checking for security pattern removal..."

for pattern in "${SECURITY_PATTERNS[@]}"; do
  if git diff --cached | grep -q "^-.*${pattern}"; then
    echo "❌ PERMANENT BLOCK: Security pattern removal detected"
    echo ""
    echo "Pattern found: $pattern"
    echo ""
    echo "Security features cannot be deleted. Instead:"
    echo "  1. KEEP the validation logic"
    echo "  2. REFACTOR for clarity"
    echo "  3. CREATE an ADR explaining decision"
    echo "  4. GET security review before changes"
    echo ""
    exit 2
  fi
done

exit 0
