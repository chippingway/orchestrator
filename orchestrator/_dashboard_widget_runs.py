# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The per-issue drill-down, and the historical site for the list above it.

The recent-run table this module is named for is the dashboard owner's own
object: the expander a window's `agent_exit` rows are listed inside, and the
notice a window with none renders instead. A caller that names this module
gets those rather than a copy, so the listing a page draws and the columns the
owner projects cannot come apart. The per-issue trace beneath the listing is
still built here.
"""
from __future__ import annotations

from orchestrator.analytics import read as analytics_read
from orchestrator import _dashboard_widget_models as models
from orchestrator.observability.dashboard import (
    filter_binding,
    recent_runs,
    scoped_reads,
)


NO_AGENT_EXITS_MESSAGE = recent_runs.NO_AGENT_EXITS_MESSAGE
_render_recent_runs = recent_runs.render_recent_runs


def _render_drilldown_view(
    modules: models._DashboardModules,
    filters: models._DashboardFilters,
) -> None:
    """Render the per-issue event trace when an issue is selected."""
    if filters.issue_input is None:
        return
    modules.st.subheader(f"Issue #{filters.issue_input} drill-down")
    if filters.repo is None:
        modules.st.info(
            "Pick a specific repo in the sidebar before drilling "
            "into an issue number -- GitHub issue numbers repeat across repos."
        )
        return
    try:
        trace = scoped_reads.scoped_read(
            analytics_read.get_issue_events,
            repo=filters.repo,
            issue=filters.issue_input,
            start=filters.window.start,
            end=filters.window.end,
            events=filter_binding.filter_list(filters.events),
            stages=filter_binding.filter_list(filters.stages),
        )
    except analytics_read.AnalyticsReadError as error:
        modules.st.error(f"Issue drill-down failed: {error}")
        return
    if trace:
        modules.st.dataframe(
            modules.pd.DataFrame(
                [
                    {
                        "ts": event.ts,
                        "event": event.event,
                        "stage": event.stage,
                        "duration (s)": event.duration_s,
                        "result": event.result,
                        "agent": event.agent_role,
                        "backend": event.backend,
                        "exit": event.exit_code,
                        "cost (USD)": event.cost_usd,
                    }
                    for event in trace
                ]
            ),
            use_container_width=True,
        )
    else:
        modules.st.info(
            f"No analytics events recorded for "
            f"`{filters.repo}#{filters.issue_input}` under the current filters."
        )
