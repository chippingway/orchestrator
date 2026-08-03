# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The order the matrix's rows are drawn in, and the click that chose it.

A sort lives in the page URL rather than in session state, so a matrix an
operator sorted survives a rerun and can be handed to someone else as a link.
That makes the query parameters untrusted input: a column the vocabulary no
longer offers, a stale link, or a direction with no column beside it degrades
to the default order rather than raising on a page opened to read a table.

The default is repository ascending, then trigger rate descending, so each
repository's rows lead with the skills its runs actually reached for while the
repositories themselves stay in an order an operator can scan. It is a separate
reading from the per-column one because it orders on two keys at once, which no
single clicked column can express.

The parse takes its argument through a pinned signature so callers keep passing
`params` by that name while the body reads it back off the binding.
"""
from __future__ import annotations

from inspect import Parameter, Signature
from typing import Any, Optional, Sequence

from orchestrator.observability.analytics.query.skill_models import (
    SkillTriggerMatrixRow,
)
from orchestrator.observability.dashboard.skill_matrix_columns import (
    SKILL_MATRIX_DIR_PARAM,
    SKILL_MATRIX_SORT_KEYS,
    SKILL_MATRIX_SORT_PARAM,
)


def parse_skill_matrix_sort(
    *args: Any,
    **kwargs: Any,
) -> tuple[Optional[str], bool]:
    """Resolve the matrix sort key and direction from query parameters."""
    bound = _SORT_SIGNATURE.bind(*args, **kwargs)
    query_params = bound.arguments["params"]
    sort_key = query_params.get(SKILL_MATRIX_SORT_PARAM)
    if sort_key not in SKILL_MATRIX_SORT_KEYS:
        return None, False
    return sort_key, query_params.get(SKILL_MATRIX_DIR_PARAM) == "desc"


_SORT_SIGNATURE = Signature(
    (Parameter("params", Parameter.POSITIONAL_OR_KEYWORD),),
)
parse_skill_matrix_sort.__signature__ = _SORT_SIGNATURE


def sort_skill_matrix_rows(
    rows: Sequence[SkillTriggerMatrixRow],
    sort_key: Optional[str],
    descending: bool,
) -> list[SkillTriggerMatrixRow]:
    """Order the rows by one column, leaving a key nobody offers alone."""
    key_function = SKILL_MATRIX_SORT_KEYS.get(sort_key)
    if key_function is None:
        return list(rows)
    return sorted(rows, key=key_function, reverse=descending)


def default_sort_skill_matrix_rows(
    rows: Sequence[SkillTriggerMatrixRow],
) -> list[SkillTriggerMatrixRow]:
    """Order the rows the way a matrix nobody has sorted opens."""
    return sorted(rows, key=skill_matrix_default_sort_key)


def skill_matrix_default_sort_key(
    row: SkillTriggerMatrixRow,
) -> tuple[str, float]:
    """Repository ascending, then trigger rate descending within it."""
    repo = (row.repo or "").lower()
    rate = -row.rate
    return repo, rate
