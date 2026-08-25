# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The late fields' pinned round trip, legacy compatibility, and restart."""
from __future__ import annotations

import json
import unittest
from types import MappingProxyType

from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.late_split import formats as _formats
from orchestrator.workflow.late_split import state as _late_state
from orchestrator.workflow.late_split.models import LateGeneration, LatePhase

from tests.workflow.late_split import generation_test_support as _support

_LEGACY_STATE = MappingProxyType({
    "dev_agent": "codex",
    "branch": "orchestrator/issue-7",
    "user_content_hash": "abc",
})

_RESOURCES_KEY = "late_resources"
_CYCLE_KEY = "late_cycle_id"
_DEPTH_KEY = "late_lineage_depth"
_CANDIDATE_KEY = "late_candidate_sha"
_BASE_KEY = "late_base_sha"
_TITLE_HASH_KEY = "late_title_body_hash"
_COMMENT_HASH_KEY = "late_comment_hash"

# Hex of the wrong length for the field claiming it: an abbreviation no commit
# this domain froze is spelled as, one character short of an object id, one
# past it, and a digest truncated to a commit's length or by a character.
_ABBREVIATION = "a1b2c3d"
_ONE_SHORT = "a" * (_support.SHA_LENGTH - 1)
_ONE_LONG = "b" * (_support.SHA_LENGTH + 1)
_COMMIT_SHAPED = "c" * _support.SHA_LENGTH
_TRUNCATED_DIGEST = "d" * (_support.DIGEST_LENGTH - 1)

# One damaged value per field contract: an identity that is not positive, a
# measurement that is not a count, a commit field that is not spelled like
# one, a depth outside the lineage, and a restart target no restart applies.
_NOT_LIVE_STATE = (
    ("late_root_issue", 0),
    ("late_current_issue", -9),
    ("late_generation", -1),
    ("late_threshold", -1),
    ("late_additions", -4000),
    (_CANDIDATE_KEY, "rationale: inspect /srv/private/key"),
    (_BASE_KEY, "HEAD~1"),
    (_TITLE_HASH_KEY, "not a digest"),
    (_COMMENT_HASH_KEY, "zzz"),
    # Hex, but not the length the field's own contract is: an abbreviated
    # commit is not one this domain froze, and a truncated digest is not a
    # hash of anything a fingerprint could be compared against.
    (_CANDIDATE_KEY, _ABBREVIATION),
    (_CANDIDATE_KEY, _ONE_SHORT),
    (_BASE_KEY, _ONE_LONG),
    (_TITLE_HASH_KEY, _COMMIT_SHAPED),
    (_COMMENT_HASH_KEY, _TRUNCATED_DIGEST),
    ("late_comment_watermark_id", 0),
    ("late_plan_pr_number", -3),
    (_DEPTH_KEY, 9),
    ("late_restart_target", "workflow:done"),
    ("late_restart_cycle_id", 0),
    ("late_restart_predecessor", -2),
)

_KIND_KEY = "kind"
def _damaged(key: str, damaged) -> PinnedState:
    """A recorded cycle carrying one field a reader must refuse."""
    return PinnedState(state_data={_CYCLE_KEY: _support.CYCLE_ID, key: damaged})


def _written(generation: LateGeneration) -> PinnedState:
    state = PinnedState(comment_id=1, state_data=dict(_LEGACY_STATE))
    _late_state.write_late_generation(state, generation)
    return state


class RoundTripTest(unittest.TestCase):
    """What a generation is written as is what the next tick reads back."""

    def test_every_field_survives_a_round_trip(self) -> None:
        generation = _support.full_generation()
        self.assertEqual(
            _late_state.read_late_generation(_written(generation)),
            generation,
        )

    def test_a_root_generation_keeps_its_depth(self) -> None:
        # Depth 0 is a root, not an absent field: dropping it would read back
        # the same as never having recorded a lineage at all.
        rooted = LateGeneration(cycle_id=1, current_issue=9, lineage_depth=0)
        state = _written(rooted)
        self.assertIn(_DEPTH_KEY, state.data)
        self.assertEqual(_late_state.read_late_generation(state), rooted)

    def test_the_written_state_is_json_safe(self) -> None:
        # The pinned comment is written with `json.dumps`, so a typed member
        # that reached it as anything but its wire string would raise there
        # rather than here.
        written = json.loads(json.dumps(_written(_support.full_generation()).data))
        self.assertEqual(written["late_phase"], "snapshotting")
        self.assertEqual(written["late_cancelled_phase"], "splitting")
        self.assertEqual(
            written[_RESOURCES_KEY],
            [{
                _KIND_KEY: "snapshot_ref",
                "target": _support.SNAPSHOT_REF,
                "state": "retained",
            }],
        )

    def test_a_cleared_field_leaves_no_stale_value(self) -> None:
        state = _written(_support.full_generation())
        _late_state.write_late_generation(
            state,
            LateGeneration(cycle_id=_support.CYCLE_ID, current_issue=9),
        )
        self.assertNotIn("late_candidate_sha", state.data)
        self.assertNotIn("late_cancelled", state.data)

    def test_other_stages_keys_are_untouched(self) -> None:
        state = _written(_support.full_generation())
        _late_state.clear_late_generation(state)
        self.assertEqual(state.data, _LEGACY_STATE)


