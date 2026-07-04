"""Approval workflow client for skill operations.

Handles approval requests, polling, and status tracking.
Currently uses mock implementation; ServiceNow integration in post-launch.
"""

import time
import uuid
from datetime import datetime, timezone


class ApprovalClient:
    """Client for requesting and polling approval status.

    Mock implementation for Phase 2-3. Real ServiceNow integration in v4.1.0.
    """

    # Mock storage for approval requests (in-memory for now)
    _approvals = {}

    def __init__(self):
        """Initialize approval client."""
        pass

    def request_approval(
        self,
        skill: str,
        operation: str,
        org: str,
        role: str,
        reason: str,
        num_approvers: int = 1,
    ) -> str:
        """Request approval for a skill operation.

        Args:
            skill: Skill name (e.g., "cloudctl:switch", "cloudctl:exec")
            operation: Operation name (e.g., "login", "switch", "exec")
            org: Organization name
            role: Role being accessed
            reason: Human-readable reason for the operation
            num_approvers: Number of approvers required

        Returns:
            Approval ID (string) that can be used to poll status

        Raises:
            Exception: If approval request fails
        """
        approval_id = f"APPR-{uuid.uuid4().hex[:8].upper()}"

        # Mock: Create approval request
        self._approvals[approval_id] = {
            "id": approval_id,
            "skill": skill,
            "operation": operation,
            "org": org,
            "role": role,
            "reason": reason,
            "num_approvers": num_approvers,
            "requested_at": datetime.now(timezone.utc),
            "status": "pending",  # pending | approved | rejected
            "approver": None,
            "approval_time": None,
            "rejection_reason": None,
        }

        # TODO: Send approval request to ServiceNow
        # Mock: Print to stdout so developer can approve manually in tests
        print(f"\n🔔 APPROVAL REQUIRED: {approval_id}")
        print(f"   Operation: {skill}.{operation}")
        print(f"   Org: {org}, Role: {role}")
        print(f"   Reason: {reason}")
        print(f"   Approvers needed: {num_approvers}")
        print("   (Mock: Auto-approve in tests; real approval in ServiceNow v4.1.0)")

        return approval_id

    def poll_approval(self, approval_id: str, timeout: int = 300) -> bool:
        """Poll approval status until approved, rejected, or timeout.

        Args:
            approval_id: Approval ID from request_approval()
            timeout: Max seconds to wait for approval

        Returns:
            True if approved, False if rejected or timed out

        Raises:
            KeyError: If approval_id not found
        """
        if approval_id not in self._approvals:
            raise KeyError(f"Approval not found: {approval_id}")

        approval = self._approvals[approval_id]
        start_time = time.time()

        while True:
            # Check elapsed time
            if time.time() - start_time > timeout:
                approval["status"] = "timeout"
                return False

            # Check approval status
            status = approval["status"]
            if status == "approved":
                return True
            elif status == "rejected":
                return False
            elif status == "timeout":
                return False

            # Mock: For testing, auto-approve after 0.1 seconds
            # In real ServiceNow, this would check the API
            if time.time() - start_time > 0.1 and approval["status"] == "pending":
                approval["status"] = "approved"
                approval["approver"] = "test-approver@beyondtrust.com"
                approval["approval_time"] = datetime.now(timezone.utc)
                return True

            # Poll every 100ms
            time.sleep(0.1)

    def get_approval_status(self, approval_id: str) -> dict:
        """Get current status of an approval request.

        Args:
            approval_id: Approval ID from request_approval()

        Returns:
            {
                "status": "pending" | "approved" | "rejected" | "timeout",
                "approver": "email@beyondtrust.com" | None,
                "approval_time": "2026-04-24T14:30:00Z" | None,
                "rejection_reason": "..." | None,
            }

        Raises:
            KeyError: If approval_id not found
        """
        if approval_id not in self._approvals:
            raise KeyError(f"Approval not found: {approval_id}")

        approval = self._approvals[approval_id]

        return {
            "status": approval["status"],
            "approver": approval["approver"],
            "approval_time": (
                approval["approval_time"].isoformat()
                if approval["approval_time"]
                else None
            ),
            "rejection_reason": approval["rejection_reason"],
        }

    def reject_approval(self, approval_id: str, reason: str) -> None:
        """Reject an approval request.

        Args:
            approval_id: Approval ID to reject
            reason: Rejection reason

        Raises:
            KeyError: If approval_id not found
        """
        if approval_id not in self._approvals:
            raise KeyError(f"Approval not found: {approval_id}")

        approval = self._approvals[approval_id]
        approval["status"] = "rejected"
        approval["rejection_reason"] = reason
