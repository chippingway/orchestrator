# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a record's run summary and per-turn rows are read back as."""
from __future__ import annotations

import unittest
from typing import Any

from orchestrator.observability.trajectory_viewer import parsing
from tests.observability.analytics.analytics_assertions import assert_row_fields
from tests.observability.trajectory_viewer.trajectory_viewer_test_support import (
    ASSISTANT_MESSAGE,
    TOOL_CALL,
    TOOL_EDIT,
    TOOL_RESULT,
    record,
)


_KIND = "kind"

_NAME = "name"

_CONTENT_KEY = "content"

_TOOL_ID = "tool_id"

_TURN = "turn"

_MODEL = "model"

_MODELS = "models"

_TURNS = "turns"

_INPUT_TOKENS = "input_tokens"

_OUTPUT_TOKENS = "output_tokens"

_CACHE_READ = "cache_read_tokens"

_CACHE_WRITE = "cache_write_tokens"

_COST_USD = "cost_usd"

_COST_SOURCE = "cost_source"

_MODEL_CLAUDE = "claude-opus-4-8"

_REPORTED = "reported"

_ESTIMATED = "estimated"

_UNKNOWN_PRICE = "unknown-price"

_DONE = "done"

_USAGE_INPUT = 12

_USAGE_OUTPUT = 340

_USAGE_CACHE_READ = 18240

_USAGE_CACHE_WRITE = 512

_RUN_COST = 0.83

_TURN0_COST = 0.0123

_CODEX_INPUT = 100

_CODEX_OUTPUT = 50


def _usage_record(**overrides: Any) -> dict[str, Any]:
    """A claude line carrying run and per-turn usage plus turn-stamped steps."""
    written = record(
        user_input="fix the parser",
        output=_DONE,
        run_usage={
            _MODELS: [_MODEL_CLAUDE],
            _TURNS: 2,
            _INPUT_TOKENS: _USAGE_INPUT,
            _OUTPUT_TOKENS: _USAGE_OUTPUT,
            "cached_tokens": 0,
            _CACHE_READ: _USAGE_CACHE_READ,
            _CACHE_WRITE: _USAGE_CACHE_WRITE,
            _COST_USD: _RUN_COST,
            _COST_SOURCE: _REPORTED,
        },
        turns=[
            {
                _TURN: 0,
                _MODEL: _MODEL_CLAUDE,
                _INPUT_TOKENS: _USAGE_INPUT,
                _OUTPUT_TOKENS: _USAGE_OUTPUT,
                _CACHE_READ: _USAGE_CACHE_READ,
                _CACHE_WRITE: _USAGE_CACHE_WRITE,
                _COST_USD: _TURN0_COST,
                _COST_SOURCE: _ESTIMATED,
            },
            {
                _TURN: 1,
                _MODEL: _MODEL_CLAUDE,
                _INPUT_TOKENS: 5,
                _OUTPUT_TOKENS: 120,
                _CACHE_READ: 900,
                _CACHE_WRITE: 0,
                _COST_USD: None,
                _COST_SOURCE: _UNKNOWN_PRICE,
            },
        ],
        steps=[
            {_KIND: ASSISTANT_MESSAGE, _TURN: 0, _CONTENT_KEY: "let me look"},
            {_KIND: TOOL_CALL, _NAME: TOOL_EDIT,
             _TOOL_ID: "e1", _TURN: 0, _CONTENT_KEY: "patch"},
            {_KIND: TOOL_RESULT, _TOOL_ID: "e1", _CONTENT_KEY: "ok"},
            {_KIND: ASSISTANT_MESSAGE, _TURN: 1, _CONTENT_KEY: _DONE},
        ],
    )
    written.update(overrides)
    return written


