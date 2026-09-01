# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The late run's pinned record: what it locks, and when it is believed."""
from __future__ import annotations

import unittest
from dataclasses import replace
from unittest.mock import patch

from orchestrator import config
from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.late_split.events import LateVerdictCategory
from orchestrator.workflow.late_split.models import LateVerdict
from orchestrator.workflow.stages.decomposition import (
    late_models as _models,
    late_session as _session,
)
from tests.workflow.fixtures import BACKEND_CODEX
from tests.workflow.stages.decomposition.late_test_support import (
    CANDIDATE_SHA,
    CYCLE_ID,
    GENERATION_NUMBER,
    KEYS,
    LATE_ARGS,
    LATE_BACKEND,
    LATE_SPEC,
    OTHER_SHA,
    ROLE_DECOMPOSER,
    late_generation,
)

DAMAGED_VERDICT = "probably fine"

ASKED = "which half of this is in scope?"

TITLE = "title"
BODY = "body"
DEPENDS_ON = "depends_on"
FIRST_TITLE = "A"
SECOND_TITLE = "B"
FIRST_BODY = "a"
SECOND_BODY = "b"

SPLIT_CHILDREN = (
    {TITLE: FIRST_TITLE, BODY: FIRST_BODY},
    {TITLE: SECOND_TITLE, BODY: SECOND_BODY, DEPENDS_ON: [0]},
)


def recorded_child(title: str = FIRST_TITLE, body: str = FIRST_BODY) -> dict:
    """One child as the pinned comment records it, fields and all."""
    return {TITLE: title, BODY: body, DEPENDS_ON: []}


def _completed_run(**overrides) -> _models._LateRun:
    return replace(
        _models._LateRun(
            role=ROLE_DECOMPOSER,
            spec=LATE_SPEC,
            backend=LATE_BACKEND,
            extra_args=LATE_ARGS,
            cycle_id=CYCLE_ID,
            source_sha=CANDIDATE_SHA,
            generation=GENERATION_NUMBER,
            verdict=LateVerdict.SINGLE,
        ),
        **overrides,
    )


class LateRunRecordTest(unittest.TestCase):
    """What a fresh spawn records, and what a completed run adds to it."""

    def test_a_spawn_records_what_the_run_is(self) -> None:
        state = PinnedState()

        _session._record_late_spawn(state, _completed_run())

        self.assertEqual(state.get(KEYS.role), ROLE_DECOMPOSER)
        self.assertEqual(state.get(KEYS.agent), LATE_SPEC)
        self.assertEqual(state.get(KEYS.run_cycle_id), CYCLE_ID)
        self.assertEqual(state.get(KEYS.source_sha), CANDIDATE_SHA)
        self.assertEqual(state.get(KEYS.run_generation), GENERATION_NUMBER)

    def test_a_fresh_spawn_drops_the_previous_answer(self) -> None:
        # A tick that crashes mid-run must not read the last generation's
        # verdict back as this one's.
        state = PinnedState(data={
            KEYS.session_id: "older-sess",
            KEYS.verdict: str(LateVerdict.SINGLE),
            KEYS.category: str(LateVerdictCategory.UNSAFE_SPLIT),
        })

        _session._record_late_spawn(state, _completed_run())

        for dropped in (KEYS.session_id, KEYS.verdict, KEYS.category):
            with self.subTest(key=dropped):
                self.assertNotIn(dropped, state.data)

    def test_a_result_records_verdict_and_category(self) -> None:
        state = PinnedState()

        _session._record_late_result(state, _models._LateAdjudication(
            verdict=LateVerdict.QUESTION,
            category=LateVerdictCategory.SCOPE_AMBIGUOUS,
            question=ASKED,
        ))

        self.assertEqual(
            state.data,
            {
                KEYS.verdict: str(LateVerdict.QUESTION),
                KEYS.category: str(LateVerdictCategory.SCOPE_AMBIGUOUS),
                KEYS.question: ASKED,
            },
        )

    def test_the_record_round_trips(self) -> None:
        state = PinnedState()
        _session._record_late_spawn(state, _completed_run())
        _session._record_late_result(
            state, _models._LateAdjudication(verdict=LateVerdict.SINGLE),
        )

        self.assertEqual(_session._read_late_run(state), _completed_run())


