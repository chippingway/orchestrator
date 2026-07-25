# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Local-verification domain owners.

The `VerifyResult` model and the output budget its `output` field is sized
to live in ``models``; the HEAD and dirty-file probes that classify a
worktree after one verify command live in ``probes``. Callers import the
owner they need directly, so this initializer binds nothing and importing
one owner never drags the other in. ``orchestrator.verify`` stays the
historical facade for callers that reach these helpers through the workflow
compatibility surface.
"""
