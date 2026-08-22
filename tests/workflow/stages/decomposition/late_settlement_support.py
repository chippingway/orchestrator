# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The owner reads a finished late run is guarded by, described once.

Two modules read this one: the guard itself, and what a verdict it cleared
becomes. They share the three answers a fresh read can give -- the issue is
open, a human closed it while the agent ran, and GitHub could not be asked --
because each is a race rather than a state a fixture can simply seed: the read
happens INSIDE the call under test, after the spawn it is guarding has already
returned, so what changes the answer has to change it from inside the run.

The three finished runs are module constants because `AgentResult` is frozen
and every one of these tests wants the same one: what differs between them is
what the world does while the run is in flight, not what the run said.

The plan-PR case sits here for the same reason it does in the hold's own
tests: an issue that reached its implementation through a design discussion is
the only one with a description to put back, and both modules ask about it.
"""
from __future__ import annotations

import contextlib
from types import MappingProxyType
from unittest.mock import MagicMock, patch

from orchestrator.workflow.stages.decomposition import late_hold as _late_hold
from orchestrator.workflow.stages.decomposition import late_owner as _late_owner

from tests.support.fakes import FakeGitHubClient
from orchestrator.workflow.stages.decomposition.late_session import (
    MAX_RECORDED_BODY,
)

from tests.workflow.stages.decomposition.late_run_support import (
    LateCase,
    WorktreeSeed,
    agent_reply,
)
from tests.workflow.stages.decomposition.late_test_support import (
    CANDIDATE_SHA,
    KEYS,
    KEY_PLAN_PATH,
    PLAN_PATH,
    PLAN_PR_BODY,
    PLAN_PR_NUMBER,
)
from tests.workflow.stages.decomposition.late_test_support import (
    generation_state,
    late_generation,
    seed_late_issue,
    seed_plan_pr,
)
from tests.workflow.stages.decomposition.late_test_support import (
    NO_BLOCK_REPLY,
    OTHER_SHA,
    QUESTION_REPLY,
    SINGLE_REPLY,
    SPLIT_REPLY,
    late_block,
)

WORKFLOW_LOG = "orchestrator.workflow"

ERROR = "ERROR"

EVENT_LATE_CANCELLATION = "late_cancellation"
EVENT_LATE_SNAPSHOT = "late_snapshot"

PARK_OWNER_UNREADABLE = "late_owner_unreadable"
PARK_HOLD_FAILED = "late_plan_pr_hold_failed"
PARK_QUESTION = "late_question"
PARK_PR_UNRECONCILED = "late_pr_unreconciled"

KEY_LAST_ACTION_COMMENT_ID = "last_action_comment_id"

RECOVERY_FOLLOWUP_MARKER = "<!--orchestrator-late-owner-recovery-->"

RECOVERED_PREFIX = "Recovered automatically:"

NO_ACTION_LINE = "No action needed."

SPLIT_CHILDREN = 2

SINGLE_RUN = agent_reply(SINGLE_REPLY)
SPLIT_RUN = agent_reply(SPLIT_REPLY)
QUESTION_RUN = agent_reply(QUESTION_REPLY)

# The runs that finish without deciding anything. Each parks the issue, and
# each is a completion the guard has to stand in front of all the same: the
# issue paid for the run, and a closure during one of them strands the same
# generation as a closure during a verdict would.
TIMEOUT_RUN = agent_reply("", timed_out=True)
UNPARSED_RUN = agent_reply(NO_BLOCK_REPLY)
_TOO_LONG_TO_RECORD = "q" * MAX_RECORDED_BODY
UNRECORDABLE_RUN = agent_reply(late_block(
    '{"decision": "question", "category": "unsafe_split", '
    '"question": "' + _TOO_LONG_TO_RECORD + '"}'
))

# A worktree the read-only adjudicator moved. The run finished and its verdict
# is refused, which is one more completion that only parks.
MOVED_CANDIDATE = WorktreeSeed(head=OTHER_SHA)

PARK_TIMEOUT = "late_adjudicator_timeout"
PARK_UNPARSED = "late_manifest_invalid"
PARK_UNRECORDABLE = "late_result_unrecordable"
PARK_WORKTREE_MUTATED = "late_worktree_mutated"

# What one entry of the table below is read by.
NAME = "name"
RUN = "run"
TREE = "worktree"
REASON = "reason"

# Every non-verdict completion, with the reason it parks under and the
# worktree it needs. One table, because what the guard owes each of them is
# identical and a case added here is a case both races cover. Spelled as
# mappings rather than tuples so a test reads one case rather than unpacking
# four names it then has to keep straight.
PARKING_COMPLETIONS = (
    {NAME: "a timeout", RUN: TIMEOUT_RUN, TREE: None, REASON: PARK_TIMEOUT},
    {
        NAME: "an unusable reply",
        RUN: UNPARSED_RUN,
        TREE: None,
        REASON: PARK_UNPARSED,
    },
    {
        NAME: "an unrecordable outcome",
        RUN: UNRECORDABLE_RUN,
        TREE: None,
        REASON: PARK_UNRECORDABLE,
    },
    {
        NAME: "a moved candidate",
        RUN: SPLIT_RUN,
        TREE: MOVED_CANDIDATE,
        REASON: PARK_WORKTREE_MUTATED,
    },
)

# The mention id a park's own notice took, and therefore the watermark a
# recovery follow-up for that episode is looked for above.
PARK_NOTICE_ID = 100

# A split this issue already recorded against exactly this candidate: what a
# tick reuses instead of paying for a second adjudication.
RECORDED_SPLIT = MappingProxyType({
    KEYS.verdict: "split",
    KEYS.children: [
        {"title": "A", "body": "a", "depends_on": []},
        {"title": "B", "body": "b", "depends_on": [0]},
    ],
    KEYS.run_cycle_id: late_generation().cycle_id,
    KEYS.run_generation: late_generation().generation,
    KEYS.source_sha: CANDIDATE_SHA,
})

# What a human replacing a held pull request's description leaves behind: text
# the preserved copy is no longer a description of.
HUMAN_REWRITE = "I rewrote this while it was held."

# The two seams a killed tick can die at, named so a test says which.
OWNER_READ = "_owner_state"
OWNER_GUARD = "_guarded_owner"

# A shape GitHub could answer with that names no state at all. Reading it as
# open would publish on the strength of a read that established nothing.
STATELESS_OWNER = MagicMock(closed=False, state="")


class _ClosedDuringRun:
    """A human closing the issue while the agent is still running."""

    def __init__(self, issue, agent_result) -> None:
        self._issue = issue
        self._agent_result = agent_result

    def __call__(self, *_args, **_kwargs):
        self._issue.closed = True
        return self._agent_result


# What a human editing the notice rather than replacing it leaves behind: the
# hidden marker is still in the body, and so are words nothing here wrote.
HUMAN_ADDITION = "and a note of my own."


class _RewrittenDuringRun:
    """A human writing on the held description while the agent is running.

    Whatever they leave is what `body` says. Replacing the notice outright and
    editing a sentence inside it are the same event to everything downstream
    -- the second one is the sharp case, since the hidden marker survives it,
    so reading that marker's presence as proof the body is unchanged would
    call the pull request held and restore the preserved copy over what they
    wrote.
    """

    def __init__(self, plan_pr, agent_result, body: str = HUMAN_REWRITE):
        self._plan_pr = plan_pr
        self._agent_result = agent_result
        self._body = body

    def __call__(self, *_args, **_kwargs):
        self._plan_pr.body = self._body
        return self._agent_result


@contextlib.contextmanager
def unreadable_owner(github: FakeGitHubClient):
    """GitHub refusing the re-read the guard takes after the run."""
    with patch.object(github, "get_issue", side_effect=RuntimeError):
        yield


@contextlib.contextmanager
def killed_at(seam: str):
    """The process dying at one of the guard's seams, rather than failing.

    A `BaseException` the guard's own `except Exception` cannot catch, which
    is the whole point: a read that FAILS is handled, and a tick that does not
    live long enough to see it fail is what the obligation has to be written
    ahead of. Aimed at the guard rather than at the client, since the mid-run
    pause probe re-fetches the same issue and killing that one would be a
    different tick entirely.

    `OWNER_READ` is the kill inside the read, past the claim. `OWNER_GUARD` is
    one step earlier and nothing of the guard runs at all -- the boundary that
    decides whether the obligation is part of the write that recorded the
    result or something the step after it adds.
    """
    with patch.object(_late_owner, seam, side_effect=KeyboardInterrupt):
        yield


@contextlib.contextmanager
def stateless_owner(github: FakeGitHubClient):
    """A re-read that comes back naming no state this binary knows."""
    with patch.object(github, "get_issue", return_value=STATELESS_OWNER):
        yield


# The park a previous tick's failed read left standing. Seeded beside the
# generation's own marker because the two halves are what the reconciliation
# reads together: the marker says a read is owed, and the park says this mode
# told somebody so and therefore owes them a follow-up when it heals.
_OWED_READ_PARK = MappingProxyType({
    KEYS.awaiting: True,
    KEYS.park_reason: PARK_OWNER_UNREADABLE,
    KEY_LAST_ACTION_COMMENT_ID: PARK_NOTICE_ID,
})


# The branch a candidate publishes on, pinned so the exact-commit lookup is
# asked about a branch the fake's pull requests can actually be on.
CANDIDATE_BRANCH = "orchestrator/issue-41-candidate"

KEY_BRANCH = "branch"

KEY_PR_NUMBER = "pr_number"

# A pull request that is neither the plan nor this candidate's. What makes it
# worth its own fixture is that it is MERGED: carried into the implementing
# stage it ends the issue as done, on a change the accepted candidate is not
# in.
SETTLED_PR_NUMBER = 91

CARRYING_PR_NUMBER = 92


class GuardedLateCase(LateCase):
    """One late issue, adjudicated once, reported by what it decided."""

    def _decide(self, agent_result=SPLIT_RUN):
        """Adjudicate once and report only the outcome."""
        outcome, _spawn = self._adjudicate(agent_result)
        return outcome

    def _decide_unread(self, agent_result=SPLIT_RUN):
        """Adjudicate once with the owner unreadable, log line included."""
        with unreadable_owner(self.github):
            with self.assertLogs(WORKFLOW_LOG, level=ERROR):
                return self._decide(agent_result)

    def _seed_owing(self, recorded=None, **generation_fields) -> None:
        """Re-seed this issue as one owing an owner read from a prior tick.

        `recorded` is the run record a tick that got as far as an answer left
        beside it, for the tests about what happens once the read heals.
        """
        self.github.seed_state(
            self.issue.number,
            **generation_state(
                late_generation(
                    owner_check_pending=True, **generation_fields,
                ),
            ),
            **_OWED_READ_PARK,
            **(recorded or {}),
        )


class HeldPlanPrCase(GuardedLateCase):
    """A late issue whose plan PR already wears this generation's hold.

    Seeded held rather than held by a first tick, because what these tests
    are about is the RELEASE: an adjudication that has to take the hold first
    would have to record a verdict to get there, and a recorded verdict is
    exactly what stops the next tick spawning the run whose verdict is under
    test.
    """

    def setUp(self) -> None:
        super().setUp()
        self.github = FakeGitHubClient()
        self.generation = late_generation(
            plan_pr_number=PLAN_PR_NUMBER, plan_pr_body=PLAN_PR_BODY,
        )
        self.issue = seed_late_issue(
            self.github,
            self.generation,
            pr_number=PLAN_PR_NUMBER,
            **{KEY_PLAN_PATH: PLAN_PATH},
        )
        self.plan_pr = seed_plan_pr(
            self.github, body=_late_hold._hold_body(self.generation),
        )
