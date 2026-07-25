# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Local-verification domain owners.

The `VerifyResult` model and the output budget its `output` field is sized
to live in ``models``; the redact-then-truncate pass that fills that field in
``output``; the HEAD and dirty-file probes that classify a worktree after one
verify command in ``probes``; one command's spawn / teardown / drain and the
verdict it earns in ``process``; and the `VERIFY_COMMANDS` sequencing the
validating stage calls in ``runner``. Callers import the owner they need
directly, so this initializer binds nothing and importing one owner never drags
the others in. ``orchestrator.verify`` stays the historical forwarding shell for
callers that reach these helpers through the workflow compatibility surface.
"""
