# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the trigger-rate read, answered by its owner.

The three names are the owner's own functions, so the denominator a quiet
cohort still reports against, the key probe that separates a reported load from
an empty one, and the ordering the rows come back in are decided there.
"""

from __future__ import annotations

from orchestrator.observability.analytics.query.skill_trigger_rates import (
    skill_trigger_rate_from_row as _skill_trigger_rate_from_row,
    skill_trigger_rate_rows as _skill_trigger_rate_rows,
    skill_trigger_rate_sql as _skill_trigger_rate_sql,
)

_COMPATIBILITY_EXPORTS = (
    _skill_trigger_rate_from_row,
    _skill_trigger_rate_rows,
    _skill_trigger_rate_sql,
)
