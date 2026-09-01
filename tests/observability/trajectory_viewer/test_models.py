# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a record's immutable pieces are built through and read back as."""
from __future__ import annotations

import inspect
import unittest
from dataclasses import FrozenInstanceError

from orchestrator.observability.trajectory_viewer import models
from tests.observability.trajectory_viewer.trajectory_viewer_test_support import (
    ASSISTANT_MESSAGE,
    TOOL_BASH,
    TOOL_CALL,
    TOOL_RESULT,
)


_BODY_KEYWORD = "content"

_BODY = "ls -la"

_TOOL_ID = "t1"

_PROMPT = "prompt"

_OUTPUT = "output"

_INPUT_TOKENS = 12

_OUTPUT_TOKENS = 340

_CACHE_READ_TOKENS = 18240

_CACHE_WRITE_TOKENS = 512


class ConstructionSignatureTest(unittest.TestCase):
    """Both bodied views are built through their declared public shape."""

    def test_a_step_takes_its_fields_positionally(self) -> None:
        step = models.TrajectoryStepView(TOOL_CALL, TOOL_BASH, _TOOL_ID, _BODY, 0)
        self.assertEqual(
            (step.kind, step.name, step.tool_id, step.content, step.turn),
            (TOOL_CALL, TOOL_BASH, _TOOL_ID, _BODY, 0),
        )

    def test_an_entry_takes_its_body_second(self) -> None:
        # The timeline entry orders its fields body-first because a bracket
        # carries a body and nothing else, and the two orders are why each
        # view declares a signature of its own.
        entry = models.TimelineEntry(_PROMPT, _BODY)
        self.assertEqual((entry.kind, entry.content), (_PROMPT, _BODY))

    def test_a_body_is_passed_and_read_as_content(self) -> None:
        # `content` is the keyword the sink writes and the attribute the page
        # reads; the field behind it is named apart so the dataclass can hold
        # both it and the property that answers with it.
        step = models.TrajectoryStepView(kind=TOOL_CALL, content=_BODY)
        entry = models.TimelineEntry(kind=_OUTPUT, content=_BODY)
        self.assertEqual((step.content, step.step_content), (_BODY, _BODY))
        self.assertEqual((entry.content, entry.entry_content), (_BODY, _BODY))

    def test_an_omitted_field_takes_its_default(self) -> None:
        step = models.TrajectoryStepView(TOOL_CALL)
        named = (step.name, step.tool_id, step.content)
        self.assertEqual(named, ("", "", ""))
        self.assertIsNone(step.turn)

    def test_the_reported_signature_is_the_public_one(self) -> None:
        # The generated `__init__` takes `*args, **kwargs`, so what a caller
        # or a doc tool reads the shape off is the declared signature.
        for view, declared in (
            (models.TrajectoryStepView, models.STEP_VIEW_SIGNATURE),
            (models.TimelineEntry, models.TIMELINE_ENTRY_SIGNATURE),
        ):
            with self.subTest(view=view.__name__):
                self.assertEqual(inspect.signature(view), declared)
                self.assertIn(_BODY_KEYWORD, declared.parameters)

    def test_the_field_behind_a_body_is_not_a_keyword(self) -> None:
        # Binding the call against the declared signature is what keeps the
        # internal field name out of the public shape.
        with self.assertRaises(TypeError):
            models.TrajectoryStepView(kind=TOOL_CALL, step_content=_BODY)


class ModelBehaviorTest(unittest.TestCase):
    """The pieces are frozen, and each answers what kind of thing it is."""

    def test_a_view_cannot_be_edited(self) -> None:
        # The page hands one object to a filter, a table, and a detail card,
        # so none of them can edit the record underneath the others.
        for view in (
            models.TrajectoryStepView(TOOL_CALL),
            models.TimelineEntry(_PROMPT),
            models.TurnUsageView(),
            models.RunUsageView(),
        ):
            with self.subTest(view=type(view).__name__), self.assertRaises(FrozenInstanceError):
                view.turn = 1

    def test_a_step_reports_which_half_it_is(self) -> None:
        # A message turn is a step too, so neither half claims it.
        for kind, expected in (
            (TOOL_CALL, (True, False)),
            (TOOL_RESULT, (False, True)),
            (ASSISTANT_MESSAGE, (False, False)),
        ):
            with self.subTest(kind=kind):
                step = models.TrajectoryStepView(kind)
                self.assertEqual((step.is_call, step.is_result), expected)

    def test_an_entry_reports_which_bracket_it_is(self) -> None:
        for kind, expected in (
            (_PROMPT, (True, False)),
            (_OUTPUT, (False, True)),
            (TOOL_CALL, (False, False)),
        ):
            with self.subTest(kind=kind):
                entry = models.TimelineEntry(kind)
                self.assertEqual((entry.is_prompt, entry.is_output), expected)


class UsageTotalTest(unittest.TestCase):
    """Both usage summaries total the same four buckets."""

    def test_the_total_leaves_the_cached_subset_out(self) -> None:
        # Codex reports `cached_tokens` as a subset of its input count, so
        # adding it would bill those tokens twice.
        run_usage = models.RunUsageView(
            input_tokens=_INPUT_TOKENS,
            output_tokens=_OUTPUT_TOKENS,
            cached_tokens=9,
            cache_read_tokens=_CACHE_READ_TOKENS,
            cache_write_tokens=_CACHE_WRITE_TOKENS,
        )
        turn_usage = models.TurnUsageView(
            input_tokens=_INPUT_TOKENS,
            output_tokens=_OUTPUT_TOKENS,
            cache_read_tokens=_CACHE_READ_TOKENS,
            cache_write_tokens=_CACHE_WRITE_TOKENS,
        )
        self.assertEqual(
            run_usage.total_tokens,
            _INPUT_TOKENS + _OUTPUT_TOKENS + _CACHE_READ_TOKENS + _CACHE_WRITE_TOKENS,
        )
        self.assertEqual(turn_usage.total_tokens, run_usage.total_tokens)

    def test_a_summary_with_no_buckets_totals_zero(self) -> None:
        # A record written before the cache buckets existed omits them.
        self.assertEqual(models.RunUsageView().total_tokens, 0)
        self.assertEqual(models.TurnUsageView().total_tokens, 0)


if __name__ == "__main__":
    unittest.main()
