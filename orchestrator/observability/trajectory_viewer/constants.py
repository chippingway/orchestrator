# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What one trajectory record is recognized, bracketed, and dismissed by.

The event name is the only kind of line this viewer reads; every other record
in the sink's JSONL belongs to a producer it does not answer for. The two
timeline kinds are the viewer's own -- a run's prompt and its final output are
fields on the record rather than steps, so the brackets they are rendered as
have no spelling on the write side to agree with. The three fixture tells are
what a record the test suite left in an inherited file carries, and the banner
is what an operator reads instead of an empty table when the sink was never
switched on: the knob to set, the relaunch that makes it take effect, and the
order the two happen in.
"""

TRAJECTORY_EVENT = "agent_trajectory"
TIMELINE_PROMPT = "prompt"
TIMELINE_OUTPUT = "output"
FIXTURE_PROMPT = "ignored"
FIXTURE_SESSION_PREFIX = "sess-"
FIXTURE_SKILL_TOOL = "Skill"
UNCONFIGURED_LOG_MESSAGE = (
    "`TRAJECTORY_LOG_PATH` is not configured. The trajectory sink is "
    "opt-in and default-off, so no trajectories have been recorded. Set "
    "`TRAJECTORY_LOG_PATH=/path/to/trajectories.jsonl` in the environment "
    "and **relaunch** the orchestrator so `record_agent_exit` starts "
    "appending records, then relaunch this viewer."
)
