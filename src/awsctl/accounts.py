# file: src/awsctl/accounts.py
# SPDX-License-Identifier: MIT
"""
awsctl.accounts
---------------
Domain logic for AWS Account and Role retrieval.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from awsctl import aws
from awsctl.sso_cache import OrgRef, load_active_sso_token


@dataclass
class Account:
    account_id: str
    account_name: str
    email: str


def list_accounts(ref: OrgRef) -> List[Account]:
    """
    Retrieve list of accounts for the given organization.
    Uses aws.sso_list_accounts which handles the CLI call and timeouts.
    """
    # [FIX] PYBH-0044: Use raise_error=False to allow checking token validity manually
    token = load_active_sso_token(ref, raise_error=False)
    if not token or not token.access_token:
        # Check specific error message in sso_list_accounts wrapper.
        raise RuntimeError("No active session found. Please run `awsctl login`.")

    # Pass the token explicitly to the AWS CLI wrapper
    raw_list = aws.sso_list_accounts(ref.sso_start_url, ref.sso_region, access_token=token.access_token)

    results = []
    for item in raw_list:
        results.append(
            Account(
                account_id=str(item.get("accountId", "")),
                account_name=str(item.get("accountName", "")),
                email=str(item.get("emailAddress", "")),
            )
        )

    # Sort by name for consistency
    results.sort(key=lambda x: x.account_name)
    return results


def list_roles(ref: OrgRef, account_id: str) -> List[str]:
    """
    Retrieve list of roles for a specific account.
    """
    token = load_active_sso_token(ref, raise_error=False)
    if not token or not token.access_token:
        raise RuntimeError("No active session found. Please run `awsctl login`.")

    roles = aws.sso_list_account_roles(
        ref.sso_start_url,
        account_id,
        ref.sso_region,
        access_token=token.access_token,
    )
    return sorted(roles)
