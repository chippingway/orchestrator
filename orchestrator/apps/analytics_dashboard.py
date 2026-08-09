# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The analytics page's `streamlit run` target.

One run of the page in the order the owners under `observability/dashboard/`
are reached: bind the handles every pass draws with, settle the chrome, refuse
an install with no analytics database behind it, read the span and the filter
vocabulary a window is picked from, and -- unless there is no span to pick one
from -- draw the controls, stage the load those choices narrow, and hand the
panels beneath what came back.

Everything the run is composed of is imported inside the pass that reaches it
rather than at module scope. Streamlit, pandas, and the chart builders that
reach Plotly are there because they live in the optional `dashboard` group, so
importing this module has to work in an install carrying none of it; the domain
owners are there because the repo root reaches `sys.path` in the line above,
and under a script launch no `orchestrator.*` name resolves before that.
Deferring the composition is what keeps the two launch orderings the same one,
and it is why importing this module costs the shim and nothing else. The one
owner named at module scope is the shape those passes are annotated in, bound
for a type checker and never at run time; the pass that builds one names it
again inside itself, the way every other owner here is reached.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if __package__:
    from orchestrator.apps.bootstrap import ensure_repo_root_on_path
else:
    from bootstrap import ensure_repo_root_on_path


ensure_repo_root_on_path(__file__)

if TYPE_CHECKING:
    from orchestrator.observability.dashboard.page_models import (
        DashboardModules,
    )


def main() -> None:
    """Draw one run of the Streamlit analytics page."""
    import streamlit as st

    run_dashboard(st)


def load_dashboard_modules(st: Any) -> DashboardModules:
    """Bind the four handles every pass below is handed together."""
    import pandas as pd

    from orchestrator import dashboard_charts, dashboard_theme
    from orchestrator.observability.dashboard.page_models import (
        DashboardModules,
    )

    return DashboardModules(
        st=st,
        pd=pd,
        charts=dashboard_charts,
        theme=dashboard_theme,
    )


def configure_dashboard(modules: DashboardModules) -> None:
    """Settle the page's own chrome before a reading is drawn onto it."""
    modules.st.set_page_config(
        page_title="Orchestrator Analytics",
        layout="wide",
    )
    modules.st.markdown(modules.theme.PAGE_CSS, unsafe_allow_html=True)


def stop_if_dashboard_unconfigured(modules: DashboardModules) -> None:
    """Stop the script where it stands when no database answers for it."""
    # Read through the owner at call time rather than a name bound at this
    # module's import: the URL comes off the analytics settings holder, so a
    # page answers for the target that holder carries now rather than the one
    # this module happened to be imported alongside.
    from orchestrator.observability.dashboard import read_mode

    message = read_mode.db_unconfigured_message()
    if not message:
        return
    modules.st.warning(message)
    modules.st.stop()


def run_dashboard(st: Any) -> None:
    """Open the page on the two reads no filter narrows, and draw it."""
    from orchestrator.observability.dashboard import static_metadata

    modules = load_dashboard_modules(st)
    configure_dashboard(modules)
    stop_if_dashboard_unconfigured(modules)
    render_dashboard(
        modules,
        *static_metadata.read_static_metadata(st=modules.st),
    )


def render_dashboard(
    modules: DashboardModules,
    extent: Any,
    options: Any,
) -> None:
    """Draw the window those two reads allow, or the state that there is none."""
    from orchestrator.observability.dashboard import (
        page_controls,
        page_pipeline,
        page_sections,
        page_states,
    )

    if extent.min_ts is None or extent.max_ts is None:
        page_states.render_no_data(
            st=modules.st,
            extent=extent,
            theme=modules.theme,
        )
        return
    page = page_controls.prepare_dashboard_page(modules, extent, options)
    loaded = page_pipeline.load_dashboard_data(modules, page)
    # A window the first wave answered with no event ends the load there, so
    # there is nothing for the panels beneath to be drawn from.
    if loaded is None:
        return
    page_sections.render_dashboard_widgets(modules, page, loaded)


if __name__ == "__main__":
    main()
