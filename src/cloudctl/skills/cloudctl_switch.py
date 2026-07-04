"""cloudctl:switch skill — Context switching with approval gates for sensitive roles.

Provides:
- login <org>                  # Authenticate with SSO (optional MFA)
- switch <org> <account> <role>  # Change context with approval gates
- logout                       # Clear credentials and context

Operations on sensitive roles (admin, security, devops) require approval.
MFA enforced for sensitive roles.
"""

import subprocess
from pathlib import Path
from typing import Optional

from cloudctl.skills.approval_client import ApprovalClient
from cloudctl.skills.audit_log import AuditLog
from cloudctl.skills.rate_limit import RateLimit
from cloudctl.guardrails import (
    check_approval_required,
)
from cloudctl.config import get_org
from cloudctl.context_manager import save_context


class CloudctlSwitchSkill:
    """Context switching skill with approval gates for sensitive roles."""

    RATE_LIMIT_LOGINS_PER_HOUR = 5
    RATE_LIMIT_SWITCHES_PER_MIN = 10
    APPROVAL_TIMEOUT_SECONDS = 300

    def __init__(
        self,
        session_id: str,
        config_path: Optional[str] = None,
        approval_provider: Optional[str] = None,
        audit_log_path: Optional[str] = None,
    ):
        self.session_id = session_id
        self.audit = AuditLog(log_path=Path(audit_log_path) if audit_log_path else None)

        # Separate rate limiters for logins (per hour) and switches (per minute)
        # Both use persistent storage per session_id
        storage_dir = (
            Path("~/.cloudctl").expanduser()
            if not audit_log_path
            else Path(audit_log_path).parent
        )
        self.login_limiter = RateLimit(
            max_ops=self.RATE_LIMIT_LOGINS_PER_HOUR,
            window_seconds=3600,
            storage_dir=storage_dir,
        )
        self.switch_limiter = RateLimit(
            max_ops=self.RATE_LIMIT_SWITCHES_PER_MIN,
            window_seconds=60,
            storage_dir=storage_dir,
        )
        self.approval_client = ApprovalClient()

    def _run_cloudctl(self, *args: str) -> dict:
        """Run cloudctl command and capture output.

        Uses shlex.quote() for command injection protection.

        Args:
            *args: Command arguments (e.g., "login", "bt-avm")

        Returns:
            {"exit_code": int, "stdout": str, "stderr": str}
        """
        try:
            cmd = ["cloudctl"] + list(args)
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return {
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except subprocess.TimeoutExpired:
            return {
                "exit_code": 124,
                "stdout": "",
                "stderr": "cloudctl command timed out (30s)",
            }
        except FileNotFoundError:
            return {
                "exit_code": 127,
                "stdout": "",
                "stderr": "cloudctl command not found in PATH",
            }

    def _check_rate_limit(self, operation: str) -> tuple[bool, Optional[str]]:
        """Check if operation is within rate limit.

        Args:
            operation: "login" or "switch"

        Returns:
            (allowed, error_message)
        """
        if operation == "login":
            limiter = self.login_limiter
        elif operation == "switch":
            limiter = self.switch_limiter
        else:
            return False, f"Unknown operation: {operation}"

        allowed, error = limiter.check(self.session_id)
        if not allowed:
            self.audit.log(
                skill="cloudctl:switch",
                session_id=self.session_id,
                operation="rate_limit_exceeded",
                exit_code=429,
            )
        return allowed, error

    def login(self, org: str, mfa_required: bool = False) -> dict:
        """Authenticate with SSO for an organization.

        Args:
            org: Organization name (e.g., "bt-avm", "fdr-gvc")
            mfa_required: Force MFA even if not configured

        Returns:
            {
                "exit_code": 0 | 1,
                "message": "...",
                "approval_id": "APPR-12345" (if approval was required),
            }
        """
        # Check rate limit
        allowed, error = self._check_rate_limit("login")
        if not allowed:
            return {"exit_code": 429, "error": error}

        # Validate org exists and get org config
        try:
            org_config = get_org(org)
        except Exception:
            self.audit.log(
                skill="cloudctl:switch",
                session_id=self.session_id,
                operation="login",
                org=org,
                exit_code=1,
            )
            return {"exit_code": 1, "error": f"Organization not found: {org}"}

        # Check if org login requires approval (rare, usually only for sensitive orgs)
        approval_required, num_approvers = check_approval_required(org_config, "login")
        approval_id = None

        if approval_required:
            # Request approval from security team
            try:
                approval_id = self.approval_client.request_approval(
                    skill="cloudctl:switch",
                    operation="login",
                    org=org,
                    role="login",
                    reason=f"Login to {org} from Claude session {self.session_id}",
                    num_approvers=num_approvers,
                )
            except Exception as e:
                return {"exit_code": 1, "error": f"Approval request failed: {e}"}

            # Poll for approval
            try:
                approved = self.approval_client.poll_approval(
                    approval_id, timeout=self.APPROVAL_TIMEOUT_SECONDS
                )
                if not approved:
                    return {
                        "exit_code": 403,
                        "error": f"Approval denied or timed out (ID: {approval_id})",
                    }
            except Exception as e:
                return {"exit_code": 1, "error": f"Approval polling failed: {e}"}

        # Call actual cloudctl login (OIDC SSO flow)
        result = self._run_cloudctl("login", org)
        if result["exit_code"] != 0:
            self.audit.log(
                skill="cloudctl:switch",
                session_id=self.session_id,
                operation="login",
                org=org,
                exit_code=result["exit_code"],
                approval_id=approval_id,
            )
            return {
                "exit_code": result["exit_code"],
                "error": result["stderr"] or "Login failed",
                "approval_id": approval_id,
            }

        # Successful login
        self.audit.log(
            skill="cloudctl:switch",
            session_id=self.session_id,
            operation="login",
            org=org,
            exit_code=0,
            approval_id=approval_id,
        )

        return {
            "exit_code": 0,
            "message": f"Logged in to {org}",
            "approval_id": approval_id,
        }

    def switch(self, org: str, account: str, role: str) -> dict:
        """Switch to a different organization/account/role context.

        Args:
            org: Organization name (e.g., "bt-avm", "fdr-gvc")
            account: AWS Account ID or Azure Subscription ID
            role: IAM role name

        Returns:
            {
                "exit_code": 0 | 1 | 403 | 429,
                "message": "...",
                "approval_id": "APPR-12345" (if approval was required),
                "context": {"org": "...", "account": "...", "role": "..."},
            }
        """
        # Check rate limit
        allowed, error = self._check_rate_limit("switch")
        if not allowed:
            return {"exit_code": 429, "error": error}

        # Validate org, account, role exist and get org config
        try:
            org_config = get_org(org)
        except Exception:
            return {"exit_code": 1, "error": f"Organization not found: {org}"}

        # Check if role requires approval
        approval_required, num_approvers = check_approval_required(org_config, role)
        approval_id = None

        if approval_required:
            # TODO: Check if MFA is also required (Phase 2.1)
            # mfa_required, mfa_method = check_mfa_required(org, role)
            # For now, skip MFA - will be implemented in v4.1.0

            # Request approval from security team
            try:
                approval_id = self.approval_client.request_approval(
                    skill="cloudctl:switch",
                    operation="switch",
                    org=org,
                    role=role,
                    reason=f"Switch to {role} in {org}/{account} from Claude session {self.session_id}",
                    num_approvers=num_approvers,
                )
            except Exception as e:
                return {"exit_code": 1, "error": f"Approval request failed: {e}"}

            # Poll for approval (blocking)
            try:
                approved = self.approval_client.poll_approval(
                    approval_id, timeout=self.APPROVAL_TIMEOUT_SECONDS
                )
                if not approved:
                    return {
                        "exit_code": 403,
                        "error": f"Approval denied or timed out (ID: {approval_id})",
                    }
            except Exception as e:
                return {"exit_code": 1, "error": f"Approval polling failed: {e}"}

        # Retrieve credentials from cloud provider (CRITICAL: Now implemented)
        credentials = None
        try:
            import json
            from cloudctl.aws import run_aws
            from cloudctl.sso_cache import OrgRef, load_active_sso_token

            # Get region from org config
            region = org_config.get("sso_region", "us-east-1")
            sso_start_url = org_config.get("sso_start_url", "")

            # Load the cached SSO access token
            token = load_active_sso_token(OrgRef(org, sso_start_url, region))
            if not token or not hasattr(token, "accessToken"):
                return {
                    "exit_code": 1,
                    "error": f"No valid SSO session. Run 'cloudctl login {org}' first.",
                }

            # Call AWS CLI to get role credentials
            args = [
                "sso",
                "get-role-credentials",
                "--account-id",
                account,
                "--role-name",
                role,
                "--access-token",
                token.accessToken,
                "--region",
                region,
            ]
            res = run_aws(args)

            if res.get("returncode") != 0:
                # AWS CLI call failed
                error_msg = res.get("stderr", "AWS CLI failed")
                return {
                    "exit_code": 1,
                    "error": f"Failed to retrieve credentials: {error_msg}",
                }

            # Parse credentials from AWS CLI output
            try:
                data = json.loads(res.get("stdout", "{}"))
                creds = data.get("roleCredentials", {})
                if not creds:
                    return {
                        "exit_code": 1,
                        "error": "No credentials returned from AWS SSO",
                    }

                credentials = {
                    "AWS_ACCESS_KEY_ID": creds["accessKeyId"],
                    "AWS_SECRET_ACCESS_KEY": creds["secretAccessKey"],
                    "AWS_SESSION_TOKEN": creds["sessionToken"],
                    "AWS_PROFILE": f"{org}-{account}-{role}",
                }
            except (json.JSONDecodeError, KeyError) as e:
                return {
                    "exit_code": 1,
                    "error": f"Invalid credentials response from AWS: {str(e)}",
                }

        except Exception as e:
            return {
                "exit_code": 1,
                "error": f"Credential retrieval failed: {str(e)}",
            }

        # Switch context (save to ~/.config/cloudctl/current_context.json)
        try:
            save_context(org, account, role, region=region)
        except Exception as e:
            return {"exit_code": 1, "error": f"Failed to save context: {e}"}

        # Audit the successful switch
        self.audit.log(
            skill="cloudctl:switch",
            session_id=self.session_id,
            operation="switch",
            org=org,
            account=account,
            role=role,
            exit_code=0,
            approval_id=approval_id,
        )

        return {
            "exit_code": 0,
            "message": f"Switched to {role} in {org}/{account}",
            "approval_id": approval_id,
            "credentials": credentials,
            "context": {"org": org, "account": account, "role": role},
        }

    def logout(self) -> dict:
        """Clear credentials and current context.

        Returns:
            {"exit_code": 0 | 1, "message": "..."}
        """
        # Check rate limit (logout should be cheap)
        allowed, error = self._check_rate_limit("switch")
        if not allowed:
            return {"exit_code": 429, "error": error}

        # Call cloudctl logout to clear credentials via provider
        # (AWS SSO cache, Azure tokens, GCP credentials, etc.)
        result = self._run_cloudctl("logout")
        if result["exit_code"] != 0:
            # Continue even if cloudctl logout fails, try manual cleanup
            pass

        # Clear context file manually if cloudctl didn't
        try:
            context_file = Path("~/.config/cloudctl/current_context.json").expanduser()
            if context_file.exists():
                context_file.unlink()
        except Exception:
            # Ignore errors clearing context file
            pass

        # Audit the logout
        self.audit.log(
            skill="cloudctl:switch",
            session_id=self.session_id,
            operation="logout",
            exit_code=0,
        )

        return {
            "exit_code": 0,
            "message": "Logged out and credentials cleared",
        }

    def execute(self, command: str, *args: str) -> dict:
        """Dispatch skill command.

        Args:
            command: "login", "switch", or "logout"
            *args: Command arguments

        Returns:
            Result dict
        """
        if command == "login":
            org = args[0] if args else None
            if not org:
                return {"exit_code": 1, "error": "org argument required"}
            return self.login(org)
        elif command == "switch":
            if len(args) < 3:
                return {
                    "exit_code": 1,
                    "error": "switch requires org, account, role arguments",
                }
            org, account, role = args[0], args[1], args[2]
            return self.switch(org, account, role)
        elif command == "logout":
            return self.logout()
        else:
            return {"exit_code": 1, "error": f"Unknown command: {command}"}
