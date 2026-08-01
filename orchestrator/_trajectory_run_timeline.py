# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the run's rendering, answered by its owner.

The five functions are the owner's own, and they are the same objects the run
record binds its timeline, fixture flag, labels, and cached turn index to, so
what a page renders and what a filter hides are decided in one place.
"""

from __future__ import annotations

from orchestrator.observability.trajectory_viewer import timeline_views


timeline = timeline_views.timeline
is_fixture = timeline_views.is_fixture
detail_label = timeline_views.detail_label
label = timeline_views.label
turn_map = timeline_views.turn_map
