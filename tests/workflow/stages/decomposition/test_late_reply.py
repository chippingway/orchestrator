# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The late reply's fenced block, and what the initial parser still means."""
from __future__ import annotations

import unittest

from orchestrator.workflow.late_split.events import LateVerdictCategory
from orchestrator.workflow.late_split.models import LateVerdict
from orchestrator.workflow.stages.decomposition import manifest as _manifest
from orchestrator.workflow.stages.decomposition import late_reply as _late_reply

from tests.workflow.fixtures import _manifest as _initial_block
from tests.workflow.stages.decomposition.late_test_support import (
    QUESTION_REPLY,
    SINGLE_REPLY,
    SPLIT_REPLY,
    late_block,
)

SINGLE_PAYLOAD = '{"decision": "single", "rationale": "fits"}'

# One reply per way a late block fails to be an answer, each with the fragment
# the park message has to carry.
_REFUSED_REPLIES = (
    ("no block at all", "the late decomposer decided single", "no outcome"),
    ("two blocks", f"{SINGLE_REPLY}\n{SINGLE_REPLY}", "exactly one"),
    ("prose after", f"{SINGLE_REPLY}\nand one more thought", "final block"),
    ("not json", late_block("{decision: single}"), "invalid JSON"),
    ("not an object", late_block('["single"]'), "not a JSON object"),
    ("no decision", late_block("{}"), "decision must be"),
    ("unknown decision", late_block('{"decision": "maybe"}'), "decision must"),
    (
        "split with no children",
        late_block('{"decision": "split", "children": []}'),
        "non-empty children",
    ),
    (
        "split with a cycle",
        late_block(
            '{"decision": "split", "children": ['
            '{"title": "A", "body": "a", "depends_on": [1]},'
            '{"title": "B", "body": "b", "depends_on": [0]}]}'
        ),
        "cycle",
    ),
    (
        "question with nothing asked",
        late_block('{"decision": "question", "category": "unsafe_split"}'),
        "non-empty question",
    ),
)


class LateReplyTest(unittest.TestCase):
    """What each of the three structured outcomes parses to."""

    def test_single_carries_rationale_and_category(self) -> None:
        adjudication, error = _late_reply._parse_late_reply(SINGLE_REPLY)

        self.assertIsNone(error)
        self.assertEqual(adjudication.verdict, LateVerdict.SINGLE)
        self.assertEqual(
            adjudication.category, LateVerdictCategory.GENERATED_ARTIFACTS,
        )
        self.assertEqual(adjudication.rationale, "one coherent change")
        self.assertEqual(adjudication.children, ())
        self.assertIsNone(adjudication.child_count)

    def test_split_carries_the_children_it_proposed(self) -> None:
        adjudication, error = _late_reply._parse_late_reply(SPLIT_REPLY)

        self.assertIsNone(error)
        self.assertEqual(adjudication.verdict, LateVerdict.SPLIT)
        self.assertEqual(adjudication.child_count, 2)
        self.assertEqual(
            [child["title"] for child in adjudication.children], ["A", "B"],
        )
        self.assertEqual(adjudication.children[1]["depends_on"], [0])

    def test_question_carries_what_it_asks(self) -> None:
        adjudication, error = _late_reply._parse_late_reply(QUESTION_REPLY)

        self.assertIsNone(error)
        self.assertEqual(adjudication.verdict, LateVerdict.QUESTION)
        self.assertEqual(
            adjudication.category, LateVerdictCategory.SCOPE_AMBIGUOUS,
        )
        self.assertEqual(
            adjudication.question, "which half of this is in scope?",
        )

    def test_an_unknown_category_records_as_such(self) -> None:
        # The vocabulary is widened in review, never by what an agent wrote,
        # and a question with no category still has to have one.
        cases = (
            ('"category": "the diff smells", ', LateVerdictCategory.UNKNOWN),
            ("", LateVerdictCategory.UNKNOWN),
        )
        for declared, expected in cases:
            with self.subTest(declared=declared):
                adjudication, error = _late_reply._parse_late_reply(
                    late_block(
                        '{"decision": "question", '
                        f'{declared}"question": "which half?"}}'
                    ),
                )
                self.assertIsNone(error)
                self.assertEqual(adjudication.category, expected)

    def test_an_absent_category_stays_absent(self) -> None:
        adjudication, error = _late_reply._parse_late_reply(
            late_block(SINGLE_PAYLOAD),
        )

        self.assertIsNone(error)
        self.assertIsNone(adjudication.category)

    def test_every_refusal_names_why(self) -> None:
        for name, reply, fragment in _REFUSED_REPLIES:
            with self.subTest(case=name):
                adjudication, error = _late_reply._parse_late_reply(reply)
                self.assertIsNone(adjudication)
                self.assertIn(fragment, error)


class ModeSeparationTest(unittest.TestCase):
    """Neither parser reads the other's block, and neither changed."""

    def test_an_initial_manifest_is_not_a_late_reply(self) -> None:
        adjudication, error = _late_reply._parse_late_reply(
            _initial_block(SINGLE_PAYLOAD),
        )

        self.assertIsNone(adjudication)
        self.assertIn("no outcome", error)

    def test_a_late_reply_is_not_an_initial_manifest(self) -> None:
        # `(None, None)` is the initial contract's "the decomposer asked a
        # question", which a late block must not turn into.
        parsed, error = _manifest._parse_manifest(SINGLE_REPLY)

        self.assertIsNone(parsed)
        self.assertIsNone(error)

    def test_the_initial_envelope_is_unchanged(self) -> None:
        cases = (
            (
                _initial_block(SINGLE_PAYLOAD) * 2,
                "expected exactly one orchestrator-manifest block, found 2",
            ),
            (
                f"{_initial_block(SINGLE_PAYLOAD)}\ntrailing",
                "orchestrator-manifest must be the final block; "
                "found content after the closing fence",
            ),
        )
        for reply, expected in cases:
            with self.subTest(expected=expected):
                parsed, error = _manifest._parse_manifest(reply)
                self.assertIsNone(parsed)
                self.assertEqual(error, expected)


if __name__ == "__main__":
    unittest.main()
