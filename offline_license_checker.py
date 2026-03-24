#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""No-op offline license checker (backward compatibility).

Historically this module validated a `license.key` file and could terminate the
process when invalid. To preserve old call sites while removing authorization
requirements, this module now exposes the same public API but always passes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass
class OfflineLicenseChecker:
    """Backward-compatible checker that always reports valid status."""

    license_file: str = "license.key"

    def read_license_key(self) -> str:
        return ""

    def verify_license(self) -> Tuple[bool, str, int]:
        # (is_valid, message, days_left)
        return True, "license check disabled", 36500

    def check_and_exit(self) -> bool:
        return True


_license_checker: OfflineLicenseChecker | None = None


def init_license_checker() -> OfflineLicenseChecker:
    global _license_checker
    _license_checker = OfflineLicenseChecker()
    return _license_checker


def get_license_days_left(default: int = 36500) -> int:
    if _license_checker is None:
        return default
    _, _, days_left = _license_checker.verify_license()
    return days_left
