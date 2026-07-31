# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the dashboard read families, answered by owners.

Every name here is a query owner's own object, so a call made through this hub
runs the SQL, the projections, and the short circuits those families are
maintained by -- the three skill reads and the four breakdowns beside them
alike. The underscored ones are the projections and the cost reading this hub
published while it owned them, bound to the owner's object rather than
re-derived, and the two row caps are the owners' constants rather than a second
copy of the number a signature already defaults to.
"""

from __future__ import annotations

from orchestrator.observability.analytics.query.backend_tokens import (
    backend_daily_token_rows as _backend_daily_token_rows,
)
from orchestrator.observability.analytics.query.breakdown_reads import (
    get_backend_daily_tokens as get_backend_daily_tokens,
    get_cost_coverage as get_cost_coverage,
    get_hourly_heatmap as get_hourly_heatmap,
    get_review_round_breakdown as get_review_round_breakdown,
)
from orchestrator.observability.analytics.query.cost_coverage import (
    cost_coverage_rows as _cost_coverage_rows,
)
from orchestrator.observability.analytics.query.hourly_heatmaps import (
    hourly_heatmap_rows as _hourly_heatmap_rows,
)
from orchestrator.observability.analytics.query.review_rounds import (
    review_round_rows as _review_round_rows,
)
from orchestrator.observability.analytics.query.row_cells import cost_cell as _cost_cell
from orchestrator.observability.analytics.query.skill_adoption import (
    SKILL_ADOPTION_ROW_LIMIT as SKILL_ADOPTION_ROW_LIMIT,
    skill_adoption_rows as _skill_adoption_rows,
)
from orchestrator.observability.analytics.query.skill_matrices import (
    SKILL_MATRIX_ROW_LIMIT as SKILL_MATRIX_ROW_LIMIT,
    skill_trigger_matrix_rows as _skill_trigger_matrix_rows,
)
from orchestrator.observability.analytics.query.skill_reads import (
    get_skill_adoption as get_skill_adoption,
    get_skill_trigger_matrix as get_skill_trigger_matrix,
    get_skill_trigger_rates as get_skill_trigger_rates,
)
from orchestrator.observability.analytics.query.skill_trigger_rates import (
    skill_trigger_rate_rows as _skill_trigger_rate_rows,
)


_COMPATIBILITY_EXPORTS = (
    SKILL_ADOPTION_ROW_LIMIT,
    SKILL_MATRIX_ROW_LIMIT,
    _backend_daily_token_rows,
    _cost_cell,
    _cost_coverage_rows,
    _hourly_heatmap_rows,
    _review_round_rows,
    _skill_adoption_rows,
    _skill_trigger_matrix_rows,
    _skill_trigger_rate_rows,
    get_backend_daily_tokens,
    get_cost_coverage,
    get_hourly_heatmap,
    get_review_round_breakdown,
    get_skill_adoption,
    get_skill_trigger_matrix,
    get_skill_trigger_rates,
)
