# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The finished developer run the revision tests reconcile.

Two modules read this one: what a resumed developer's worktree becomes, and
what an UNCHANGED commit needs before it may become anything. They share every
fixture -- the locked session, the measurement a re-freeze answers with, and
the four replies a run can end on -- so the replies and the commit they leave
behind stay one description rather than two that drift.

The four replies are the whole point of the split. All of them can leave HEAD
exactly where it was, and only one of them is an answer.
"""
from __future__ import annotations

from types import MappingProxyType

from orchestrator.git.measurement.models import (
    AdditionMeasurement,
    MeasurementFailure,
)

from tests.support.fakes import FakeLabel
from tests.workflow.stages.decomposition.late_content_support import (
    DRIFT_PARKED,
    EDITED_TITLE,
    LateContentCase,
    REVISED_ADDITIONS,
    REVISED_BASE_SHA,
    REVISED_SHA,
    reply,
)
from tests.workflow.stages.decomposition.late_run_support import (
    WorktreeSeed,
    agent_reply,
)
from tests.workflow.stages.decomposition.late_test_support import (
    ADDITIONS,
    CANDIDATE_SHA,
)

DEV_AGENT = "dev_agent"
DEV_SESSION_ID = "dev_session_id"
DEV_SPEC = "claude --effort high"
DEV_SESSION = "dev-sess"

DEV_PIN = MappingProxyType(
    {DEV_AGENT: DEV_SPEC, DEV_SESSION_ID: DEV_SESSION},
)

# The marker the revision prompt asks for, and the three replies that are not
# it: prose that merely sounds like agreement, a question, and silence.
DEV_ACK = "looked again.\n\nACK: the committed work already covers that."

DEV_SOUNDS_LIKE_ACK = "the committed work already covers that, I think."

DEV_QUESTION = "should the migration keep the old column as well?"

DEV_SILENT = ""

NON_ANSWERS = (
    ("prose without the marker", DEV_SOUNDS_LIKE_ACK),
    ("a question", DEV_QUESTION),
    ("no message at all", DEV_SILENT),
)

REMEASURED = AdditionMeasurement(
    base_sha=REVISED_BASE_SHA,
    candidate_sha=REVISED_SHA,
    additions=REVISED_ADDITIONS,
)

# What an unchanged commit measures to: the candidate that went in, re-read
# against a base that may well have moved under it.
ACKNOWLEDGED = AdditionMeasurement(
    base_sha=REVISED_BASE_SHA,
    candidate_sha=CANDIDATE_SHA,
    additions=ADDITIONS,
)

UNMEASURED = AdditionMeasurement(
    base_sha=REVISED_BASE_SHA,
    failure=MeasurementFailure.DIFF_UNPINNABLE,
)

DIRTY_TREE = ("orchestrator/left_over.py",)

PAUSED_LABEL = "paused"

UNCHANGED = WorktreeSeed(head=CANDIDATE_SHA)


class RevisionCase(LateContentCase):
    """A late issue whose next tick reconciles a developer's own worktree."""

    def _seed_drifted(self, *, guided: bool = True) -> None:
        self._seed(**DRIFT_PARKED, **DEV_PIN)
        self.issue.title = EDITED_TITLE
        if guided:
            self.guidance = reply(self.issue)

    def _revise(self, reply=DEV_ACK, seed=None, measurement=REMEASURED):
        return self._run(
            reply, worktree=seed or WorktreeSeed(head=REVISED_SHA),
            measurement=measurement,
        )


class PausedDuringRun:
    """An operator applying `paused` while the developer is still running."""

    def __init__(self, case: RevisionCase) -> None:
        self._case = case

    def __call__(self, *_args, **_kwargs):
        self._case.issue.labels.append(FakeLabel(PAUSED_LABEL))
        return agent_reply(DEV_ACK)
