# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What one run of this page settles before anything is drawn.

Three steps, in the order a Streamlit script reaches them. The chrome writes
the stylesheet both pages share first and this page's after it, because the
rules that re-declare the KPI grid for five tiles win the cascade on injection
order rather than on specificity. The refusal is what an install with the sink
switched off gets: the opt-in banner under an empty topbar, so the page still
reads as itself, and then a stop -- falling through would draw an empty table
an operator would read as "nothing ran". The read is one pass over the file,
and the values a dropdown may offer are collected off the runs it returned
rather than declared, so a filter can only offer what some run actually carried.

Which file that is comes off the settings holder a caller hands in, the way
every read of that knob here does: *which* analytics instance answers is the
caller's own question, so a page composed against a reloaded one resolves the
path that one was built for.

The two empty states are worded apart because they are different facts. A file
with no records at all is usually a sink that was switched on but never written
to, so the message names what has to happen for a record to appear; a read that
returned runs the filters then dropped is an operator's own narrowing, so that
one names the way back.
"""

from __future__ import annotations

from typing import Any

from orchestrator.observability.dashboard.css import PAGE_CSS
from orchestrator.observability.trajectory_viewer import (
    filter_values,
    log_paths,
    page_models,
    reading,
    summary_html,
)
from orchestrator.observability.trajectory_viewer.css import EXTRA_CSS


NO_TRAJECTORIES_MESSAGE = (
    "No `agent_trajectory` records were found. The trajectory sink writes "
    "one record per tracked agent run once `TRAJECTORY_LOG_PATH` is set and "
    "the orchestrator has run at least one agent. Confirm the path below and "
    "that some workflow activity has happened since the sink was enabled."
)
EMPTY_FILTER_MESSAGE = (
    "No trajectories match the current filters. Clear a filter or broaden "
    "the search to see recorded runs."
)


def configure_page(st: Any) -> None:
    """Set the page chrome, this page's sheet written after the shared one."""
    st.set_page_config(page_title="Orchestrator Trajectories", layout="wide")
    st.markdown(PAGE_CSS, unsafe_allow_html=True)
    st.markdown(EXTRA_CSS, unsafe_allow_html=True)


def stop_if_unconfigured(st: Any, settings_holder: Any) -> None:
    """Draw the opt-in banner and halt the run where that sink is off."""
    message = log_paths.unconfigured_message(settings_holder)
    if not message:
        return
    st.markdown(summary_html.topbar_html(0, 0), unsafe_allow_html=True)
    st.warning(message)
    st.stop()


def load_trajectory_page(settings_holder: Any) -> page_models._TrajectoryPage:
    """Read that holder's file once, and collect what it offers to filter by."""
    log_path = log_paths.configured_path(settings_holder)
    read_runs = reading.read_trajectories(log_path)
    return page_models._TrajectoryPage(
        log_path=log_path,
        runs=read_runs,
        options=filter_values.filter_options(read_runs),
        fixture_total=sum(1 for run in read_runs if run.is_fixture),
    )
