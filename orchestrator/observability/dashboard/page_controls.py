# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The top of the page, and the load the choices made there open.

Everything an operator narrows a run of the analytics page with is decided
here, in one pass, before the first read is issued: the sidebar the rows are
picked in, the zone their timestamps are read against, the bar the days are
picked in, and the staged plan the panels below are then drawn from. Keeping
the narrowing and the staging in one owner is what makes them one description
-- the selections are normalized into the filters every shape carries, those
filters are hashed into the pair of cache keys the two waves are bound to, and
nothing in between can narrow one without narrowing the other.

The sidebar and the bar answer different questions about the same window --
which rows it holds, and which days -- so the selections come back raw and are
normalized in a single place afterwards. Three of those normalizations are the
point of it. ``All`` in the repository box is the absence of a repository
rather than a repository named ``All``. The two multiselects are read
asymmetrically, and by column rather than by preference: an event is recorded
on every row, so that selection maps straight through and a box still holding
everything narrows nothing, while a stage is optional and the box offers only
the stages actually recorded -- so a stage selection still holding everything
collapses to no clause at all, which is what keeps the rows carrying no stage
inside the window a default page reports. Clearing either box is the clause
matching nothing rather than the absence of one, since an operator who unticked
every value is asking for exactly that. The issue box is free text, so ``123``
and ``#123`` are the same number and anything else is no number.

The slot the topbar is written into is taken between the two. The banner above
the filter line reports counts the first wave has not answered yet, so the
page holds a placeholder for it here and writes it once those reads come back.

The zone is the one selection this owner does not draw. The card that offers it
sits at the foot of the page while the read it changes is bound at the top, so
it travels through the session: seeded on the first render, read back on every
one after, and passed beside the cache key rather than inside it, since an
offset moves which cell a row is counted into rather than which rows the window
holds.

The clock a load is measured against is stamped as the plan is built rather
than inside the dispatch that runs it. Nothing has been read by then, so the
reading still covers every wave an operator waits through -- and the one path
that skips that dispatch, the notice an empty window is answered with, has a
reading to report its own load off.

Streamlit is the caller's, reached through the modules shape rather than
imported, so this owner stays testable without the optional dependency group.
"""
from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Sequence

from orchestrator.observability.dashboard import (
    date_filter,
    filters,
    page_models,
    read_mode,
    read_plan,
    windows,
)


SIDEBAR_HEADER = "Filters"

# The repository box's first option, and the one value it answers with that
# names no repository. It is offered even where the database holds none, so the
# box reads as a filter set to everything rather than as a broken control.
ALL_REPOS = "All"

EVENT_FILTER_HELP = (
    "Narrows every widget. An empty selection means "
    "'show nothing for these events'."
)

STAGE_FILTER_HELP = (
    "Narrows every widget. An empty selection means "
    "'show nothing for these stages'."
)

ISSUE_FILTER_HELP = (
    "Enter `123` or `#123` to narrow every widget to one "
    "issue AND render the per-issue event trace at the "
    "bottom. Requires a specific repo above."
)


@dataclass(frozen=True)
class SidebarSelections:
    repo: str
    events: Sequence[str]
    stages: Sequence[str]
    issue_input: str


def render_sidebar_filters(*, st: Any, options: Any) -> SidebarSelections:
    """Render sidebar filters and return their unresolved selections."""
    with st.sidebar:
        st.header(SIDEBAR_HEADER)
        repo_options = (ALL_REPOS,)
        if options.repos:
            repo_options = (ALL_REPOS, *options.repos)
        repo_choice = st.selectbox("Repo", repo_options, index=0)
        event_choice = st.multiselect(
            "Events",
            list(options.events),
            default=list(options.events),
            help=EVENT_FILTER_HELP,
        )
        stage_choice = st.multiselect(
            "Stages",
            list(options.stages),
            default=list(options.stages),
            help=STAGE_FILTER_HELP,
        )
        issue_input = st.text_input(
            "Issue number",
            value="",
            help=ISSUE_FILTER_HELP,
        )
    return SidebarSelections(
        repo=repo_choice,
        events=event_choice,
        stages=stage_choice,
        issue_input=issue_input,
    )


def timezone_choice(st: Any) -> int:
    """Report the offset a run is displayed in, seeding it on first render."""
    # The selectbox inside the activity card writes this key, so the seeding
    # here is only ever the first render's -- and a page opened on a zone
    # nobody has picked yet still reads its hours in one.
    if "tz_offset_hours" not in st.session_state:
        st.session_state.tz_offset_hours = filters.DEFAULT_TZ_OFFSET_HOURS
    return int(st.session_state.tz_offset_hours)


def resolve_dashboard_filters(
    window: windows.DateWindow,
    selections: SidebarSelections,
    options: Any,
) -> page_models.DashboardFilters:
    """Normalize one sidebar pass into what every read is narrowed by."""
    repo = None
    if selections.repo != ALL_REPOS:
        repo = selections.repo
    return page_models.DashboardFilters(
        window=window,
        repo=repo,
        issue_input=filters.parse_issue_number(selections.issue_input),
        events=list(selections.events),
        stages=filters.resolve_stage_filter(
            selections.stages,
            options.stages,
        ),
    )


def render_dashboard_controls(
    modules: page_models.DashboardModules,
    extent: Any,
    options: Any,
) -> page_models.DashboardControls:
    """Draw the sidebar and the filter bar, and read both back as controls."""
    selections = render_sidebar_filters(st=modules.st, options=options)
    timezone_offset = timezone_choice(modules.st)
    topbar_slot = modules.st.empty()
    window_meta = date_filter.render_date_filter_bar(
        st=modules.st,
        extent=extent,
        extent_min_d=extent.min_ts.date(),
        extent_max_d=extent.max_ts.date(),
    )
    return page_models.DashboardControls(
        filters=resolve_dashboard_filters(window_meta[0], selections, options),
        topbar_slot=topbar_slot,
        meta_slot=window_meta[1],
        timezone_offset=timezone_offset,
    )


def prepare_dashboard_page(
    modules: page_models.DashboardModules,
    extent: Any,
    options: Any,
) -> page_models.DashboardPage:
    """Draw those controls, then stage the load the choices narrow."""
    controls = render_dashboard_controls(modules, extent, options)
    keys = read_plan.build_read_keys(
        window=controls.filters.window,
        repo_filter=controls.filters.repo,
        event_filter=controls.filters.events,
        stage_filter=controls.filters.stages,
        issue_filter=controls.filters.issue,
    )
    readers = read_plan.widget_readers(
        st=modules.st,
        key=keys[0],
        prev_key=keys[1],
        tz_offset_choice=controls.timezone_offset,
    )
    return page_models.DashboardPage(
        extent=extent,
        controls=controls,
        reads=read_plan.DashboardReadPlan(
            first_wave=readers[0],
            second_wave=readers[1],
            parallel=read_mode.dashboard_parallel_reads_enabled(),
            started_at=perf_counter(),
        ),
    )
