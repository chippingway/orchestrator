# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Every reading the gate could not take, which costs the push and not the work.

A tree that is not provably clean, a pull request whose state or head nothing
could read, one that is closed or merged, a count that never happened, a head
that moved off what a live record froze, and a frozen publication that is not
the one this tick reads. Each parks with nothing pushed and no label moved,
rather than reporting a number nobody took.
"""
from __future__ import annotations

import unittest

from orchestrator.git.measurement.models import MeasurementFailure

from tests.workflow.stages.fixing import fixing_test_support as fixing
from tests.workflow.stages.fixing import (
    published_gate_support as support,
)

AT_THE_CEILING = support.AT_THE_CEILING
BASE_OBJECT_PRESENT = support.BASE_OBJECT_PRESENT
CEILING = support.CEILING
COUNT_ADDED_LINES = support.COUNT_ADDED_LINES
FREEZE_BASE_COMMIT = support.FREEZE_BASE_COMMIT
LABEL_DECOMPOSING = support.LABEL_DECOMPOSING
LABEL_READY = support.LABEL_READY
MEASURED_BASE_SHA = support.MEASURED_BASE_SHA
MEASURED_CANDIDATE_SHA = support.MEASURED_CANDIDATE_SHA
PAST_THE_CEILING = support.PAST_THE_CEILING
UNDER_THE_CEILING = support.UNDER_THE_CEILING
_SizeGateFixtureMixin = support._SizeGateFixtureMixin
recorded_generation = support.recorded_generation

FIXING = fixing.FIXING
ISSUE = fixing.ISSUE
PR_HEAD_SHA = fixing.PR_HEAD_SHA
PR_NUMBER = fixing.PR_NUMBER
PUSH_BRANCH = fixing.PUSH_BRANCH
SHA_BEFORE = fixing.SHA_BEFORE
STAGE_FIXING = fixing.STAGE_FIXING
VALIDATING = fixing.VALIDATING
config = fixing.config
patch = fixing.patch

_HELD = (ISSUE, LABEL_DECOMPOSING)
# The two keywords a gated push names its commit and pins its ref by.
REVISION = "revision"
LEASE = "force_with_lease"
WRITE_PINNED_STATE = "write_pinned_state"
WRITE_REJECTED = "pinned write rejected"
SET_WORKFLOW_LABEL = "set_workflow_label"
RELABEL_REJECTED = "label write rejected"
# A second pull request on the same branch, for the record frozen on the
# first: the same head can be the tip of both.
OTHER_PR_NUMBER = PR_NUMBER + 1
# A path no checkout is at, for the host the frozen pair was not made on.
ABSENT_WORKTREE = fixing.Path("/tmp/orchestrator-absent-checkout")
REVIEW_ROUND = fixing.REVIEW_ROUND
PENDING_FIX_AT = fixing.PENDING_FIX_AT

def _published_pr(scenario):
    """The pull request this fixture's round is publishing onto."""
    return scenario.github.get_pr(PR_NUMBER)


def _assert_nothing_was_read(case, scenario, mocks) -> None:
    """Nothing pushed, nothing measured, and a human asked for."""
    case._assert_held(scenario, mocks)
    case._assert_parked(scenario)
    mocks[COUNT_ADDED_LINES].assert_not_called()


