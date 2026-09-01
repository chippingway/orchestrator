# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The controls a read is narrowed by, and the narrowing they drive.

Drawing the widgets and reading their answers back sit together so that what a
control returns and what the run filter takes are decided in one place. Every
"no clause" spelling is folded here: an unticked multiselect and the *All*
repository choice both become ``None``, because an empty selection handed
through as a filter would answer an operator who narrowed nothing with an empty
table. The issue box takes ``#123`` as readily as ``123``, through the same
parse the analytics page's issue filter is read with, so one spelling works on
both pages.

The fixture toggle is off by default and hides rather than deletes: a
trajectory file inherited from a run with the sink enabled during the test suite
carries synthetic records, and an operator has to be able to see them tagged
before deciding to drop them.

Streamlit is the caller's, handed in rather than imported, so this owner stays
loadable in an install carrying no viewer dependencies at all.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from orchestrator.observability.dashboard.filters import parse_issue_number
from orchestrator.observability.trajectory_viewer import filtering, page_models
from orchestrator.observability.trajectory_viewer.filter_models import FilterOptions
from orchestrator.observability.trajectory_viewer.run_html import REPO_LABEL
from orchestrator.observability.trajectory_viewer.runs import TrajectoryRun


def render_categorical_filters(
    st: Any,
    options: FilterOptions,
) -> tuple[Sequence[str], Sequence[str], Sequence[str]]:
    """Draw the three multiselects, each offered only values a run carried."""
    backends = st.multiselect(
        "Backend",
        list(options.backends),
        help="Leave empty to include every backend.",
    )
    roles = st.multiselect(
        "Agent role",
        list(options.agent_roles),
        help="Leave empty to include every role.",
    )
    stages = st.multiselect(
        "Stage",
        list(options.stages),
        help="Leave empty to include every stage.",
    )
    return backends, roles, stages


def render_text_filters(st: Any) -> tuple[str, str]:
    """Draw the issue box and the free-text search, as typed."""
    issue_input = st.text_input(
        "Issue number",
        value="",
        help="Enter `123` or `#123` to narrow to one issue.",
    )
    query_input = st.text_input(
        "Search",
        value="",
        help=(
            "Case-insensitive substring matched across the prompt, "
            "system prompt, output, tool names, tool payloads, and skill names."
        ),
    )
    return issue_input, query_input


def render_trajectory_sidebar(
    st: Any,
    options: FilterOptions,
) -> page_models._TrajectoryFilters:
    """Draw the whole sidebar and read it back as one filter request."""
    with st.sidebar:
        st.header("Filters")
        repo_choice = st.selectbox(REPO_LABEL, ("All", *options.repos), index=0)
        categorical = render_categorical_filters(st, options)
        text_filters = render_text_filters(st)
        hide_fixtures = st.checkbox(
            "Hide synthetic fixtures",
            value=False,
            help=(
                "Drop records that look like test-suite fixtures -- a "
                "sentinel `ignored` prompt, a `sess-*` session id, or a "
                "Skill-only run. Leave off to keep them, flagged with a "
                "`fixture` tag in the table and run picker."
            ),
        )
    return page_models._TrajectoryFilters(
        repo=None if repo_choice == "All" else repo_choice,
        backends=categorical[0] or None,
        agent_roles=categorical[1] or None,
        stages=categorical[2] or None,
        issue=parse_issue_number(text_filters[0]),
        query=text_filters[1],
        hide_fixtures=hide_fixtures,
    )


def filter_page_runs(
    page: page_models._TrajectoryPage,
    filters: page_models._TrajectoryFilters,
) -> list[TrajectoryRun]:
    """Narrow a read by what the sidebar answered, in the order it was read."""
    return filtering.filter_runs(
        page.runs,
        repo=filters.repo,
        backends=filters.backends,
        agent_roles=filters.agent_roles,
        stages=filters.stages,
        issue=filters.issue,
        query=filters.query,
        exclude_fixtures=filters.hide_fixtures,
    )
