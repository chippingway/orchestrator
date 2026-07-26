# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Stable workflow surface backed by responsibility-focused lazy leaves.

This initializer carries the whole compatibility facade -- the lazy
``__getattr__`` / ``__dir__`` hooks over the immutable export manifest --
so ``orchestrator.workflow`` itself stays the import site, identity source,
and ``patch.object`` target for every name the manifest inventories. Those
hooks are all it binds. The ``state`` owner beside it holds the label
vocabulary the GitHub and git layers below the engine are typed by, and
importing a submodule runs this initializer first, so anything bound here would
be a cost those layers pay on every import.
"""
from __future__ import annotations

from orchestrator import _workflow_exports

__dir__ = _workflow_exports.exported_dir
__getattr__ = _workflow_exports.resolve_export
