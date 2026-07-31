# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical raw-read import site, answered by the query owners.

The six reads are the owners' own functions, so a call made here runs the SQL,
the ordering, and the short circuits the read families are maintained by. The
underscored names beside them are the projections and coercions this hub
published while it owned them: a private name a caller already imported is
still a name it imported, so each is bound to the owner's object rather than
re-derived here.
"""

from __future__ import annotations

from orchestrator.observability.analytics.query.agent_exits import (
    agent_exit_from_row as _agent_exit_from_row,
    recent_agent_exit_rows as _recent_agent_exit_rows,
)
from orchestrator.observability.analytics.query.event_breakdowns import (
    event_breakdown_rows as _event_breakdown_rows,
)
from orchestrator.observability.analytics.query.filter_options import (
    FILTER_OPTION_COLUMNS as _FILTER_OPTION_COLUMNS,
    filter_options_from_rows as _filter_options_from_rows,
    filter_options_sql as _filter_options_sql,
)
from orchestrator.observability.analytics.query.issue_events import (
    issue_event_from_row as _issue_event_from_row,
    issue_event_rows as _issue_event_rows,
)
from orchestrator.observability.analytics.query.issue_summaries import (
    ISSUE_SORT_BY_OPTIONS as _ISSUE_SORT_BY_OPTIONS,
    SORT_BY_COST as SORT_BY_COST,
    SORT_BY_LAST_SEEN as SORT_BY_LAST_SEEN,
    issue_order_sql as _issue_order_sql,
    issue_summary_from_row as _issue_summary_from_row,
    issue_summary_rows as _issue_summary_rows,
    issues_sql as _issues_sql,
)
from orchestrator.observability.analytics.query.raw_reads import (
    get_data_extent as get_data_extent,
    get_event_breakdown as get_event_breakdown,
    get_filter_options as get_filter_options,
    get_issue_events as get_issue_events,
    get_issues as get_issues,
    get_recent_agent_exits as get_recent_agent_exits,
)
from orchestrator.observability.analytics.query.raw_values import (
    bool_or_none as _bool_or_none,
    empty_filter_selected as _empty_filter_selected,
    float_or_none as _float_or_none,
    int_or_none as _int_or_none,
    row_int as _row_int,
)


_COMPATIBILITY_EXPORTS = (
    _agent_exit_from_row,
    _recent_agent_exit_rows,
    _event_breakdown_rows,
    _FILTER_OPTION_COLUMNS,
    _filter_options_from_rows,
    _filter_options_sql,
    _issue_event_from_row,
    _issue_event_rows,
    _ISSUE_SORT_BY_OPTIONS,
    SORT_BY_COST,
    SORT_BY_LAST_SEEN,
    _issue_order_sql,
    _issue_summary_from_row,
    _issue_summary_rows,
    _issues_sql,
    get_data_extent,
    get_event_breakdown,
    get_filter_options,
    get_issue_events,
    get_issues,
    get_recent_agent_exits,
    _bool_or_none,
    _empty_filter_selected,
    _float_or_none,
    _int_or_none,
    _row_int,
)
