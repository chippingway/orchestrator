# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The post-publication entry a generation records, and what it may not be."""
from __future__ import annotations

import unittest
from dataclasses import replace

from orchestrator.workflow.late_split.formats import InvalidLateValue
from orchestrator.workflow.state import WorkflowLabel

from tests.workflow.late_split import generation_test_support as _support

_STAGE = "stage"
_PR_NUMBER = "pr_number"
_PUBLISHED_SHA = "published_sha"

# What each of the three fields reads back as once a hand edit has taken it,
# keyed by the name on the record rather than the argument that set it.
_UNNAMED_CONTEXT = (
    ("source_stage", None),
    ("published_pr_number", None),
    (_PUBLISHED_SHA, ""),
)


def _entered_at(**overrides) -> dict:
    """The whole of what a post-publication entry names, one field swapped."""
    named = {
        _STAGE: _support.SOURCE_STAGE,
        _PR_NUMBER: _support.PUBLISHED_PR_NUMBER,
        _PUBLISHED_SHA: _support.PUBLISHED_SHA,
    }
    return {**named, **overrides}


class PublicationEntryTest(unittest.TestCase):
    """What a post-publication entry has to name to be recorded as one."""

    def test_an_entry_names_what_was_published(self) -> None:
        entered = _support.measured_generation().with_publication(
            **_entered_at(),
        )

        self.assertTrue(entered.post_publication)
        self.assertIs(entered.source_stage, WorkflowLabel.IN_REVIEW)
        self.assertEqual(
            entered.published_pr_number, _support.PUBLISHED_PR_NUMBER,
        )
        self.assertEqual(entered.published_sha, _support.PUBLISHED_SHA)
        self.assertTrue(entered.has_publication_context)

    def test_saying_nothing_is_pre_publication(self) -> None:
        # The absence is the answer rather than a gap, which is what lets a
        # record written without this group stay valid untouched.
        recorded = _support.measured_generation()

        self.assertFalse(recorded.post_publication)
        self.assertFalse(recorded.has_publication_context)

    def test_a_stage_is_kept_as_the_state_it_names(self) -> None:
        # The wire spelling a pinned comment holds is the label itself, and
        # what the record keeps is the member a later tick acts on.
        entered = _support.measured_generation().with_publication(
            **_entered_at(stage=str(WorkflowLabel.FIXING)),
        )

        self.assertIs(entered.source_stage, WorkflowLabel.FIXING)

    def test_an_entry_it_cannot_name_is_refused(self) -> None:
        # The pinned write drops what it cannot type, so a value accepted
        # here would leave the marker standing over a context nothing could
        # reconcile: a state this workflow has no label for, a pull request
        # nobody can ask GitHub about, or a head that is not a commit.
        refused = (
            (_STAGE, "workflow:sharpening"),
            (_STAGE, None),
            (_STAGE, _support.PUBLISHED_PR_NUMBER),
            (_PR_NUMBER, 0),
            (_PR_NUMBER, True),
            (_PR_NUMBER, "34"),
            (_PUBLISHED_SHA, "a1b2c3d"),
            (_PUBLISHED_SHA, ""),
            (_PUBLISHED_SHA, None),
        )
        for field, damaged in refused:
            with self.subTest(field=field, damaged=damaged):
                with self.assertRaises(InvalidLateValue):
                    _support.measured_generation().with_publication(
                        **_entered_at(**{field: damaged}),
                    )

    def test_the_marker_alone_names_no_publication(self) -> None:
        # Every field beside the flag is read fail-closed, so a hand-edited
        # or older pinned comment can leave the marker with a pull request
        # nothing can name, a head no branch is compared against, or a stage
        # nothing could put the issue back into. None of the three can be
        # recovered from anywhere else on the issue.
        entered = _support.measured_generation().with_publication(
            **_entered_at(),
        )
        for field, gone in _UNNAMED_CONTEXT:
            with self.subTest(field=field):
                damaged = replace(entered, **{field: gone})

                self.assertTrue(damaged.post_publication)
                self.assertFalse(damaged.has_publication_context)


if __name__ == "__main__":
    unittest.main()
