# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical surface for the decomposition, dependency, and umbrella handlers.

The owners live in :mod:`orchestrator.workflow.stages.decomposition`; every
name here is read back off one of them rather than rebuilt, so both import
sites hand back the same object and a `patch.object` against either is what
the other resolves. Dropped once the callers it serves name the owner instead.
"""
from __future__ import annotations

from orchestrator.stages import _decomposition_exports

__dir__ = _decomposition_exports.exported_dir
__getattr__ = _decomposition_exports.resolve_export
