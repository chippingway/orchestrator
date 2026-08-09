# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Lazy compatibility hooks for :mod:`orchestrator.analytics`."""

from __future__ import annotations

import importlib
import sys
from types import ModuleType
from typing import Any

from orchestrator.analytics._package_manifest import (
    EXPORTED_NAMES,
    MEMBER_OWNERS,
    MODULE_EXPORTS,
)


def _package_module() -> ModuleType:
    return sys.modules["orchestrator.analytics"]


def resolve_export(export_name: str) -> Any:
    """Answer one historical name off the owner that defines it now.

    Nothing is cached back onto this package: the settings a caller reads here
    are the ones the recorders read, so an access has to reach the owner that
    holds them rather than a copy this package took at its own import.

    `__all__` is answered here rather than assigned in the initializer so this
    package keeps binding nothing at import -- naming it costs an importer
    neither the recorders nor the process configuration behind the knobs.
    """
    if export_name == "__all__":
        return EXPORTED_NAMES
    module_export = MODULE_EXPORTS.get(export_name)
    if module_export is not None:
        return importlib.import_module(module_export)
    owner = MEMBER_OWNERS.get(export_name)
    if owner is None:
        raise AttributeError(
            f"module 'orchestrator.analytics' has no attribute {export_name!r}",
        )
    return getattr(importlib.import_module(owner), export_name)


def exported_dir() -> list[str]:
    """Include lazy analytics compatibility names in package introspection."""
    package_names = set(_package_module().__dict__)
    return sorted(package_names | set(EXPORTED_NAMES) | {"__all__"})


__getattr__ = resolve_export
__dir__ = exported_dir
