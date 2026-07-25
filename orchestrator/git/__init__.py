# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Git execution domain owners.

Plain and hardened `git` invocation together with the local
transport-config probe live in ``commands``; the process-local
per-target-root lock registry lives in ``locks``. Callers import the owner
they need directly, so this initializer binds nothing and importing one
owner never drags the other in. ``orchestrator.git_plumbing`` stays the
historical facade for callers that still reach these helpers through the
workflow compatibility surface.
"""
