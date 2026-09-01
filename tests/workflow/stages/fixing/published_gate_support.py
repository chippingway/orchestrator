# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""One whole tick whose dev run commits onto a pull request that is already open.

The fixture the post-publication size gate's contract is driven through. The
`fixing` in_review route, because it is the shortest road to the shared dev-fix
publication every gated push goes through: one unread comment past the debounce
window resumes the locked session, the run commits, and everything after that
is the gate and the push it either allows or holds.

It is a `fixing` scenario and lives with that route's own fixture, whatever it
is used to exercise: what it seeds and runs is this stage's handler, so keeping
it here is what stops the tests of another stage's owner reaching across a
package boundary for it.
"""

from __future__ import annotations

# The frozen commit and the worktree status a case seeds the gate with.
# Every case names this module `support` and reads them off it, so the
# same-name alias is what declares the import a re-export rather than a
# dead one -- the same reason the mid-run effects below carry one.
from orchestrator.git.measurement.models import FrozenCommit as FrozenCommit
from orchestrator.git.verification.probes import (
    _WorktreeStatus as _WorktreeStatus,
)
from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.late_split import state as _late_state
from orchestrator.workflow.late_split.models import LateGeneration, LatePhase

from tests.workflow import fixtures
# The four things a case can have happen to the pull request while the dev
# run is out, reached off this module through the same door.
from tests.workflow.mid_run_effects import (
    _BreaksThePullRequest as _BreaksThePullRequest,
    _ClosesThePullRequest as _ClosesThePullRequest,
    _MovesThePullRequest as _MovesThePullRequest,
    _RelabelsTheIssue as _RelabelsTheIssue,
)
from tests.workflow.stages.fixing import fixing_test_support as support

MEASURED_BASE_SHA = fixtures.MEASURED_BASE_SHA
MEASURED_CANDIDATE_SHA = fixtures.MEASURED_CANDIDATE_SHA
LABEL_DECOMPOSING = fixtures.LABEL_DECOMPOSING

# A state with an edge to the adjudication and no pull request behind it,
# for the human relabel that lands while an agent is out.
LABEL_READY = fixtures.LABEL_READY

# The pinned keys a generation the size gate froze round-trips through, and
# the four the publication group is read back off.
KEY_CANDIDATE_SHA = "late_candidate_sha"
KEY_BASE_SHA = "late_base_sha"
KEY_THRESHOLD = "late_threshold"
KEY_ADDITIONS = "late_additions"
KEY_PHASE = "late_phase"
KEY_APPROVED_SHA = "late_approved_sha"
KEY_APPROVED_LEASE = "late_approved_lease"
KEY_POST_PUBLICATION = "late_post_publication"
KEY_SOURCE_STAGE = "late_source_stage"
KEY_PUBLISHED_PR = "late_published_pr_number"
KEY_PUBLISHED_SHA = "late_published_sha"

# The receipt a landed gated push leaves, which is the implementing seam's
# own field rather than one of the group above: it names what this branch put
# on the remote, not what the reading was entered against.
KEY_RECEIPT_SHA = "implementing_published_sha"

# The head that receipt REPLACED, written with it and never on its own: what
# dates the receipt to one publication attempt, since the receipt itself is
# never cleared and goes on naming a commit pushed rounds ago.
KEY_RECEIPT_LEASE = "implementing_published_lease"

# The validating route's single replay anchor, cleared with its round.
KEY_REVIEWER_COMMENT_ID = "pending_fix_reviewer_comment_id"

PARK_MEASUREMENT_FAILED = "late_measurement_failed"
PARK_CANDIDATE_MOVED = "late_candidate_moved"
PHASE_MEASURING = "measuring"
EVENT_LATE_MEASUREMENT = "late_measurement"

COUNT_ADDED_LINES = "_count_added_lines"
FREEZE_BASE_COMMIT = "_freeze_base_commit"
BASE_OBJECT_PRESENT = "_base_object_present"

# The two keywords a gated push names its commit and pins its ref by.
REVISION = "revision"
LEASE = "force_with_lease"

CEILING = 5
UNDER_THE_CEILING = 4
AT_THE_CEILING = 5
PAST_THE_CEILING = 6
MAX_ADDED_LINES = "MAX_ADDED_LINES"
DECOMPOSE = "DECOMPOSE"

# A head the pull request was not left standing on, for the tick that finds
# somebody else's push where the record froze one.
MOVED_HEAD = "ab" * (fixtures.SHA_LENGTH // 2)

# A commit the checkout went to while the push was out, for the races the
# publication boundary refuses on the far side of its own effect.
MOVED_AFTER_PUSH = "de" * (fixtures.SHA_LENGTH // 2)

# The commit an earlier tick of this issue froze and the checkout has since
# moved past, for the resumed developer whose fresh commit supersedes a
# record.
SUPERSEDED_CANDIDATE = "5c" * (fixtures.SHA_LENGTH // 2)

# A commit an EARLIER round of this issue put on the remote. The receipt names
# the last push this stage made and is never cleared, so it goes on naming
# this one for the rest of the issue's life -- which is what a case about a
# pull request rewound onto it needs.
STALE_RECEIPT = "7a" * (fixtures.SHA_LENGTH // 2)

# The head each successive round of a pull request grown one fix at a time
# leaves the checkout on. Spelled apart from every other commit here because a
# candidate the receipt already names is a republication rather than a fresh
# fix, and a round of growth is about the fix nobody has measured yet.
GROWN_CANDIDATES = tuple(
    marker * (fixtures.SHA_LENGTH // 2) for marker in ("a1", "b2", "c3")
)


def recorded_generation(**overrides) -> dict:
    """The pinned fields a post-publication generation is retried from.

    Written through the domain's own writer rather than spelled as a dict, so
    a test seeding a crash between the freeze and the count seeds exactly what
    the freeze would have left behind -- the publication it was entered on
    included, which is what the retry proves the pull request has not moved
    against.
    """
    recorded = PinnedState(data={})
    _late_state.write_late_generation(
        recorded,
        LateGeneration(**{
            "cycle_id": 1,
            "generation": 1,
            "root_issue": support.ISSUE,
            "current_issue": support.ISSUE,
            "lineage_depth": 0,
            "candidate_sha": MEASURED_CANDIDATE_SHA,
            "base_sha": MEASURED_BASE_SHA,
            "threshold": CEILING,
            "phase": LatePhase.MEASURING,
            **overrides,
        }).with_publication(
            stage=support.FIXING,
            pr_number=support.PR_NUMBER,
            published_sha=support.PR_HEAD_SHA,
        ),
    )
    return recorded.data


class _SizeGateAssertionsMixin:
    """What a tick that went through the gate looks like afterwards."""

    def _pinned(self, scenario) -> dict:
        """What the pinned comment says once this tick has finished."""
        return scenario.github.pinned_data(support.ISSUE)

    def _assert_unpushed(self, mocks) -> None:
        """Nothing reached the remote on this tick."""
        mocks[support.PUSH_BRANCH].assert_not_called()

    def _assert_pushed_once(self, mocks):
        """One push went out, reported so its keywords can be read off it."""
        pushed = mocks[support.PUSH_BRANCH]
        pushed.assert_called_once()
        return pushed.call_args

    def _assert_settled_publication(self, mocks) -> None:
        """The leased no-op a publication the remote already carries makes.

        Named and pinned at the same commit, which is what makes the request
        the atomic proof it exists to be: the pull request is standing on the
        commit, so git has nothing to send and rejects outright if somebody
        moved it between the freeze and here.
        """
        pushed = self._assert_pushed_once(mocks)
        self.assertEqual(pushed.kwargs[REVISION], MEASURED_CANDIDATE_SHA)
        self.assertEqual(pushed.kwargs[LEASE], MEASURED_CANDIDATE_SHA)

    def _assert_unmeasured(self, mocks) -> None:
        """No reading was taken -- the candidate was decided about already."""
        mocks[COUNT_ADDED_LINES].assert_not_called()

    def _assert_held(self, scenario, mocks) -> None:
        """Nothing pushed, and the issue not handed on for another review."""
        self._assert_unpushed(mocks)
        self.assertNotIn(
            (support.ISSUE, support.VALIDATING), scenario.github.label_history,
        )

    def _assert_parked(self, scenario) -> None:
        pinned = self._pinned(scenario)
        self.assertTrue(pinned[support.AWAITING_HUMAN])
        self.assertEqual(pinned[support.PARK_REASON], PARK_MEASUREMENT_FAILED)
        self.assertEqual(scenario.github.label_history, [])


class _SizeGateFixtureMixin(support._FixingFixtureMixin, _SizeGateAssertionsMixin):
    """The seed and the run one fix round through the gate is driven by."""

    def _seed_fix_round(self, **extra_state):
        long_ago = support.datetime.now(support.timezone.utc) - support.timedelta(
            hours=1,
        )
        feedback = support.FakeComment(
            id=support.TRIGGER_ID,
            body=support.FIX_FEEDBACK,
            user=support.FakeUser(support.ALICE),
            created_at=long_ago,
        )
        return support.IssueScenario(*self._seed(
            pr=self._open_pr(),
            issue_comments=[feedback],
            extra_state=extra_state or None,
        ))

    def _run_fix_round(self, scenario, **run_options):
        run_options.setdefault(
            "run_agent",
            support._agent(
                session_id=support.DEV_SESSION,
                last_message=support.PUSHED_FIX_MESSAGE,
            ),
        )
        run_options.setdefault(
            "head_shas", (support.SHA_BEFORE, support.SHA_AFTER),
        )
        with support.patch.object(
            support.config, support.DEBOUNCE_CONFIG, support.DEBOUNCE_SECONDS,
        ):
            return self._run_fixing(
                scenario.github, scenario.issue, **run_options,
            )
