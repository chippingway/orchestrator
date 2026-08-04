# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the analytics page's own composition.

The entrypoint one run of the page is started from and the five passes it is
drawn by are the canonical app's own functions, published here under the
private spellings the facade always resolved them by. A caller that names this
module gets those rather than copies, so the page an operator launches and the
page a historical caller drives are one run of one composition.
"""
from __future__ import annotations

from orchestrator.apps import analytics_dashboard


main = analytics_dashboard.main
_load_dashboard_modules = analytics_dashboard.load_dashboard_modules
_configure_dashboard = analytics_dashboard.configure_dashboard
_stop_if_dashboard_unconfigured = analytics_dashboard.stop_if_dashboard_unconfigured
_run_dashboard = analytics_dashboard.run_dashboard
_render_dashboard = analytics_dashboard.render_dashboard
