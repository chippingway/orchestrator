# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the staged read dispatch.

The wave dispatch behind a page load, the load line it ends on, the two-wave
run in front of both, the mapping a wave hands back, the message the spinner
over it is opened with, and the logger that line is emitted on are the
dashboard owner's own objects. A caller that names this module -- the hub in
front of it and every historical `dashboard.<name>` import through that hub --
reaches those rather than a copy, so a page and the owner cannot answer a
failed load, or measure a completed one, differently.
"""
from __future__ import annotations

from orchestrator.observability.dashboard import dispatch


LOADING_INDICATOR_MESSAGE = dispatch.LOADING_INDICATOR_MESSAGE
_ReadResults = dispatch.ReadResults
log = dispatch.log
_dispatch_reads = dispatch.dispatch_reads
_log_dashboard_load = dispatch.log_dashboard_load
_run_read_waves = dispatch.run_read_waves
