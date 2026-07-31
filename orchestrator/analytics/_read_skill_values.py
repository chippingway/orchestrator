# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the skill readings, answered by their owner.

The five names are the owner's own functions, so the JSON payload a name list
is coerced from, the bucket an unrecorded label falls to, and the ranking a
matrix cell is sorted by are each decided once whichever module a caller names.
"""

from __future__ import annotations

from orchestrator.observability.analytics.query.skill_values import (
    as_skill_names as _as_skill_names,
    label_or_unknown as _label_or_unknown,
    row_label as _row_label,
    skill_cohort as _skill_cohort,
    skill_matrix_order_key as _skill_matrix_order_key,
)

_COMPATIBILITY_EXPORTS = (
    _as_skill_names,
    _label_or_unknown,
    _row_label,
    _skill_cohort,
    _skill_matrix_order_key,
)
