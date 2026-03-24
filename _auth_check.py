#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compatibility auth shim.

This project previously performed import-time authorization checks via
`import _auth_check`. The check is intentionally disabled now, but we keep
this module to avoid runtime/import errors for any legacy extension code that
still imports `_auth_check`.
"""

from __future__ import annotations


def check_license() -> bool:
    """Legacy API: always returns True."""
    return True


# Keep side effects empty on import.
AUTH_ENABLED = False
