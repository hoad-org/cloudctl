# file: src/awsctl/__init__.py
# SPDX-License-Identifier: MIT
"""
awsctl - Enterprise AWS SSO Context Switcher
"""

from __future__ import annotations

# Expose version information
try:
    from ._version import __version__, __version_tuple__
except ImportError:
    __version__ = "0.0.0"
    __version_tuple__ = (0, 0, 0)
