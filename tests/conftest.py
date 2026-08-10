# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Pytest fixtures shared by the whole test suite.

The only fixture here disables the analytics sinks for every test.
`_run_agent_tracked` on `workflow/engine/usage.py` appends a record per
tracked agent run, and the append reads `ANALYTICS_LOG_PATH` off the
analytics `settings` holder at call time; that knob defaults to
`<LOG_DIR>/analytics.jsonl` under the repo root, so any test that drives
a stage handler (directly or via the workflow mixin) would otherwise
scribble into the operator's real log directory. The autouse fixture
below patches the path to `None` (the documented "off" knob) so the
suite is hermetic by default.

The same handler also writes a redacted `agent_trajectory` record to
`TRAJECTORY_LOG_PATH` -- the opt-in trajectory sink. It defaults off
(unset env), but an operator who exported `TRAJECTORY_LOG_PATH` before
running `pytest` would have the resolved path live on that holder, so
every tracked-agent test would scribble trajectories into their real
file. The fixture pins it to `None` too, for the same hermeticity
reason.

Tests that need a sink (e.g. `AgentAnalyticsTest`, the trajectory
recording tests) override the patch inline -- nested `patch.object`
lets the inner temp path win for the duration of its context, then
unwinds back to `None`.

The fixture also puts all six knobs back when the test ends. A test that
re-parses the holder against its own environment reloads it in place, so
the values it lands would otherwise outlive it and decide what the next
test reads.
"""
from __future__ import annotations

from importlib import import_module
from unittest.mock import patch

import pytest

from tests.support.bootstrap import normalize_test_environment

normalize_test_environment()

analytics_settings = import_module(
    "orchestrator.observability.analytics.settings",
)

_KNOBS = (
    "ANALYTICS_DB_URL",
    "ANALYTICS_LOG_PATH",
    "ANALYTICS_RETENTION_DAYS",
    "TRACK_SKILL_TRIGGERS",
    "TRAJECTORY_LOG_PATH",
    "TRAJECTORY_RETENTION_DAYS",
)


@pytest.fixture(autouse=True)
def _disable_analytics_sink():
    entering = {name: getattr(analytics_settings, name) for name in _KNOBS}
    try:
        with patch.object(analytics_settings, "ANALYTICS_LOG_PATH", None), \
                patch.object(analytics_settings, "TRAJECTORY_LOG_PATH", None):
            yield
    finally:
        for name, knob in entering.items():
            setattr(analytics_settings, name, knob)
