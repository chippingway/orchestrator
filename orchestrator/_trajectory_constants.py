# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the record vocabulary, answered by its owner.

The seven names are the owner's own constants, so the event a line is read for,
the brackets a run is wrapped in, the tells that mark a fixture, and the banner
an unconfigured sink answers with read the same whichever module a caller
names.
"""

from __future__ import annotations

from orchestrator.observability.trajectory_viewer import constants


TRAJECTORY_EVENT = constants.TRAJECTORY_EVENT
TIMELINE_PROMPT = constants.TIMELINE_PROMPT
TIMELINE_OUTPUT = constants.TIMELINE_OUTPUT
FIXTURE_PROMPT = constants.FIXTURE_PROMPT
FIXTURE_SESSION_PREFIX = constants.FIXTURE_SESSION_PREFIX
FIXTURE_SKILL_TOOL = constants.FIXTURE_SKILL_TOOL
UNCONFIGURED_LOG_MESSAGE = constants.UNCONFIGURED_LOG_MESSAGE
