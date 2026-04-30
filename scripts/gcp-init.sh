#!/bin/bash
# gcp-init.sh — Complete GCP setup: authenticate, detect success, grant org IAM roles
#
# Usage:
#   ./scripts/gcp-init.sh <org-id> <email> [role1] [role2] ...
#
# Example:
#   ./scripts/gcp-init.sh 1045595480395 admin@craighoad.com projectCreator folderCreator billing.projectManager folderIamAdmin

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Validate arguments
if [ $# -lt 2 ]; then
    echo "Usage: $0 <org-id> <email> [role1] [role2] ..."
    echo ""
    echo "Example: $0 1045595480395 admin@craighoad.com projectCreator folderCreator billing.projectManager folderIamAdmin"
    exit 1
fi

ORG_ID="$1"
EMAIL="$2"
shift 2
ROLES=("$@")

if [ ${#ROLES[@]} -eq 0 ]; then
    ROLES=("projectCreator" "folderCreator" "billing.projectManager" "folderIamAdmin")
fi

echo -e "${CYAN}================================================${NC}"
echo -e "${CYAN}GCP Setup: Authentication + IAM Role Grant${NC}"
echo -e "${CYAN}================================================${NC}"
echo ""
echo -e "${YELLOW}Organization ID:${NC} $ORG_ID"
echo -e "${YELLOW}Email:${NC} $EMAIL"
echo -e "${YELLOW}Roles:${NC} ${ROLES[*]}"
echo ""

# Step 1: Authenticate
echo -e "${CYAN}Step 1: Authenticate with GCP${NC}"
echo -e "${YELLOW}Browser will open automatically...${NC}"
echo ""

if ! python -m cloudctl gcp login --account "$EMAIL"; then
    echo -e "${RED}❌ Authentication failed${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✅ Authentication successful${NC}"
echo ""

# Step 2: Verify authentication
echo -e "${CYAN}Step 2: Verifying authentication...${NC}"
if ! gcloud auth print-access-token > /dev/null 2>&1; then
    echo -e "${RED}❌ Token verification failed${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Access token confirmed${NC}"
echo ""

# Step 3: Grant IAM roles
echo -e "${CYAN}Step 3: Granting organization-level IAM roles${NC}"
echo -e "${YELLOW}Granting roles:${NC} ${ROLES[*]}"
echo ""

if ! python -m cloudctl gcp grant-iam-roles "$ORG_ID" "$EMAIL" "${ROLES[@]}"; then
    echo -e "${RED}❌ Role grant failed${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✅ All done!${NC}"
echo ""
echo -e "${CYAN}================================================${NC}"
echo -e "${CYAN}GCP Setup Complete${NC}"
echo -e "${CYAN}================================================${NC}"
echo ""
echo -e "${YELLOW}You can now:${NC}"
echo -e "${CYAN}  • Deploy Phase 0 Terraform${NC}"
echo -e "${CYAN}  • Create GCP projects${NC}"
echo -e "${CYAN}  • Manage organization folders and IAM${NC}"
echo ""
