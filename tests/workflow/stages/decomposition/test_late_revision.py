# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The developer run guidance buys, and the candidate it comes back with."""
from __future__ import annotations

from orchestrator.workflow.late_split.models import LateFailure
from orchestrator.workflow.stages.decomposition.late_models import (
    _LateDisposition,
)

from tests.workflow.stages.decomposition.late_content_support import (
    DRIFT_PARKED,
    EDITED_BODY,
    EDITED_TITLE,
    EVENT_AGENT_SPAWN,
    EVENT_LATE_MEASUREMENT,
    GUIDANCE_BODY,
)
from tests.workflow.stages.decomposition.late_content_support import (
    KEY_ADDITIONS,
    KEY_COMMENT_WATERMARK,
    KEY_GENERATION,
    KEY_LAST_ACTION_COMMENT_ID,
)
from tests.workflow.stages.decomposition.late_content_support import (
    PARK_REVISION_DIRTY,
    PARK_REVISION_UNMEASURED,
    REVISED_ADDITIONS,
    REVISED_BASE_SHA,
    REVISED_SHA,
    REVISION_PARKED,
    ROLE_DEVELOPER,
    STAGE_DECOMPOSING,
)
from tests.workflow.stages.decomposition.late_content_support import (
    BARE_CONTINUE,
    RECORDED_SINGLE,
    reply,
)
from tests.workflow.stages.decomposition.late_revision_support import (
    DEV_ACK,
    DEV_PIN,
    DEV_SESSION,
    DIRTY_TREE,
    PausedDuringRun,
    RevisionCase,
    UNMEASURED,
)
from tests.workflow.stages.decomposition.late_run_support import (
    WorktreeSeed,
    agent_reply,
)
from tests.workflow.stages.decomposition.late_test_support import (
    CANDIDATE_SHA,
    EVENT_LATE_FAILURE,
    GENERATION_NUMBER,
    KEYS,
    NEXT_GENERATION,
)


class DeveloperResumeTest(RevisionCase):
    """Whose session runs, under which role and stage, and on what."""

    def test_guidance_resumes_the_locked_session(self) -> None:
        self._seed_drifted()

        outcome, spawn = self._revise()

        self.assertEqual(outcome.disposition, _LateDisposition.REVISED)
        spawn.assert_called_once()
        self.assertEqual(
            spawn.call_args.kwargs["resume_session_id"], DEV_SESSION,
        )

    def test_the_run_is_a_developer_decomposing(self) -> None:
        self._seed_drifted()

        self._revise()

        spawned = self._events_named(EVENT_AGENT_SPAWN)[-1]
        self.assertEqual(spawned["agent_role"], ROLE_DEVELOPER)
        self.assertEqual(spawned["stage"], STAGE_DECOMPOSING)

    def test_the_guidance_is_what_the_dev_is_shown(self) -> None:
        self._seed_drifted()

        _outcome, spawn = self._revise()

        self.assertIn(GUIDANCE_BODY, spawn.call_args.args[1])

    def test_the_edited_issue_is_shown_beside_it(self) -> None:
        # A resume is exactly the case that cannot see an edit: the replayed
        # transcript holds the issue as it read when the work started, and the
        # commonest reason to be here is that a human changed it since.
        self._seed_drifted()
        self.issue.body = EDITED_BODY

        _outcome, spawn = self._revise()

        prompt = spawn.call_args.args[1]
        self.assertIn(EDITED_TITLE, prompt)
        self.assertIn(EDITED_BODY, prompt)

    def test_a_landed_run_records_the_reply_as_read(self) -> None:
        # Both watermarks, because two consumers read the same thread: the
        # generation's own, so the comment does not come back as fresh
        # guidance, and the issue-wide one, so the later validating ->
        # in_review handoff does not replay it as fresh PR feedback.
        self._seed_drifted()

        self._revise()

        pinned = self._pinned()
        self.assertEqual(pinned[KEY_COMMENT_WATERMARK], self.guidance.id)
        self.assertEqual(pinned[KEY_LAST_ACTION_COMMENT_ID], self.guidance.id)

    def test_a_declined_run_consumes_nothing(self) -> None:
        # A pause and a shutdown sweep both mean the tick did not happen. A
        # consumption made durable by one of them would drop the human's
        # instruction with nothing on the issue left pointing at it.
        for label, declined in (
            ("paused", PausedDuringRun(self)),
            ("interrupted", agent_reply(DEV_ACK, interrupted=True)),
        ):
            with self.subTest(declined=label):
                self._seed_drifted()

                outcome, _spawn = self._revise(reply=declined)

                self.assertEqual(outcome.disposition, _LateDisposition.DEFERRED)
                pinned = self._pinned()
                self.assertNotIn(KEY_COMMENT_WATERMARK, pinned)
                self.assertTrue(pinned[KEYS.awaiting])


