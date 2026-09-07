# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""One adjudicated candidate parked for the person nobody can show.

The fixture the authorization park's own contract is driven through, apart
from any tick: what these cases are about is a thread and a pinned comment --
which reply a reading acts on, what the record it writes says, and how far it
consumes -- and driving that through a whole stage handler would put a
publication seam between the case and the answer it is asserting on.

The generation carries the PAIR and no count, which is exactly what the park
leaves: a record answering "oversized" is what this workflow means by an
adjudication in flight, and the dispatcher puts `workflow:decomposing` back
over one before any stage runs. So the reading is re-taken by the tick that
acts, and the count a case hands in is that tick's own.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.late_split import state as _late_state
from orchestrator.workflow.late_split.models import LateGeneration, LatePhase
from orchestrator.workflow.stages.implementing import (
    late_command as _command,
    late_records as _records,
    state as _state,
)
from tests.support.fakes import FakeComment, FakeGitHubClient, FakeUser, make_issue
from tests.workflow.fixtures import (
    _TEST_SPEC,
    LABEL_IMPLEMENTING,
    MEASURED_BASE_SHA,
    MEASURED_CANDIDATE_SHA,
    SHA_LENGTH,
)

ISSUE_NUMBER = 612
THRESHOLD = 4000
OVERSIZED_ADDITIONS = 9123
PR_NUMBER = 41
WORKTREE = Path("/tmp/orchestrator-test-late-consent")

# A directory the recovery's existence probe finds, standing in for the
# checkout the committed candidate lives in.
TEMP_WORKTREE_ROOT = Path("/tmp")

# A commit that types as one and that no record on this issue names: the id an
# operator copies out of a notice about work a resumed developer moved past.
STRANGER_SHA = "d" * SHA_LENGTH

# How much of a whole object id a `git log` line shows, which is what somebody
# types when they abbreviate. Nothing in this domain writes one, so it is the
# mismatch it is rather than a prefix to compare.
ABBREVIATED = 7

TRUSTED_AUTHOR = "alice"
OUTSIDER = "mallory"
ALLOWLIST_CONFIG = "ALLOWED_ISSUE_AUTHORS"

# Where the thread had been read to when the park went up, so every reply a
# case seeds is one the reading is entitled to find.
PRIOR_ACTION_COMMENT_ID = 900

_COMMAND = "/orchestrator authorize-oversized {commit}"

AUTHORIZE = _COMMAND.format(commit=MEASURED_CANDIDATE_SHA)
AUTHORIZE_ANOTHER = _COMMAND.format(commit=STRANGER_SHA)
AUTHORIZE_ABBREVIATED = _COMMAND.format(
    commit=MEASURED_CANDIDATE_SHA[:ABBREVIATED],
)
GUIDANCE = "make it smaller, please"

KEY_OVERRIDE_CANDIDATE_SHA = "late_override_candidate_sha"
KEY_OVERRIDE_BASE_SHA = "late_override_base_sha"
KEY_OVERRIDE_ADDITIONS = "late_override_additions"
KEY_OVERRIDE_THRESHOLD = "late_override_threshold"
KEY_OVERRIDE_COMMENT_ID = "late_override_comment_id"

KEY_EXEMPT_SHA = "late_exempt_sha"


def measured() -> LateGeneration:
    """The reading the tick that acts took, which the terms are written from."""
    return LateGeneration(
        cycle_id=1,
        generation=1,
        root_issue=ISSUE_NUMBER,
        current_issue=ISSUE_NUMBER,
        lineage_depth=0,
        candidate_sha=MEASURED_CANDIDATE_SHA,
        base_sha=MEASURED_BASE_SHA,
        threshold=THRESHOLD,
        additions=OVERSIZED_ADDITIONS,
        phase=LatePhase.MEASURING,
    )


# A gate call entered PAST a publication: the stage it takes the issue out
# of, the pull request the work already has, and the head that pull request
# stands on. What it changes here is the notice, since guidance reaches a
# developer only where the ordinary resume is still in front of the issue.
PUBLISHED_ENTRY = _records._PublicationEntry(
    stage=LABEL_IMPLEMENTING,
    pr_number=PR_NUMBER,
    published_sha=MEASURED_BASE_SHA,
)


def measured_pair(**overrides) -> dict:
    """The pair the freeze wrote, which is all a standing park carries.

    Deliberately without the count: a generation answering "oversized" is what
    this workflow means by an adjudication in flight, so a park that recorded
    one would be relabelled out from under itself before anything could answer
    it. What the announce-once guard compares is the COMMIT.
    """
    recorded = PinnedState(data={})
    _late_state.write_late_generation(
        recorded, replace(measured(), additions=0, **overrides),
    )
    return recorded.data


class _ParkedCase:
    """An issue holding one adjudicated candidate nobody has authorized."""

    def setUp(self) -> None:
        self.github = FakeGitHubClient()
        self.issue = make_issue(ISSUE_NUMBER, label=LABEL_IMPLEMENTING)
        self.github.add_issue(self.issue)
        self.github.seed_state(ISSUE_NUMBER)
        self._seed()

    def _seed(self, **state) -> None:
        """Replace the pinned comment with the one a case is about."""
        self.github.seed_state(ISSUE_NUMBER, **{
            _state._AWAITING_HUMAN: True,
            _state._PARK_REASON: _command.PARK_UNAUTHORIZED_EXEMPTION,
            _state._LAST_ACTION_COMMENT_ID: PRIOR_ACTION_COMMENT_ID,
            KEY_EXEMPT_SHA: MEASURED_CANDIDATE_SHA,
            **state,
        })

    def _unparked(self, **state) -> None:
        """The same issue with nothing standing on it, for the door cases."""
        self.github.seed_state(ISSUE_NUMBER, **{
            _state._LAST_ACTION_COMMENT_ID: PRIOR_ACTION_COMMENT_ID,
            KEY_EXEMPT_SHA: MEASURED_CANDIDATE_SHA,
            **state,
        })

    def _reply(self, body: str, author: str = TRUSTED_AUTHOR) -> int:
        """Add one comment past the consumed watermark, and say which it is."""
        identified = self.github.next_reply_id(self.issue)
        self.issue.comments.append(
            FakeComment(identified, body, user=FakeUser(author)),
        )
        return identified

    def _state(self) -> PinnedState:
        return self.github.read_pinned_state(self.issue)

    def _pinned(self) -> dict:
        return self.github.pinned_data(ISSUE_NUMBER)

    def _gate(self, state: PinnedState | None = None, **entered):
        """The gate call this park was taken on, or is being answered from."""
        return _records._Gate(
            gh=self.github,
            spec=_TEST_SPEC,
            issue=self.issue,
            state=self._state() if state is None else state,
            worktree=WORKTREE,
            **entered,
        )
