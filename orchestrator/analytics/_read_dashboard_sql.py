# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the finished-run condition, answered by its owner.

The name is the splice owner's own constant, so a scan narrowing to completed
agent runs pins the same event the exclusion probe beside it tests for.
"""

from __future__ import annotations

from orchestrator.observability.analytics.query.conditions import (
    AGENT_EXIT_CONDITION as _AGENT_EXIT_CONDITION,
)

_COMPATIBILITY_EXPORTS = (_AGENT_EXIT_CONDITION,)
