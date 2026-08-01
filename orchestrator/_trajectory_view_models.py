# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the record's pieces, answered by their owner.

The four frozen views are the owner's own classes -- including the module name
they report and the signatures they are constructed through -- so a caller that
builds a step here and one that builds it on the owner produce the same object.
The field names and the two body accessors travel with them, because the
signatures are declared in terms of the former and the ``content`` property is
installed from the latter.
"""

from __future__ import annotations

from orchestrator.observability.trajectory_viewer import models


KIND_FIELD = models.KIND_FIELD
NAME_FIELD = models.NAME_FIELD
TOOL_ID_FIELD = models.TOOL_ID_FIELD
CONTENT_FIELD = models.CONTENT_FIELD
TURN_FIELD = models.TURN_FIELD
ORIGIN_MODULE = models.ORIGIN_MODULE
STEP_VIEW_SIGNATURE = models.STEP_VIEW_SIGNATURE
TIMELINE_ENTRY_SIGNATURE = models.TIMELINE_ENTRY_SIGNATURE
public_step_content = models.public_step_content
public_entry_content = models.public_entry_content
TrajectoryStepView = models.TrajectoryStepView
TimelineEntry = models.TimelineEntry
TurnUsageView = models.TurnUsageView
RunUsageView = models.RunUsageView
