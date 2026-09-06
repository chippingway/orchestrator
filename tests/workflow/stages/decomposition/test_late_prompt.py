# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What the late-only prompt has to put in front of the adjudicator."""
from __future__ import annotations

import unittest

from orchestrator.workflow.late_split.events import LateVerdictCategory
from orchestrator.workflow.late_split.models import MAX_LINEAGE_DEPTH
from orchestrator.workflow.stages.decomposition import late_prompt as _prompt, late_reply as _late_reply
from orchestrator.workflow.stages.decomposition.late_reply import _SPLIT_BLOCKER
from orchestrator.workflow.stages.decomposition.validation import _MAX_CHILDREN
from tests.support.fakes import make_issue
from tests.workflow.fixtures import _TEST_SPEC
from tests.workflow.stages.decomposition.late_test_support import (
    ADDITIONS,
    BASE_SHA,
    CANDIDATE_SHA,
    LATE_FENCE,
    LATE_ISSUE_NUMBER,
    ROOT_ISSUE,
    SCOPE,
    SPLIT_BLOCKER,
    THRESHOLD,
    late_block,
    late_generation,
)

ISSUE_TITLE = "make the thing work"
ISSUE_BODY = "the original ask, as a human wrote it"
THREAD = "@alice: please keep the migration out of it"


def _prompt_for(generation=None) -> str:
    issue = make_issue(
        LATE_ISSUE_NUMBER, title=ISSUE_TITLE, body=ISSUE_BODY,
    )
    return _prompt._build_late_decompose_prompt(
        _TEST_SPEC,
        issue,
        THREAD,
        late_generation() if generation is None else generation,
        [],
    )


class LatePromptContextTest(unittest.TestCase):
    """The prompt carries the whole question, not just the size."""

    def test_it_carries_the_whole_question(self) -> None:
        for fragment in (
            ISSUE_TITLE,
            ISSUE_BODY,
            THREAD,
            SCOPE,
            f"git diff {BASE_SHA}...{CANDIDATE_SHA}",
            f"candidate commit: {CANDIDATE_SHA}",
            f"base commit: {BASE_SHA}",
            f"{ADDITIONS} lines",
            f"ceiling of {THRESHOLD}",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, _prompt_for())

    def test_it_says_the_work_exists_read_only(self) -> None:
        composed = _prompt_for()

        self.assertIn("ALREADY implemented", composed)
        self.assertIn("COMMITTED", composed)
        self.assertIn("read-only", composed)

    def test_the_diff_is_the_measured_range(self) -> None:
        # Two dots would show everything that happened on the base since the
        # candidate branched, so a diverged history would put the agent on
        # changes nobody measured.
        composed = _prompt_for()

        self.assertNotIn(f"{BASE_SHA}..{CANDIDATE_SHA}`", composed)
        self.assertIn("THREE dots, not two", composed)

    def test_it_places_the_issue_in_its_lineage(self) -> None:
        composed = _prompt_for()

        self.assertIn(f"root issue: #{ROOT_ISSUE}", composed)
        self.assertIn(f"this issue: #{LATE_ISSUE_NUMBER}", composed)
        self.assertIn(f"lineage depth: 1 of at most {MAX_LINEAGE_DEPTH}", composed)


class LatePromptContractTest(unittest.TestCase):
    """The outcomes, the bounds, and the block the parser then reads."""

    def test_it_names_the_fence_and_decisions(self) -> None:
        composed = _prompt_for()

        self.assertIn(LATE_FENCE, composed)
        for decision in ('"single"', '"split"', '"question"'):
            with self.subTest(decision=decision):
                self.assertIn(decision, composed)

    def test_it_states_the_bounds_it_is_judged_by(self) -> None:
        # Both numbers are read back off the owners that enforce them, so the
        # bound an agent is told cannot drift from the bound it is judged by.
        composed = _prompt_for()

        self.assertIn(f"at most {_MAX_CHILDREN} entries", composed)
        self.assertIn(f"at most {MAX_LINEAGE_DEPTH}", composed)

    def test_it_offers_the_closed_category_set(self) -> None:
        # Read off the closed vocabulary, so a category widened in review
        # reaches the prompt with it. `unknown` is what this binary answers
        # for a spelling it does not know, never one an agent may choose.
        offered = {
            member for member in LateVerdictCategory
            if f"`{member}`" in _prompt._CATEGORIES
        }

        self.assertEqual(
            offered,
            set(LateVerdictCategory) - {LateVerdictCategory.UNKNOWN},
        )
        self.assertIn(_prompt._CATEGORIES, _prompt_for())

    def test_generated_artifacts_get_both_answers(self) -> None:
        # The false positive and the real finding differ by whether the
        # artifacts belong in the commit, which is a human's call.
        composed = _prompt_for()

        self.assertIn('`single` with `"category": "generated_artifacts"`', composed)
        self.assertIn("should NOT have been committed", composed)

    def test_the_single_it_asks_for_reads_explained(self) -> None:
        # The two halves of one contract: the key the prompt states is the
        # key the parser reads, so a reply that did what it was asked carries
        # its explanation rather than falling back to the stand-in a record
        # with none answers with. Asking for a spelling nothing reads would
        # leave every conforming `single` saying why it was not split and
        # nobody keeping the sentence.
        self.assertIn(f'`"{_SPLIT_BLOCKER}"`', _prompt_for())

        adjudication, _refusal = _late_reply._parse_late_reply(late_block(
            f'{{"decision": "single", "{_SPLIT_BLOCKER}": "{SPLIT_BLOCKER}"}}',
        ))

        self.assertEqual(
            adjudication.split_blocker_explanation, SPLIT_BLOCKER,
        )

    def test_the_split_rule_follows_the_lineage_depth(self) -> None:
        cases = (
            (0, True), (MAX_LINEAGE_DEPTH - 1, True),
            (MAX_LINEAGE_DEPTH, False), (None, False),
        )
        for depth, offered in cases:
            with self.subTest(depth=depth):
                composed = _prompt_for(late_generation(lineage_depth=depth))
                self.assertEqual("`split` is available" in composed, offered)
                self.assertEqual(
                    "may NOT split further" in composed, not offered,
                )

    def test_an_unreadable_depth_reads_unknown(self) -> None:
        composed = _prompt_for(late_generation(lineage_depth=None))

        self.assertIn("lineage depth: unknown", composed)


if __name__ == "__main__":
    unittest.main()