class GateRefusalTest(unittest.TestCase, _SizeGateFixtureMixin):
    """Every reading the gate could not take costs the push, not the work."""

    def test_an_unreadable_tree_refuses_the_push(self) -> None:
        # A `git status` that established nothing names no paths, which is
        # what a clean tree names too -- so the diff a push would publish is
        # not the diff anything here could have measured.
        scenario = self._seed_fix_round()

        mocks = self._run_fix_round(scenario, tree_readable=False)

        self._assert_refused(scenario, mocks)

    def test_a_pull_request_closed_mid_run_refuses(self) -> None:
        # The preflight drains a closed pull request before anything runs, so
        # this state can only arrive while the agent is out -- and a closed
        # pull request has nowhere for the push to land, which makes a count
        # against it a question nobody can act on.
        scenario = self._seed_fix_round()
        closing = fixing.MagicMock(side_effect=support._ClosesThePullRequest(
            scenario.github.get_pr(PR_NUMBER),
            fixing._agent(
                session_id=fixing.DEV_SESSION,
                last_message=fixing.PUSHED_FIX_MESSAGE,
            ),
        ))

        mocks = self._run_fix_round(scenario, run_agent=closing)

        self._assert_refused(scenario, mocks)

    def test_a_state_nothing_could_read_refuses(self) -> None:
        # The lookup came back and the request behind `pr_state` did not. A
        # gate that guarded only the lookup would raise out of the one road
        # that ends in a park, and an exception on the way to a park is a park
        # nobody takes -- with the fix still unpushed and unmeasured.
        scenario = self._seed_fix_round()

        mocks = self._run_fix_round(
            scenario, run_agent=self._refuses_one_read(scenario, "state"),
        )

        self._assert_refused(scenario, mocks)

    def test_a_head_nothing_could_read_refuses(self) -> None:
        # The other lazy read, and the one a measurement is worth nothing
        # without: the head is what the count is taken against and what the
        # push is leased to.
        scenario = self._seed_fix_round()

        mocks = self._run_fix_round(
            scenario, run_agent=self._refuses_one_read(scenario, "head"),
        )

        self._assert_refused(scenario, mocks)

    def test_a_count_nobody_could_take_refuses(self) -> None:
        # Never "small": what a failed `git diff` writes to stdout is nothing,
        # which is what a candidate that changes nothing writes too.
        scenario = self._seed_fix_round()

        mocks = self._run_fix_round(
            scenario, added_lines=MeasurementFailure.DIFF_FAILED,
        )

        self._assert_held(scenario, mocks)
        self._assert_parked(scenario)

    def test_a_publication_that_moved_refuses(self) -> None:
        # Something pushed to the pull request between the freeze and this
        # tick, so the frozen pair no longer describes what the pull request
        # would come to. The record is left naming the head it froze rather
        # than re-entered over the one that landed, which is what keeps the
        # move visible to whoever reconciles it.
        scenario = self._seed_fix_round(**recorded_generation())
        scenario.github.get_pr(PR_NUMBER).head.sha = support.MOVED_HEAD

        mocks = self._run_fix_round(scenario)

        self._assert_refused(scenario, mocks)
        self.assertEqual(
            scenario.github.pinned_data(ISSUE)[support.KEY_PUBLISHED_SHA],
            PR_HEAD_SHA,
        )

    def _refuses_one_read(self, scenario, failing: str):
        """A dev run that leaves the pull request refusing one attribute."""
        return fixing.MagicMock(side_effect=support._BreaksThePullRequest(
            scenario.github, PR_NUMBER, failing,
            fixing._agent(
                session_id=fixing.DEV_SESSION,
                last_message=fixing.PUSHED_FIX_MESSAGE,
            ),
        ))

    _assert_refused = _assert_nothing_was_read


class EntryStageRefusalTest(unittest.TestCase, _SizeGateFixtureMixin):
    """A stage the entry may not freeze a publication group on.

    The five that push onto a pull request the remote already carries are the
    whole of it. `ready`, `blocked`, and `umbrella` each have an edge to the
    adjudication for reasons of their own and no pull request behind any of
    them, so a check against the transition graph would wave one through.
    """

    def test_a_stage_nothing_publishes_from_refuses(self) -> None:
        # The stage the entry freezes is the one the issue carries AFTER the
        # run, so a human relabel landing while the agent is out is what this
        # reads back. Frozen from there, the record would name a stage no
        # reconciliation may measure or push a candidate from -- and the group
        # is the one thing a later tick could not re-derive.
        scenario = self._seed_fix_round()
        moved = fixing.MagicMock(side_effect=support._RelabelsTheIssue(
            scenario.issue, LABEL_READY,
            fixing._agent(
                session_id=fixing.DEV_SESSION,
                last_message=fixing.PUSHED_FIX_MESSAGE,
            ),
        ))

        mocks = self._run_fix_round(scenario, run_agent=moved)

        _assert_nothing_was_read(self, scenario, mocks)
        self.assertNotIn(
            support.KEY_SOURCE_STAGE, scenario.github.pinned_data(ISSUE),
        )