class LateResultRecordTest(unittest.TestCase):
    """What a completed outcome is written as, and what it refuses to be."""

    def test_a_split_records_its_manifest(self) -> None:
        # The manifest IS what a split decided, so a record without it would
        # refuse the re-run while the answer it stands for was gone.
        state = PinnedState()

        _session._record_late_result(state, _models._LateAdjudication(
            verdict=LateVerdict.SPLIT,
            rationale="two slices",
            children=SPLIT_CHILDREN,
        ))

        self.assertEqual(
            state.get(KEYS.children),
            [
                recorded_child(),
                {TITLE: SECOND_TITLE, BODY: SECOND_BODY, DEPENDS_ON: [0]},
            ],
        )

    def test_a_manifest_carries_only_its_own_fields(self) -> None:
        # Rewritten from the three fields a child issue is created out of, so
        # nothing an agent put beside them lands in the comment humans read.
        state = PinnedState()

        _session._record_late_result(state, _models._LateAdjudication(
            verdict=LateVerdict.SPLIT,
            children=({TITLE: FIRST_TITLE, BODY: FIRST_BODY, "notes": "x"},),
        ))

        self.assertEqual(state.get(KEYS.children), [recorded_child()])

    def test_an_outcome_past_the_budget_is_refused(self) -> None:
        # Shortening it would record a question nobody asked; the caller is
        # told it did not fit rather than handed half an outcome.
        state = PinnedState()

        kept = _session._record_late_result(state, _models._LateAdjudication(
            verdict=LateVerdict.QUESTION,
            category=LateVerdictCategory.UNKNOWN,
            question="q" * _session.MAX_RECORDED_BODY,
        ))

        self.assertFalse(kept)
        self.assertEqual(state.data, {})

    def test_what_the_comment_already_holds_counts(self) -> None:
        # A result small on its own can still be the one that pushes the
        # comment past what GitHub accepts, and finding that out from the
        # failed write means the agent has already been paid for.
        held = PinnedState(data={
            KEYS.plan_pr_body: "p" * (_session.MAX_RECORDED_BODY - 100),
        })
        modest = _models._LateAdjudication(
            verdict=LateVerdict.SPLIT, children=SPLIT_CHILDREN,
        )

        self.assertTrue(
            _session._record_late_result(PinnedState(), modest),
        )
        self.assertFalse(_session._record_late_result(held, modest))
        self.assertNotIn(KEYS.verdict, held.data)

    def test_a_recovered_outcome_is_whole(self) -> None:
        state = PinnedState()
        _session._record_late_result(state, _models._LateAdjudication(
            verdict=LateVerdict.SPLIT, children=SPLIT_CHILDREN,
        ))

        recovered = _session._recovered_adjudication(
            _session._read_late_run(state),
        )

        self.assertEqual(recovered.verdict, LateVerdict.SPLIT)
        self.assertEqual(
            [child[TITLE] for child in recovered.children],
            [FIRST_TITLE, SECOND_TITLE],
        )
        self.assertEqual(recovered.children[1][DEPENDS_ON], [0])

class LateSessionLockTest(unittest.TestCase):
    """Which backend a later run lands on, and what it falls back to."""

    def test_an_unlocked_issue_uses_the_config(self) -> None:
        run = _session._read_late_run(PinnedState())

        self.assertEqual(run.spec, config.DECOMPOSE_AGENT_SPEC)
        self.assertEqual(run.backend, config.DECOMPOSE_AGENT)
        self.assertEqual(run.extra_args, config.DECOMPOSE_AGENT_ARGS)
        self.assertEqual(run.role, ROLE_DECOMPOSER)

    def test_a_locked_spec_outranks_the_config(self) -> None:
        state = PinnedState(data={KEYS.agent: LATE_SPEC})

        with patch.object(config, "DECOMPOSE_AGENT_SPEC", BACKEND_CODEX):
            run = _session._read_late_run(state)

        self.assertEqual(run.spec, LATE_SPEC)
        self.assertEqual(run.backend, LATE_BACKEND)
        self.assertEqual(run.extra_args, LATE_ARGS)

    def test_a_legacy_bare_backend_round_trips(self) -> None:
        run = _session._read_late_run(
            PinnedState(data={KEYS.agent: BACKEND_CODEX}),
        )

        self.assertEqual(run.backend, BACKEND_CODEX)
        self.assertEqual(run.extra_args, ())


class LateRunAnswersTest(unittest.TestCase):
    """When a recorded result is read instead of paying for another run."""

    def test_only_this_generation_and_commit(self) -> None:
        cases = (
            ("the recorded answer", _completed_run(), True),
            # A restart mints a fresh cycle and puts the generation counter
            # back where it started, so the counter alone would read one
            # cycle's verdict as the next one's.
            ("another cycle", _completed_run(cycle_id=CYCLE_ID + 1), False),
            ("another generation", _completed_run(generation=2), False),
            ("another commit", _completed_run(source_sha=OTHER_SHA), False),
            ("no commit at all", _completed_run(source_sha=""), False),
            ("no result yet", _completed_run(verdict=None), False),
        )
        for name, run, answered in cases:
            with self.subTest(case=name):
                self.assertEqual(run.answers(late_generation()), answered)

    def test_an_incomplete_record_reads_unanswered(self) -> None:
        # A half-written outcome is worse than none: it would suppress the
        # next spawn and then have nothing to announce or create.
        cases = (
            ("a damaged verdict", {KEYS.verdict: DAMAGED_VERDICT}),
            ("a question with no question", {
                KEYS.verdict: str(LateVerdict.QUESTION),
                KEYS.category: str(LateVerdictCategory.UNSAFE_SPLIT),
            }),
            ("a question with no category", {
                KEYS.verdict: str(LateVerdict.QUESTION),
                KEYS.question: ASKED,
            }),
            ("a split with no manifest", {
                KEYS.verdict: str(LateVerdict.SPLIT),
            }),
            ("a split whose manifest is not one", {
                KEYS.verdict: str(LateVerdict.SPLIT),
                KEYS.children: [{TITLE: FIRST_TITLE}],
            }),
        )
        for name, recorded in cases:
            with self.subTest(case=name):
                run = _session._read_late_run(PinnedState(data={
                    KEYS.run_cycle_id: CYCLE_ID,
                    KEYS.source_sha: CANDIDATE_SHA,
                    KEYS.run_generation: GENERATION_NUMBER,
                    **recorded,
                }))

                self.assertFalse(run.answers(late_generation()))

    def test_a_complete_split_reads_answered(self) -> None:
        run = _session._read_late_run(PinnedState(data={
            KEYS.run_cycle_id: CYCLE_ID,
            KEYS.source_sha: CANDIDATE_SHA,
            KEYS.run_generation: GENERATION_NUMBER,
            KEYS.verdict: str(LateVerdict.SPLIT),
            KEYS.children: [recorded_child()],
        }))

        self.assertTrue(run.answers(late_generation()))


if __name__ == "__main__":
    unittest.main()
