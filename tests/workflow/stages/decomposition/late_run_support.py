# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The harness one late adjudication is driven inside.

Narrower than the stage-handler patch set on purpose: the coordinator is not a
dispatched handler and touches exactly two seams, the worktree the frozen
candidate lives in and the tracked spawn. The worktree it is pointed at is a
real directory, because the coordinator refuses to adjudicate a candidate this
host cannot show the agent.

The two recorders are classes rather than closures for the reason the stage
tests' recorders are: what a test is asking about is what pinned state held
INSIDE a side effect, and neither the spawn nor the pull-request edit is
observable from outside the call that makes it.
"""
from __future__ import annotations

import contextlib
import tempfile
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

from orchestrator.agents import runner as _agent_runner
from orchestrator.git.verification.probes import _WorktreeStatus
from orchestrator.workflow.stages.decomposition import (
    late_coordinator as _coordinator,
)

from tests.workflow.fixtures import _TEST_SPEC, _agent
from tests.workflow.git_owners import seam_patch
from tests.workflow.stages.decomposition.late_test_support import (
    CANDIDATE_SHA,
    LATE_ISSUE_NUMBER,
    seeded_late_issue,
)

WORKTREE_NAME = f"issue-{LATE_ISSUE_NUMBER}"


@dataclass(frozen=True)
class WorktreeSeed:
    """What the candidate's worktree answers a late run's probes with.

    The defaults are the only shape a verdict may be read on: the checkout is
    there, HEAD is still the frozen candidate, and the tree is provably clean.
    A test about a read-only agent that wrote says otherwise.
    """

    exists: bool = True
    head: str = CANDIDATE_SHA
    readable: bool = True
    dirty: tuple[str, ...] = ()


def agent_reply(message: str, **result_fields):
    """One finished agent run carrying a late reply."""
    return _agent(last_message=message, **result_fields)


@contextlib.contextmanager
def late_run_context(spawn, seed: WorktreeSeed):
    """Point the coordinator at a real worktree and a mocked spawn."""
    with contextlib.ExitStack() as stack:
        scratch = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        worktree = scratch / WORKTREE_NAME
        if seed.exists:
            worktree.mkdir()
        stack.enter_context(
            seam_patch("_worktree_path", MagicMock(return_value=worktree)),
        )
        stack.enter_context(
            seam_patch("_head_sha", MagicMock(return_value=seed.head)),
        )
        stack.enter_context(seam_patch(
            "_worktree_status",
            MagicMock(return_value=_WorktreeStatus(
                readable=seed.readable, paths=tuple(seed.dirty),
            )),
        ))
        stack.enter_context(patch.object(_agent_runner, "run_agent", spawn))
        yield


def adjudicate(github, issue, agent_result=None, *, worktree=None):
    """Run one late adjudication and report the spawn it went through."""
    if callable(agent_result):
        spawn = MagicMock(side_effect=agent_result)
    else:
        spawn = MagicMock(return_value=agent_result)
    with late_run_context(spawn, worktree or WorktreeSeed()):
        outcome = _coordinator._adjudicate_late_generation(
            github, _TEST_SPEC, issue, github.read_pinned_state(issue),
        )
    return outcome, spawn


class SpawnSnapshot:
    """What pinned state held at the moment the agent was started.

    The persist-before-spawn order is only visible from inside the spawn: a
    record written afterwards would still be there by the time a test looked.
    """

    def __init__(self, github, agent_result) -> None:
        self.snapshots: list[dict] = []
        self._github = github
        self._agent_result = agent_result

    def __call__(self, *_args, **_kwargs):
        self.snapshots.append(self._github.pinned_data(LATE_ISSUE_NUMBER))
        return self._agent_result


class HoldSnapshot:
    """What pinned state held each time the plan PR body was rewritten."""

    def __init__(self, github) -> None:
        self.snapshots: list[dict] = []
        self._github = github
        self._edit = github.edit_pr_body

    def __call__(self, pr, body):
        self.snapshots.append(self._github.pinned_data(LATE_ISSUE_NUMBER))
        return self._edit(pr, body)


class LateCase:
    """One late issue on a fake client, and the coordinator run over it."""

    def setUp(self) -> None:
        github, issue = seeded_late_issue()
        self.github = github
        self.issue = issue

    def _adjudicate(self, agent_result=None, *, worktree=None):
        return adjudicate(
            self.github, self.issue, agent_result, worktree=worktree,
        )

    def _pinned(self) -> dict:
        return self.github.pinned_data(LATE_ISSUE_NUMBER)

    def _events_named(self, family: str) -> list[dict]:
        return [
            record for record in self.github.recorded_events
            if record.get("event") == family
        ]
