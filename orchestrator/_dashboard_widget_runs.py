# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the run listing and the trace beneath it.

The expander a window's `agent_exit` rows are listed inside, the notice a
window with none renders instead, and the per-issue trace drawn under both are
the dashboard owners' own objects, published here under the private spellings
the page always imported them by. A caller that names this module gets those
rather than copies, so the listing a page draws and the columns its owner
projects cannot come apart.
"""
from __future__ import annotations

from orchestrator.observability.dashboard import drilldown, recent_runs


NO_AGENT_EXITS_MESSAGE = recent_runs.NO_AGENT_EXITS_MESSAGE
_render_recent_runs = recent_runs.render_recent_runs
_render_drilldown_view = drilldown.render_drilldown_view
