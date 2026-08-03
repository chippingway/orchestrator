# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the bar a page picks its window in.

The window a preset opens the bar on, the two pickers an operator overrides it
with, and the bar those are assembled into are the dashboard owner's own
objects. A caller that names this module gets those rather than a copy, so the
window a page reports over and the one the owner resolves cannot come apart.
"""
from __future__ import annotations

from orchestrator.observability.dashboard import date_filter


_initial_filter_window = date_filter.initial_filter_window
_render_date_inputs = date_filter.render_date_inputs
_render_date_filter_bar = date_filter.render_date_filter_bar
