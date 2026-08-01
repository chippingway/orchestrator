# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The trajectory viewer's `streamlit run` target.

One run of the page in the order the owners under
`observability/trajectory_viewer/` are reached: settle the chrome, refuse an
install whose sink is switched off, read the file once, draw the sidebar and
read it back as one request, narrow the read by it, and hand the survivors to
the page renderer.

Everything the run is composed of is imported inside the entry function, not at
module scope. Streamlit is there because it lives in the optional `dashboard`
group, so importing this module has to work in an install that has none of it;
the domain owners are there because the repo root reaches `sys.path` in the
line above, and under a script launch no `orchestrator.*` name resolves before
that. Which analytics instance answers for the sink's knob is read at call time
for the same reason: a page composed against a reloaded environment resolves
the file that environment was built for.
"""

from __future__ import annotations

if __package__:
    from orchestrator.apps.bootstrap import ensure_repo_root_on_path
else:
    from bootstrap import ensure_repo_root_on_path


ensure_repo_root_on_path(__file__)


def main() -> None:
    """Draw one run of the Streamlit trajectory viewer."""
    import streamlit as st

    from orchestrator import analytics
    from orchestrator.observability.trajectory_viewer import (
        controls,
        page_render,
        page_setup,
    )

    page_setup.configure_page(st)
    page_setup.stop_if_unconfigured(st, analytics)
    page = page_setup.load_trajectory_page(analytics)
    filters = controls.render_trajectory_sidebar(st, page.options)
    page_render.render_trajectory_page(
        st,
        page,
        filters,
        controls.filter_page_runs(page, filters),
    )


if __name__ == "__main__":
    main()
