# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Analytics recording owners.

Home of the append side of the analytics sink. The owners divide by what a
record costs to produce: the envelope and the four producer-facing recorders
that write one (``events``), the JSONL line and both sinks' locking under it
(``io``), the typed requests and keyword signatures a call is bound through
(``models``), and the four steps a finished agent run is summarized by --
usage and cost (``usage``), the opt-in skill evidence (``skills``), the
out-of-band Codex capabilities either of those falls back to (``catalog``),
and the order they are composed and written in (``agent_exit``).

This initializer re-exports the narrow public surface (``__all__``): the six
recorders a producer calls -- the envelope builder and the append beneath
them, plus one each for a stage entered, a stage evaluated, a repo's skill
catalog scanned, and a tracked agent run finished. Each is bound here once, at
import, to the owner's own object rather than a wrapper around it. Everything
else -- the typed requests, the parse steps, the JSONL append's arguments --
is reached on its owner, so this package carries no private re-exports.

Where the sink is written, and whether it is written at all, is answered by
the ``config`` owner beside this package rather than here: the read path and
the sync ask the same owner, and a knob has one home. What *is* asked of the
flat ``orchestrator.analytics`` package is which values are in force and where
an interception lands -- ``events.settings_holder`` documents which instance
of it answers.

One finished run's second record -- the opt-in trajectory -- belongs to the
``trajectories`` package beside this one, and ``agent_exit`` calls its
``persistence`` owner directly. That instance travels with it: the settings
holder rides on the exit context, so the gate the write runs behind and the
append that ends it answer for the same instance the baseline record did,
without the sink being reached back through it. The dependency runs one way --
nothing under ``trajectories`` imports these recorders except the sink append
a caller outside a tracked run reaches, which sits above them.

This is the one analytics path the orchestrator process itself runs, and it
runs fail-open inside a tracked agent run, so it stays free of the query,
sync, and page graphs above it.
"""
from orchestrator.observability.analytics.recording import events as _events

__all__ = (
    "append_record",
    "build_record",
    "record_agent_exit",
    "record_repo_skill_catalog",
    "record_stage_enter",
    "record_stage_evaluation",
)

append_record = _events.append_record
build_record = _events.build_record
record_agent_exit = _events.record_agent_exit
record_repo_skill_catalog = _events.record_repo_skill_catalog
record_stage_enter = _events.record_stage_enter
record_stage_evaluation = _events.record_stage_evaluation
