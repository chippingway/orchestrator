# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the drill-down's typed request and adapter.

Both are the dashboard owner's own objects, published here under the private
spellings the facade always exported them by. A caller that names this module
gets those rather than copies, so the call shape a caller is bound through and
the one the adapter reports stay one description.
"""
from __future__ import annotations

from orchestrator.observability.dashboard import drilldown_request


_DrilldownRequest = drilldown_request.DrilldownRequest
_render_drilldown = drilldown_request.render_drilldown
