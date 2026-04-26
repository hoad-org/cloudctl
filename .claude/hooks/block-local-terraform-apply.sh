#!/bin/bash

# Check if this is a terraform apply command
if [[ "$@" == *"apply"* ]] && [[ "$@" != *"plan"* ]]; then
  
  # Allow for local development only
  if [[ -f ".env.local" ]] || [[ "$ENVIRONMENT" == "local" ]]; then
    echo "ℹ️  Local development detected. terraform apply allowed."
    exit 0
  fi
  
  echo "❌ PERMANENT BLOCK: terraform apply cannot run locally"
  echo ""
  echo "Infrastructure changes MUST go through GitHub Actions."
  echo ""
  echo "WHY:"
  echo "  • Audit trail (who approved, when)"
  echo "  • Code review (plan output reviewed in PR)"
  echo "  • CI/CD checks (policy validation, tests)"
  echo "  • Reproducibility (exact same apply every time)"
  echo ""
  echo "REQUIRED WORKFLOW:"
  echo "  1. Update terraform/*.tf"
  echo "  2. git push origin <branch>"
  echo "  3. Create PR"
  echo "  4. GitHub Actions runs 'terraform plan' → shows in PR comments"
  echo "  5. Review plan output in PR"
  echo "  6. Merge to main"
  echo "  7. GitHub Actions runs 'terraform apply' automatically"
  echo ""
  echo "To inspect what would apply (without applying):"
  echo "  terraform plan -out=plan.tfplan"
  echo ""
  exit 2
fi

if [[ "$@" == *"plan"* ]]; then
  exit 0
fi

exit 0
