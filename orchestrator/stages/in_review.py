# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical surface for the watermark, feedback, drift, and merge-gate helpers.

The owners live in :mod:`orchestrator.workflow.stages.in_review`; every name
here resolves to the owner's own object rather than a rebuilt one, so a caller
reaching through this module gets the exact function the owners call each other
through.

Identity is all that is forwarded. Each resolved name is cached in this module's
namespace, so a `patch.object` intercepts the lookup site it lands on and not
the other one: patch the owner to intercept orchestrator code, which imports the
owner directly, and the dispatch table, which names the handler owner; patch
here only for a caller that still reads the name off this module. Dropped once
the callers it serves name the owner instead.
"""
from __future__ import annotations

from orchestrator.stages import _in_review_exports

__dir__ = _in_review_exports.exported_dir
__getattr__ = _in_review_exports.resolve_export