class RevisedCandidateTest(RevisionCase):
    """What a clean revised tree is re-frozen and re-measured as."""

    def test_a_new_commit_replaces_the_candidate(self) -> None:
        self._seed_drifted()

        outcome, _spawn = self._revise()

        self.assertEqual(outcome.disposition, _LateDisposition.REVISED)
        pinned = self._pinned()
        self.assertEqual(pinned[KEYS.candidate_sha], REVISED_SHA)
        self.assertEqual(pinned[KEYS.base_sha], REVISED_BASE_SHA)
        self.assertEqual(pinned[KEY_ADDITIONS], REVISED_ADDITIONS)
        self.assertEqual(pinned[KEY_GENERATION], NEXT_GENERATION)
        self.assertFalse(pinned[KEYS.awaiting])
        self.assertEqual(len(self._events_named(EVENT_LATE_MEASUREMENT)), 1)

    def test_a_tree_it_cannot_vouch_for_parks(self) -> None:
        # Uncommitted work is in the checkout a publication pushes from and
        # out of the diff a verdict is taken on, and a status read that
        # established nothing is not proof of anything either.
        for label, seed in (
            ("dirty", WorktreeSeed(head=REVISED_SHA, dirty=DIRTY_TREE)),
            ("unreadable", WorktreeSeed(head=REVISED_SHA, readable=False)),
        ):
            with self.subTest(tree=label):
                self._seed_drifted()

                outcome, _spawn = self._revise(seed=seed)

                self.assertEqual(outcome.disposition, _LateDisposition.PARKED)
                pinned = self._pinned()
                self.assertEqual(pinned[KEYS.park_reason], PARK_REVISION_DIRTY)
                self.assertEqual(pinned[KEYS.candidate_sha], CANDIDATE_SHA)
                self.assertEqual(pinned[KEY_GENERATION], GENERATION_NUMBER)

    def test_an_unreadable_head_is_not_a_candidate(self) -> None:
        self._seed_drifted()

        outcome, _spawn = self._revise(seed=WorktreeSeed(head=""))

        self.assertEqual(outcome.disposition, _LateDisposition.PARKED)
        self.assertEqual(
            self._pinned()[KEYS.park_reason], PARK_REVISION_UNMEASURED,
        )

    def test_a_candidate_nobody_measured_is_not_small(self) -> None:
        self._seed_drifted()

        outcome, _spawn = self._revise(measurement=UNMEASURED)

        self.assertEqual(outcome.disposition, _LateDisposition.PARKED)
        pinned = self._pinned()
        self.assertEqual(pinned[KEYS.park_reason], PARK_REVISION_UNMEASURED)
        self.assertEqual(pinned[KEYS.candidate_sha], CANDIDATE_SHA)
        self.assertEqual(
            [
                record["failure"]
                for record in self._events_named(EVENT_LATE_FAILURE)
            ],
            [str(LateFailure.MEASUREMENT_FAILED)],
        )


