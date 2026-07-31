# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Analytics trajectory budget tests."""

import json


import tempfile


import unittest


from pathlib import Path


from unittest.mock import patch


from orchestrator.observability.usage import trajectory as _usage_trajectory
from orchestrator.observability.usage import trajectory_models as _usage_records


from tests.analytics_reload_helpers import reload_analytics as _reload


from tests.analytics_jsonl_helpers import (
    read_text as _read_text,
    read_records as _read_records,
)


from tests.analytics_trajectory_cases import (
    claude_multistep_stdout as _claude_multistep_stdout,
)


from tests.observability.analytics.trajectories import (
    trajectories_test_support as _support,
)

_ANALYTICS_FILENAME_ALTERNATE = _support.ANALYTICS_FILENAME_ALTERNATE


_CLAUDE = _support.CLAUDE


_CLAUDE_MODEL = _support.CLAUDE_MODEL


_PROMPT_TEXT = _support.PROMPT_TEXT


_RUN_USAGE_KEY = _support.RUN_USAGE_KEY


_STEPS_KEY = _support.STEPS_KEY


_TOOL_CALL_KIND = _support.TOOL_CALL_KIND


_TRAJECTORY_FILENAME = _support.TRAJECTORY_FILENAME


_TRUNCATED_KEY = _support.TRUNCATED_KEY


_TURNS_KEY = _support.TURNS_KEY


_RECORD_BUDGET = "_TRAJECTORY_RECORD_BUDGET"


_DROPS_EXCESS_STEPS_OBJECT_ARGUMENT = 2000


_DROPS_EXCESS_STEPS_RESULT_TEXT = 20


_BUDGET_TOOL_PAIR_COUNT = 5


_MANY_TURNS_COUNT = 5_000


_METADATA_ONLY_STEP_COUNT = 10_000


def _emit_stubbed_trajectory(test_case, analytics, trajectory) -> tuple[str, dict]:
    with tempfile.TemporaryDirectory() as temp_dir:
        trajectory_path = Path(temp_dir) / _TRAJECTORY_FILENAME
        with patch.object(
            _usage_trajectory,
            "parse_agent_trajectory",
            return_value=trajectory,
        ):
            test_case._emit(
                analytics,
                stdout="",
                prompt=_PROMPT_TEXT,
                traj_path=trajectory_path,
                analytics_path=Path(temp_dir) / _ANALYTICS_FILENAME_ALTERNATE,
            )
        raw_record = _read_text(trajectory_path)
    return raw_record, json.loads(raw_record)


class RecordAgentExitTrajectoryBudgetTest(_support.RecordAgentExitTrajectorySupport):
    def test_total_record_budget_drops_excess_steps(self) -> None:
        # When the cumulative redacted content crosses the record budget the
        # remaining steps are dropped and `truncated` is set, so one runaway
        # run cannot write an unbounded JSONL line.
        _, analytics = _reload()
        with (
            tempfile.TemporaryDirectory() as td,
            patch.object(analytics, _RECORD_BUDGET, _DROPS_EXCESS_STEPS_OBJECT_ARGUMENT),
        ):
            t_path = Path(td) / _TRAJECTORY_FILENAME
            self._emit(
                analytics,
                stdout=_claude_multistep_stdout(
                    n_steps=_BUDGET_TOOL_PAIR_COUNT,
                    result_text="ten-chars!" * _DROPS_EXCESS_STEPS_RESULT_TEXT,
                ),
                traj_path=t_path,
                analytics_path=Path(td) / _ANALYTICS_FILENAME_ALTERNATE,
            )
            rec = _read_records(t_path)[0]
            self.assertTrue(rec[_TRUNCATED_KEY])
            # 5 pairs => 10 steps emitted; the budget dropped the tail but
            # kept a prefix.
            self.assertGreater(len(rec[_STEPS_KEY]), 0)
            self.assertLess(
                len(rec[_STEPS_KEY]),
                _BUDGET_TOOL_PAIR_COUNT * 2,
            )
            # The 5 small per-turn entries fit under the budget (they are drawn
            # down before the steps), so all are kept while the step tail is
            # dropped; a turns array that itself overflows is truncated too
            # (see test_turns_array_respects_total_budget).
            self.assertEqual(
                len(rec[_TURNS_KEY]),
                _BUDGET_TOOL_PAIR_COUNT,
            )
            self.assertIn(_RUN_USAGE_KEY, rec)

    def test_turns_array_respects_total_budget(self) -> None:
        # Regression: the per-turn `turns[]` array is charged AND truncated
        # under the record budget, not merely charged. A claude run with
        # thousands of turns but no steps would otherwise write the whole
        # array in full via `build_record` and overshoot the budget by its
        # size -- the reviewer reproduced ~914 KB with zero steps kept.
        _, analytics = _reload()
        many = _usage_records.AgentTrajectory(
            backend=_CLAUDE,
            turns=tuple(
                _usage_records.TurnUsage(
                    turn=index,
                    model=_CLAUDE_MODEL,
                    input_tokens=1,
                    output_tokens=1,
                )
                for index in range(_MANY_TURNS_COUNT)
            ),
        )
        raw, rec = _emit_stubbed_trajectory(self, analytics, many)
        self.assertTrue(rec[_TRUNCATED_KEY])
        self.assertLess(len(rec[_TURNS_KEY]), _MANY_TURNS_COUNT)
        # The on-disk line is bounded near the budget, not the ~914 KB an
        # uncapped turns array produced.
        self.assertLess(len(raw), getattr(analytics, _RECORD_BUDGET) * 2)

    def test_metadata_only_steps_respect_total_budget(self) -> None:
        # Regression: the budget must count each step's serialized metadata,
        # not just `len(content)`. A run of 10,000 empty-content steps -- each
        # still ~80 bytes of `kind` / `name` / `tool_id` JSON -- would
        # otherwise produce a multi-hundred-KB record with NO `truncated`
        # flag, because the old content-length-only check never advanced.
        _, analytics = _reload()
        many = _usage_records.AgentTrajectory(
            backend=_CLAUDE,
            steps=tuple(
                _usage_records.TrajectoryStep(
                    kind=_TOOL_CALL_KIND,
                    name="command_execution",
                    tool_id=f"id{index}",
                    content=None,
                )
                for index in range(_METADATA_ONLY_STEP_COUNT)
            ),
        )
        raw, rec = _emit_stubbed_trajectory(self, analytics, many)
        self.assertTrue(rec[_TRUNCATED_KEY])
        self.assertLess(
            len(rec[_STEPS_KEY]),
            _METADATA_ONLY_STEP_COUNT,
        )
        # The on-disk line is bounded near the budget, not the ~749 KB an
        # uncapped run produced -- one step of overshoot plus the envelope.
        self.assertLess(len(raw), getattr(analytics, _RECORD_BUDGET) * 2)


if __name__ == "__main__":
    unittest.main()
