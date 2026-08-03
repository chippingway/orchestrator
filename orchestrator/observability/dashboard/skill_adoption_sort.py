# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The order the adoption table's rows are drawn in, and the click that chose it.

A sort lives in the page URL rather than in session state, so a table an
operator sorted survives a rerun and can be handed to someone else as a link.
That makes the query parameters untrusted input: a column the vocabulary no
longer offers, a stale link, or a direction with no column beside it degrades
to the default order rather than raising on a page opened to read a table.

The default is repository ascending, then adoption rate descending, so each
repository's rows lead with the skills its sessions actually loaded while the
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
    SkillAdoptionRow,
)
from orchestrator.observability.dashboard.skill_adoption_columns import (
    SKILL_ADOPTION_DIR_PARAM,
    SKILL_ADOPTION_SORT_KEYS,
    SKILL_ADOPTION_SORT_PARAM,
)


def parse_skill_adoption_sort(
    *args: Any,
    **kwargs: Any,
) -> tuple[Optional[str], bool]:
    """Resolve the adoption sort key and direction from query parameters."""
    bound = _SORT_SIGNATURE.bind(*args, **kwargs)
    query_params = bound.arguments["params"]
    sort_key = query_params.get(SKILL_ADOPTION_SORT_PARAM)
    if sort_key not in SKILL_ADOPTION_SORT_KEYS:
        return None, False
    return sort_key, query_params.get(SKILL_ADOPTION_DIR_PARAM) == "desc"


_SORT_SIGNATURE = Signature(
    (Parameter("params", Parameter.POSITIONAL_OR_KEYWORD),),
)
parse_skill_adoption_sort.__signature__ = _SORT_SIGNATURE


def sort_skill_adoption_rows(
    rows: Sequence[SkillAdoptionRow],
    sort_key: Optional[str],
    descending: bool,
) -> list[SkillAdoptionRow]:
    """Order the rows by one column, leaving a key nobody offers alone."""
    key_function = SKILL_ADOPTION_SORT_KEYS.get(sort_key)
    if key_function is None:
        return list(rows)
    return sorted(rows, key=key_function, reverse=descending)


def default_sort_skill_adoption_rows(
    rows: Sequence[SkillAdoptionRow],
) -> list[SkillAdoptionRow]:
    """Order the rows the way a table nobody has sorted opens."""
    return sorted(rows, key=skill_adoption_default_sort_key)


def skill_adoption_default_sort_key(
    row: SkillAdoptionRow,
) -> tuple[str, float]:
    """Repository ascending, then adoption rate descending within it."""
    repo = (row.repo or "").lower()
    rate = -row.adoption_rate
    return repo, rate
