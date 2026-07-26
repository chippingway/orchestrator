# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Stable workflow surface backed by responsibility-focused lazy leaves.

This initializer carries the whole compatibility facade -- the lazy
``__getattr__`` / ``__dir__`` hooks over the immutable export manifest --
so ``orchestrator.workflow`` itself stays the import site, identity source,
and ``patch.object`` target for every name the manifest inventories.
Nothing here reaches into the ``engine`` subpackage, so an import of this
package costs only the two dependency bindings below.
"""
from __future__ import annotations

from orchestrator import _workflow_dependencies, _workflow_exports

analytics = _workflow_dependencies.analytics
config = _workflow_dependencies.config

__dir__ = _workflow_exports.exported_dir
__getattr__ = _workflow_exports.resolve_export