class PublicationMovedMidRunTest(unittest.TestCase, _SizeGateFixtureMixin):
    """A pull request somebody else pushed to while the agent was out.

    The branch is in sync with its publication when a fix round opens -- the
    reviewer just read that head -- so the head the round names is the head
    the agent built on. Read afterwards instead, a push that landed in between
    becomes the lease and the force-push drops it.
    """

    def test_a_publication_that_moved_mid_run_refuses(self) -> None:
        # The race the round's own head closes. The pull request was standing
        # on A when the reviewer read it and this round began there; somebody
        # pushed B while the agent was out, and the agent built C on top of A.
        # Read afterwards, B becomes the lease and the force-push puts C on
        # the branch with B gone. Named up front, the two readings of that one
        # fact disagree and nothing is measured or pushed at all.
        scenario = self._seed_fix_round()

        mocks = self._run_fix_round(
            scenario,
            run_agent=support._MovesThePullRequest(
                scenario.github.get_pr(PR_NUMBER),
                support.MOVED_HEAD,
                fixing._agent(
                    session_id=fixing.DEV_SESSION,
                    last_message=fixing.PUSHED_FIX_MESSAGE,
                ),
            ),
        )

        self._assert_refused(scenario, mocks)
        # And the pull request is left exactly where the other push put it.
        self.assertEqual(
            scenario.github.get_pr(PR_NUMBER).head.sha, support.MOVED_HEAD,
        )

    def test_a_move_onto_the_candidate_refuses(self) -> None:
        # The exact-candidate move, which is the one a fresh round cannot
        # explain. Nothing of this workflow's has pushed yet -- no approval,
        # no receipt, no record -- so a pull request that leaves the head the
        # round began at and arrives at the very commit the agent just made
        # got there because the AGENT pushed it, not because a settlement
        # landed. Read as this issue's own push the candidate is measured and
        # routed, which hands adjudication a change the remote already carries
        # and is exactly the release this gate exists to hold back.
        scenario = self._seed_fix_round()
        published = _published_pr(scenario)

        mocks = self._run_fix_round(
            scenario,
            run_agent=support._MovesThePullRequest(
                published,
                MEASURED_CANDIDATE_SHA,
                fixing._agent(
                    session_id=fixing.DEV_SESSION,
                    last_message=fixing.PUSHED_FIX_MESSAGE,
                ),
            ),
        )

        self._assert_refused(scenario, mocks)
        self.assertNotIn(
            (ISSUE, LABEL_DECOMPOSING), scenario.github.label_history,
        )
        self.assertEqual(published.head.sha, MEASURED_CANDIDATE_SHA)

    def test_a_rewind_onto_its_own_receipt_refuses(self) -> None:
        # The sharp form of the same rewind, and the one pairing the receipt
        # with the commit in hand does not catch: the branch is rewound onto a
        # commit published rounds ago and the CHECKOUT is standing on it too,
        # so the receipt names the candidate. Every local fact then agrees and
        # none of them is about this round -- forgiven, the gate reads the
        # candidate as already published, takes no count at all, and hands the
        # reviewer a pull request somebody else moved. What dates a receipt is
        # the head it replaced, and a rewind cannot supply the one this round
        # began at: a receipt from an earlier attempt names another, and one
        # written before the pair was recorded names none.
        for lease in (support.STALE_RECEIPT, None):
            with self.subTest(lease=lease):
                scenario = self._seed_fix_round(**{
                    support.KEY_RECEIPT_SHA: MEASURED_CANDIDATE_SHA,
                    support.KEY_RECEIPT_LEASE: lease,
                })
                published = _published_pr(scenario)

                mocks = self._run_fix_round(
                    scenario,
                    run_agent=support._MovesThePullRequest(
                        published,
                        MEASURED_CANDIDATE_SHA,
                        fixing._agent(
                            session_id=fixing.DEV_SESSION,
                            last_message=fixing.PUSHED_FIX_MESSAGE,
                        ),
                    ),
                )

                self._assert_refused(scenario, mocks)

    def test_a_move_onto_a_stale_receipt_refuses(self) -> None:
        # The one move the entry forgives is this issue's OWN push having
        # landed, and every piece of evidence for that is a durable record of
        # one: a live approval, a live record, or the receipt read together
        # with the commit in hand. The receipt ALONE is not -- it names the
        # last commit this stage pushed and is never cleared, so a pull
        # request a revert or a rewrite rewound onto a commit published rounds
        # ago would read as this tick's push arriving. Forgiven, the candidate
        # is measured and force-pushed over whoever rewound it.
        scenario = self._seed_fix_round(
            **{support.KEY_RECEIPT_SHA: support.STALE_RECEIPT},
        )

        mocks = self._run_fix_round(
            scenario,
            run_agent=support._MovesThePullRequest(
                scenario.github.get_pr(PR_NUMBER),
                support.STALE_RECEIPT,
                fixing._agent(
                    session_id=fixing.DEV_SESSION,
                    last_message=fixing.PUSHED_FIX_MESSAGE,
                ),
            ),
        )

        self._assert_refused(scenario, mocks)
        self.assertEqual(
            scenario.github.get_pr(PR_NUMBER).head.sha, support.STALE_RECEIPT,
        )

    _assert_refused = _assert_nothing_was_read


class FrozenPublicationIdentityTest(
    unittest.TestCase, _SizeGateFixtureMixin,
):
    """The whole frozen group is compared, or nothing is measured at all."""

    def test_a_changed_pull_request_refuses(self) -> None:
        # The head alone is not an identity: a branch reused across two pull
        # requests can put the same commit at the tip of both, so a count
        # taken against one would be settled against the other under the same
        # generation.
        scenario = self._seed_fix_round(
            **recorded_generation(), pr_number=OTHER_PR_NUMBER,
        )
        scenario.github.add_pr(self._open_pr(number=OTHER_PR_NUMBER))

        mocks = self._run_fix_round(scenario)

        self._assert_refused(scenario, mocks)
        self.assertEqual(
            scenario.github.pinned_data(ISSUE)[support.KEY_PUBLISHED_PR],
            PR_NUMBER,
        )

    def test_a_damaged_publication_refuses(self) -> None:
        # The marker says the reading was taken on a publication and the
        # record cannot name it. Skipping the comparison there is what lets
        # the entry read NOW be stamped over the evidence the count was
        # actually taken on, so an old number is acted on under a publication
        # nobody measured it against.
        scenario = self._seed_fix_round(**self._damaged())

        mocks = self._run_fix_round(scenario)

        self._assert_refused(scenario, mocks)
        self.assertNotIn(
            support.KEY_PUBLISHED_SHA, scenario.github.pinned_data(ISSUE),
        )

    def _damaged(self) -> dict:
        """A frozen group whose head a hand edit took off the record."""
        damaged = recorded_generation()
        damaged.pop(support.KEY_PUBLISHED_SHA)
        return damaged

    _assert_refused = _assert_nothing_was_read
