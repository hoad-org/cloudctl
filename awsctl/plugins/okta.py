# file: awsctl/plugins/okta.py
"""
Okta plugin scaffold.

Goal:
- Prepare or validate Okta-side state before awsctl triggers AWS SSO login.
- Where allowed, reduce manual steps but do not bypass provider-required browser consent.

Future ideas:
- Device code flow hints
- Pre-check enrolled factors
"""

from awsctl.utils import info, warn


def pre_login(org: dict) -> None:
    info("Okta plugin: pre-login checks starting")
    # Example: verify org has expected keys for Okta-integrated SSO
    if "sso_start_url" not in org:
        warn("Okta plugin: org missing sso_start_url; nothing to do")