class StalledRevisionTest(RevisionCase):
    """A bare continue re-reads a finished run rather than paying again."""

    def test_a_continue_remeasures_without_a_spawn(self) -> None:
        self._seed(**REVISION_PARKED, **DEV_PIN)
        reply(self.issue, BARE_CONTINUE)

        outcome, spawn = self._revise()

        self.assertEqual(outcome.disposition, _LateDisposition.REVISED)
        spawn.assert_not_called()
        pinned = self._pinned()
        self.assertEqual(pinned[KEYS.candidate_sha], REVISED_SHA)
        self.assertFalse(pinned[KEYS.awaiting])

    def test_a_still_dirty_tree_repeats_no_notice(self) -> None:
        self._seed(**REVISION_PARKED, **DEV_PIN)
        reply(self.issue, BARE_CONTINUE)
        self._revise(seed=WorktreeSeed(head=REVISED_SHA, dirty=DIRTY_TREE))
        posted = len(self._bodies())

        outcome, spawn = self._revise(
            seed=WorktreeSeed(head=REVISED_SHA, dirty=DIRTY_TREE),
        )

        self.assertEqual(outcome.disposition, _LateDisposition.PARKED)
        spawn.assert_not_called()
        self.assertEqual(len(self._bodies()), posted)

    def test_nothing_new_leaves_the_park_alone(self) -> None:
        self._seed(**REVISION_PARKED, **DEV_PIN)

        outcome, spawn = self._revise()

        self.assertEqual(outcome.disposition, _LateDisposition.PARKED)
        spawn.assert_not_called()
        self.assertEqual(self._pinned()[KEYS.candidate_sha], CANDIDATE_SHA)

    def test_guidance_runs_the_developer_again(self) -> None:
        self._seed(**REVISION_PARKED, **DEV_PIN)
        reply(self.issue)

        outcome, spawn = self._revise()

        self.assertEqual(outcome.disposition, _LateDisposition.REVISED)
        spawn.assert_called_once()

    def test_guidance_beside_a_reverted_edit_runs(self) -> None:
        # Taking the edit back does not withdraw the change the human asked
        # for. Absorbing it into the baseline would consume an instruction
        # without acting on it and then reuse a verdict nobody re-earned.
        self._seed(**DRIFT_PARKED, **DEV_PIN)
        reply(self.issue)

        outcome, spawn = self._revise()

        self.assertEqual(outcome.disposition, _LateDisposition.REVISED)
        spawn.assert_called_once()
        pinned = self._pinned()
        self.assertEqual(pinned[KEYS.candidate_sha], REVISED_SHA)
        self.assertFalse(pinned[KEYS.awaiting])


class UnparkedGuidanceTest(RevisionCase):
    """What a reply earns when the issue is waiting on nothing."""

    def test_guidance_runs_the_developer(self) -> None:
        # Guidance means the same thing with nothing parked: the work has to
        # change. Folding it into the baseline would consume a human's
        # instruction without acting on it.
        self._seed(**DEV_PIN)
        reply(self.issue)

        revised, resumed = self._revise()

        self.assertEqual(revised.disposition, _LateDisposition.REVISED)
        resumed.assert_called_once()
        self.assertEqual(self._pinned()[KEYS.candidate_sha], REVISED_SHA)

    def test_guidance_after_a_verdict_runs_too(self) -> None:
        # A verdict recorded over work the human has since asked to be
        # different is exactly the one that must not stand: the re-measured
        # candidate advances the generation, so the old answer stops applying.
        self._seed(**RECORDED_SINGLE, **DEV_PIN)
        reply(self.issue)

        revised, resumed = self._revise()

        self.assertEqual(revised.disposition, _LateDisposition.REVISED)
        resumed.assert_called_once()
        pinned = self._pinned()
        self.assertEqual(pinned[KEY_GENERATION], NEXT_GENERATION)
        self.assertEqual(pinned[KEYS.candidate_sha], REVISED_SHA)

    def test_a_continue_with_no_park_does_nothing(self) -> None:
        # The one reply that lands here with nothing to do: no park is waiting
        # on it and no candidate needs certifying.
        self._seed(**RECORDED_SINGLE, **DEV_PIN)
        reply(self.issue, BARE_CONTINUE)

        reused, resumed = self._revise()

        self.assertEqual(reused.disposition, _LateDisposition.DECIDED)
        resumed.assert_not_called()
        self.assertEqual(self._pinned()[KEY_GENERATION], GENERATION_NUMBER)