class FieldContractTest(unittest.TestCase):
    """Each field is read for what it has to be, not for its Python type."""

    def test_a_field_is_read_for_what_it_has_to_be(self) -> None:
        # A hand-edited comment gets no live state out of a value that is not
        # what the field is: a negative measurement is not a measurement, a
        # non-positive identity is not one, and text that is not spelled like
        # a commit is not one. Every one reads back absent.
        for key, damaged in _NOT_LIVE_STATE:
            with self.subTest(key=key, damaged=damaged):
                self.assertEqual(
                    _support.read_state(_damaged(key, damaged)),
                    LateGeneration(cycle_id=_support.CYCLE_ID),
                )

    def test_a_whole_commit_and_digest_are_kept(self) -> None:
        # The other direction of the length rule: both hashes git writes are
        # commits, and a whole SHA-256 digest is a fingerprint.
        for length in sorted(_formats.COMMIT_LENGTHS):
            with self.subTest(length=length):
                frozen = "a" * length
                state = PinnedState(state_data={
                    _CYCLE_KEY: _support.CYCLE_ID,
                    _CANDIDATE_KEY: frozen,
                    _COMMENT_HASH_KEY: _support.COMMENT_HASH,
                })
                read_back = _support.read_state(state)
                self.assertEqual(read_back.candidate_sha, frozen)
                self.assertEqual(read_back.comment_hash, _support.COMMENT_HASH)

    def test_a_negative_measurement_is_not_oversized(self) -> None:
        # The reading that would otherwise put a candidate through the gate:
        # a threshold of -1 beside an additions of 0.
        state = PinnedState(state_data={
            _CYCLE_KEY: _support.CYCLE_ID,
            "late_threshold": -1,
            "late_additions": 0,
        })
        read_back = _support.read_state(state)
        self.assertIsNone(read_back.threshold)
        self.assertFalse(read_back.is_oversized)

    def test_only_the_literal_flag_is_set(self) -> None:
        # `bool("false")` is True, so reading a flag for its truthiness would
        # arm a cancellation, or a pending restart, that nobody wrote.
        for key in ("late_cancelled", "late_restart_pending"):
            for damaged in ("false", "no", 0, [], 1):
                with self.subTest(key=key, damaged=damaged):
                    self.assertEqual(
                        _support.read_state(_damaged(key, damaged)),
                        LateGeneration(cycle_id=_support.CYCLE_ID),
                    )

    def test_a_damaged_field_is_never_written_back(self) -> None:
        # What a read refuses, a write must not preserve: the next tick would
        # read the value this one declined to act on.
        for key, damaged in _NOT_LIVE_STATE:
            with self.subTest(key=key, damaged=damaged):
                self.assertNotIn(
                    key,
                    _support.rewritten_state(_damaged(key, damaged)).data,
                )


class LegacyCompatibilityTest(unittest.TestCase):
    """An issue that never entered the late gate needs no migration."""

    def test_no_late_fields_reads_as_absent(self) -> None:
        state = PinnedState(state_data=dict(_LEGACY_STATE))
        read_back = _support.read_state(state)
        self.assertEqual(read_back, LateGeneration())
        self.assertFalse(read_back.is_present)

    def test_writing_an_absent_generation_is_a_no_op(self) -> None:
        # The whole compatibility claim: a handler that reads and writes late
        # state on every issue leaves a legacy pinned comment as it found it.
        state = PinnedState(state_data=dict(_LEGACY_STATE))
        self.assertEqual(
            _support.rewritten_state(state).data, _LEGACY_STATE,
        )

    def test_a_cycle_less_record_is_not_written(self) -> None:
        # Without a cycle nothing could correlate the record to an audit line
        # or a child's lineage, so the fields are cleared instead.
        state = _written(_support.full_generation())
        _late_state.write_late_generation(
            state, LateGeneration(current_issue=9, phase=LatePhase.MEASURING),
        )
        self.assertEqual(state.data, _LEGACY_STATE)

    def test_unreadable_fields_read_as_absent(self) -> None:
        # A hand-edited comment, or one an older binary wrote differently:
        # every field falls back to its own default rather than raising on a
        # tick that has committed work to reconcile. The two ledgers are the
        # deliberate exception -- an obligation is not absent just because it
        # could not be typed -- so they are excluded here and covered by
        # `test_ledgers.py`.
        state = PinnedState(state_data={
            _CYCLE_KEY: "two",
            _DEPTH_KEY: None,
            "late_phase": "sharpening",
        })
        self.assertEqual(
            _support.read_state(state), LateGeneration(),
        )

    def test_a_damaged_depth_does_not_read_as_a_root(self) -> None:
        # The cap is only worth what its field is: a recorded cycle at the
        # bound whose depth is damaged must not read back as depth 0 and
        # split again. Unknown is the answer, and unknown may not split.
        for damaged in ("corrupt", None, [3], {}):
            with self.subTest(damaged=damaged):
                state = PinnedState(state_data={
                    _CYCLE_KEY: _support.CYCLE_ID,
                    _DEPTH_KEY: damaged,
                })
                read_back = _support.read_state(state)
                self.assertIsNone(read_back.lineage_depth)
                self.assertFalse(read_back.may_split)

    def test_a_damaged_depth_is_never_normalized(self) -> None:
        # The write must not normalize the gap away either, or the next tick
        # would read the 0 this one refused to infer.
        state = PinnedState(state_data={
            _CYCLE_KEY: _support.CYCLE_ID,
            _DEPTH_KEY: "corrupt",
        })
        self.assertNotIn(_DEPTH_KEY, _support.rewritten_state(state).data)

if __name__ == "__main__":
    unittest.main()
