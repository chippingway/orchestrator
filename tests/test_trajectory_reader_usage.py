# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Trajectory run- and per-turn usage parsing tests."""

import unittest


from orchestrator import trajectory_reader as tr
from tests.analytics_assertions import assert_row_fields


_KIND = "kind"


_NAME = "name"


_CONTENT_KEY = "content"


_TOOL_ID = "tool_id"


_TURN = "turn"


_INPUT_TOKENS = "input_tokens"


_OUTPUT_TOKENS = "output_tokens"


_COST_USD = "cost_usd"


_COST_SOURCE = "cost_source"


_MODEL = "model"


_MODELS = "models"


_CACHE_READ = "cache_read_tokens"


_TOOL_CALL = "tool_call"


_TOOL_RESULT = "tool_result"


_ASSISTANT_MESSAGE = "assistant_message"


_BACKEND_CLAUDE = "claude"


_BACKEND_CODEX = "codex"


_MODEL_CLAUDE = "claude-opus-4-8"


_REPORTED = "reported"


_UNKNOWN_PRICE = "unknown-price"


_STAGE_IMPLEMENTING = "implementing"


_ROLE_DEVELOPER = "developer"


_TOOL_BASH = "Bash"


_TOOL_EDIT = "Edit"


_T1 = "t1"


_PROMPT_DO_THING = "do the thing"


_DONE = "done"


_LS = "ls"


_TS = "2026-06-20T10:00:00+00:00"


_ISSUE = 42


_USAGE_INPUT = 12


_USAGE_OUTPUT = 340


_USAGE_CACHE_READ = 18240


_USAGE_CACHE_WRITE = 512


_RUN_COST = 0.83


_TURN0_COST = 0.0123


_CODEX_INPUT = 100


_CODEX_OUTPUT = 50


def _record(**overrides):
    record = {
        "ts": _TS,
        "repo": "acme/widgets",
        "issue": _ISSUE,
        "event": "agent_trajectory",
        "stage": _STAGE_IMPLEMENTING,
        "agent_role": _ROLE_DEVELOPER,
        "backend": _BACKEND_CLAUDE,
        "steps": [],
    }
    record.update(overrides)
    return record


def _usage_record(**overrides):
    """A claude record carrying run + per-turn usage and turn-stamped steps."""
    record = _record(
        user_input="fix the parser",
        output=_DONE,
        run_usage={
            _MODELS: [_MODEL_CLAUDE],
            "turns": 2,
            _INPUT_TOKENS: _USAGE_INPUT,
            _OUTPUT_TOKENS: _USAGE_OUTPUT,
            "cached_tokens": 0,
            _CACHE_READ: _USAGE_CACHE_READ,
            "cache_write_tokens": _USAGE_CACHE_WRITE,
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
                "cache_write_tokens": _USAGE_CACHE_WRITE,
                _COST_USD: _TURN0_COST,
                _COST_SOURCE: "estimated",
            },
            {
                _TURN: 1,
                _MODEL: _MODEL_CLAUDE,
                _INPUT_TOKENS: 5,
                _OUTPUT_TOKENS: 120,
                _CACHE_READ: 900,
                "cache_write_tokens": 0,
                _COST_USD: None,
                _COST_SOURCE: _UNKNOWN_PRICE,
            },
        ],
        steps=[
            {_KIND: _ASSISTANT_MESSAGE, _TURN: 0, _CONTENT_KEY: "let me look"},
            {_KIND: _TOOL_CALL, _NAME: _TOOL_EDIT, _TOOL_ID: "e1", _TURN: 0, _CONTENT_KEY: "patch"},
            {_KIND: _TOOL_RESULT, _TOOL_ID: "e1", _CONTENT_KEY: "ok"},
            {_KIND: _ASSISTANT_MESSAGE, _TURN: 1, _CONTENT_KEY: _DONE},
        ],
    )
    record.update(overrides)
    return record


