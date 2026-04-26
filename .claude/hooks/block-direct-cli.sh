#!/bin/bash
set -e

echo "🔍 Checking for direct CLI infrastructure changes..."

if git log -1 --pretty=format:%B 2>/dev/null | grep -iE "(aws|gcloud|kubectl|helm|docker)" >/dev/null 2>&1; then
  STAGED_TF=$(git diff --cached --name-only | grep "\.tf$" | wc -l)
  
  if [ "$STAGED_TF" -eq 0 ]; then
    echo "❌ PERMANENT BLOCK: Infrastructure changes detected without Terraform code"
    echo ""
    echo "Commit message mentions: $(git log -1 --pretty=format:%B | head -1)"
    echo "But no terraform/*.tf files were staged"
    echo ""
    echo "REQUIRED WORKFLOW:"
    echo "  1. Update terraform/*.tf to reflect your intended changes"
    echo "  2. git add terraform/*.tf"
    echo "  3. git commit (will be reviewed in PR)"
    echo "  4. Push to GitHub"
    echo "  5. GitHub Actions: terraform plan → review → terraform apply"
    echo ""
    exit 2
  fi
fi

if git diff --cached --name-only | grep -q "terraform\.tfstate"; then
  echo "❌ PERMANENT BLOCK: Direct terraform.tfstate edit detected"
  echo ""
  echo "Never commit .tfstate directly. Instead:"
  echo "  1. Update terraform/*.tf files"
  echo "  2. Let terraform apply update .tfstate"
  echo "  3. Only commit .tfstate via automated CI/CD"
  echo ""
  exit 2
fi

exit 0
