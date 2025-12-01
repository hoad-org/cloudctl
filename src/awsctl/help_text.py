# file: src/awsctl/help_text.py
# SPDX-License-Identifier: MIT
"""
Help text definitions using Markdown for Rich rendering.
"""

HELP_MARKDOWN = """
# awsctl: Enterprise AWS Context Switcher (v2.0.0)

**awsctl** is your copilot for AWS Identity Center (SSO).

---

## 🔐 Authentication & Context

* `awsctl login`        : Authenticate to your Organization.
* `awsctl switch`       : **Interactive Context Switcher** (Account + Role).
* `awsctl switch -`     : Toggle back to previous context.
* `awsctl logout`       : Clear cached tokens and shell variables.

## 🛠 Utilities

* `awsctl exec`         : Run a command in a target account (one-shot).
* `awsctl env`          : Print current exported variables to stdout.
* `awsctl console`      : Open AWS Console in browser.

## 🔍 Discovery & Status

* `awsctl status`       : View current identity and token health.
* `awsctl list`         : Explore Org, Accounts, or Roles.
* `awsctl doctor`       : System diagnostics.

## ⚙️ System

* `awsctl setup`        : Run the configuration wizard.
* `awsctl cache-clear`  : Force refresh of account lists.

**Global Flags:**
* `--debug`             : Enable verbose logging to stderr.

For full details, see `docs/USER_GUIDE.md`.
"""