class UsageParsingTest(unittest.TestCase):
    """The reader parses run- and per-turn usage tolerantly."""

    def test_full_usage_round_trips(self) -> None:
        run = tr.parse_record(_usage_record(), seq=0)
        assert run is not None and run.run_usage is not None
        # Run summary round-trips.
        assert_row_fields(
            self,
            run.run_usage,
            {
                _MODELS: (_MODEL_CLAUDE,),
                "input_tokens": _USAGE_INPUT,
                "turns": 2,
                _COST_SOURCE: _REPORTED,
            },
        )
        # Per-turn breakdown round-trips, including the unpriced turn.
        self.assertEqual(len(run.turns), 2)
        assert_row_fields(self, run.turns[0], {"turn": 0, _COST_USD: _TURN0_COST})
        assert_row_fields(
            self,
            run.turns[1],
            {_COST_USD: None, _COST_SOURCE: _UNKNOWN_PRICE},
        )

    def test_step_turn_is_parsed_when_recorded(self) -> None:
        run = tr.parse_record(_usage_record(), seq=0)
        assert run is not None
        # Billed steps carry their turn; the tool_result input stays None.
        self.assertEqual(
            [step.turn for step in run.steps],
            [0, 0, None, 1],
        )

    def test_pre_usage_record_is_compatible(self) -> None:
        # A record written before the usage feature: no run_usage, no
        # turns, no step.turn. It parses with empty defaults rather than
        # dropping the record or raising.
        run = tr.parse_record(
            _record(
                user_input=_PROMPT_DO_THING,
                output=_DONE,
                steps=[{_KIND: _TOOL_CALL, _NAME: _TOOL_BASH, _TOOL_ID: _T1, _CONTENT_KEY: _LS}],
            ),
            seq=0,
        )
        assert run is not None
        self.assertIsNone(run.run_usage)
        self.assertEqual(run.turns, ())
        self.assertIsNone(run.steps[0].turn)

    def test_malformed_usage_is_tolerated(self) -> None:
        # run_usage not a dict -> None; a non-dict turns entry dropped; a
        # non-numeric cost / turn index coerced away, never raising.
        run = tr.parse_record(
            _record(
                run_usage="oops",
                turns=[
                    "not-a-dict",
                    {_TURN: "bad", _MODEL: _MODEL_CLAUDE, _COST_USD: "free"},
                ],
                steps=[{_KIND: _TOOL_CALL, _NAME: _TOOL_EDIT, _TURN: "nope", _CONTENT_KEY: "x"}],
            ),
            seq=0,
        )
        assert run is not None
        self.assertIsNone(run.run_usage)
        # The non-dict entry is dropped; the malformed one survives with its
        # bad fields coerced away.
        self.assertEqual(len(run.turns), 1)
        self.assertIsNone(run.turns[0].turn)
        self.assertIsNone(run.turns[0].cost_usd)
        self.assertIsNone(run.steps[0].turn)

    def test_non_list_array_fields_are_tolerated(self) -> None:
        # A hand-edited record with a scalar where an array is expected
        # (`"turns": 1`, `"steps": 1`) must yield an empty section, not a
        # `TypeError` when the reader iterates it.
        run = tr.parse_record(_record(turns=1, steps=1), seq=0)
        assert run is not None
        self.assertEqual(run.turns, ())
        self.assertEqual(run.steps, ())

    def test_codex_run_usage_without_per_turn_detail(self) -> None:
        # Codex records the run summary but no per-turn breakdown: run_usage
        # present, turns empty, every step.turn None. Its run_usage also
        # omits the cache buckets, exercising the numeric-field 0 default.
        run = tr.parse_record(
            _record(
                backend=_BACKEND_CODEX,
                run_usage={
                    _MODELS: ["gpt-5"],
                    _INPUT_TOKENS: _CODEX_INPUT,
                    _OUTPUT_TOKENS: _CODEX_OUTPUT,
                    _COST_USD: 0.02,
                    _COST_SOURCE: "estimated",
                },
                steps=[{_KIND: _TOOL_CALL, _NAME: "shell", _CONTENT_KEY: _LS}],
            ),
            seq=0,
        )
        assert run is not None and run.run_usage is not None
        self.assertEqual(run.turns, ())
        assert_row_fields(
            self,
            run.run_usage,
            {
                _MODELS: ("gpt-5",),
                "input_tokens": _CODEX_INPUT,
                "output_tokens": _CODEX_OUTPUT,
                _CACHE_READ: 0,
            },
        )
        self.assertIsNone(run.steps[0].turn)