class UsageParsingTest(unittest.TestCase):
    """Run and per-turn usage are read back tolerantly, or not at all."""

    def test_the_whole_summary_is_read_back(self) -> None:
        run = parsing.parse_record(_usage_record(), sequence=0)
        assert run is not None and run.run_usage is not None
        assert_row_fields(self, run.run_usage, {
            _MODELS: (_MODEL_CLAUDE,),
            _INPUT_TOKENS: _USAGE_INPUT,
            _TURNS: 2,
            _COST_SOURCE: _REPORTED,
        })
        # The per-turn rows round-trip, the unpriced one included.
        self.assertEqual(len(run.turns), 2)
        assert_row_fields(self, run.turns[0], {_TURN: 0, _COST_USD: _TURN0_COST})
        assert_row_fields(
            self, run.turns[1], {_COST_USD: None, _COST_SOURCE: _UNKNOWN_PRICE},
        )

    def test_a_step_carries_the_turn_it_was_billed_to(self) -> None:
        run = parsing.parse_record(_usage_record(), sequence=0)
        assert run is not None
        # A tool result is the provider's input, not a billed turn of its own.
        billed = [step.turn for step in run.steps]
        self.assertEqual(billed, [0, 0, None, 1])

    def test_a_line_written_before_usage_existed(self) -> None:
        run = parsing.parse_record(
            record(steps=[{_KIND: TOOL_CALL, _NAME: TOOL_EDIT, _CONTENT_KEY: "ls"}]),
            sequence=0,
        )
        assert run is not None
        self.assertIsNone(run.run_usage)
        self.assertEqual(run.turns, ())
        self.assertIsNone(run.steps[0].turn)

    def test_a_malformed_summary_is_narrowed_away(self) -> None:
        run = parsing.parse_record(
            record(
                run_usage="oops",
                turns=[
                    "not-a-dict",
                    {_TURN: "bad", _MODEL: _MODEL_CLAUDE, _COST_USD: "free"},
                ],
                steps=[{_KIND: TOOL_CALL, _NAME: TOOL_EDIT,
                        _TURN: "nope", _CONTENT_KEY: "x"}],
            ),
            sequence=0,
        )
        assert run is not None
        self.assertIsNone(run.run_usage)
        # The non-object entry is dropped; the readable one survives with its
        # unreadable fields narrowed away rather than raising.
        self.assertEqual(len(run.turns), 1)
        surviving = run.turns[0]
        self.assertIsNone(surviving.turn)
        self.assertIsNone(surviving.cost_usd)
        self.assertIsNone(run.steps[0].turn)

    def test_a_scalar_where_an_array_belongs(self) -> None:
        # A hand-edited line spelling `"turns": 1` must yield an empty section
        # rather than a TypeError when the parse iterates it.
        run = parsing.parse_record(record(turns=1, steps=1), sequence=0)
        assert run is not None
        self.assertEqual((run.turns, run.steps), ((), ()))

    def test_a_summary_with_no_per_turn_detail(self) -> None:
        # Codex records the run summary and no per-turn breakdown, and its
        # summary omits the cache buckets -- the numeric-field 0 default.
        run = parsing.parse_record(
            record(
                backend="codex",
                run_usage={
                    _MODELS: ["gpt-5"],
                    _INPUT_TOKENS: _CODEX_INPUT,
                    _OUTPUT_TOKENS: _CODEX_OUTPUT,
                    _COST_USD: 0.02,
                    _COST_SOURCE: _ESTIMATED,
                },
                steps=[{_KIND: TOOL_CALL, _NAME: "shell", _CONTENT_KEY: "ls"}],
            ),
            sequence=0,
        )
        assert run is not None and run.run_usage is not None
        self.assertEqual(run.turns, ())
        assert_row_fields(self, run.run_usage, {
            _MODELS: ("gpt-5",),
            _INPUT_TOKENS: _CODEX_INPUT,
            _OUTPUT_TOKENS: _CODEX_OUTPUT,
            _CACHE_READ: 0,
        })
        self.assertIsNone(run.steps[0].turn)


if __name__ == "__main__":
    unittest.main()
