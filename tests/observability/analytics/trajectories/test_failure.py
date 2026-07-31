# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Analytics trajectory failure-isolation tests."""

import tempfile


import unittest


from pathlib import Path


from unittest.mock import patch


from orchestrator.observability.usage import trajectory as _usage_trajectory


from tests.analytics_reload_helpers import reload_analytics as _reload


from tests.analytics_jsonl_helpers import (
    read_records as _read_records,
)


from tests.analytics_recording_cases import (
    claude_stdout_with_skills as _claude_stdout_with_skills,
)


from tests.analytics_trajectory_cases import (
    claude_trajectory_stdout as _claude_trajectory_stdout,
)


from tests.observability.analytics.trajectories import (
    trajectories_test_support as _support,
)

_AGENT_EXIT = _support.AGENT_EXIT


_ANALYTICS_FILENAME = _support.ANALYTICS_FILENAME


_ANALYTICS_FILENAME_ALTERNATE = _support.ANALYTICS_FILENAME_ALTERNATE


_EVENT_KEY = _support.EVENT_KEY


_INPUT_TOKENS_KEY = _support.INPUT_TOKENS_KEY


_OUTPUT_KEY = _support.OUTPUT_KEY


_PROMPT_TEXT = _support.PROMPT_TEXT


_TRAJECTORY_FILENAME = _support.TRAJECTORY_FILENAME


_USER_INPUT_KEY = _support.USER_INPUT_KEY


_DEVELOP = "develop"


SKILL_STREAM_INPUT_TOKENS = 1_000


class RecordAgentExitTrajectoryFailureTest(_support.RecordAgentExitTrajectorySupport):
    def test_parser_failure_keeps_baseline_and_skills(self) -> None:
        # The trajectory parse rides its own fail-open guard: a parser bug
        # logs and is swallowed, leaving the baseline `agent_exit` record AND
        # the skill-trigger return value (which drives the audit events)
        # intact.
        _, analytics = _reload()
        with tempfile.TemporaryDirectory() as td:
            a_path = Path(td) / _ANALYTICS_FILENAME
            t_path = Path(td) / _TRAJECTORY_FILENAME
            with (
                patch.object(
                    _usage_trajectory,
                    "parse_agent_trajectory",
                    side_effect=RuntimeError("boom"),
                ),
                self.assertLogs(analytics.log, level="ERROR"),
            ):
                self.assertEqual(
                    self._emit(
                        analytics,
                        stdout=_claude_stdout_with_skills(skills=(_DEVELOP,)),
                        prompt=_PROMPT_TEXT,
                        traj_path=t_path,
                        analytics_path=a_path,
                        track=True,
                    ),
                    [_DEVELOP],
                )
            # Skill return value (and thus audit emission) is unaffected.
            # Baseline record survived...
            base = _read_records(a_path)
            self.assertEqual(len(base), 1)
            self.assertEqual(base[0][_EVENT_KEY], _AGENT_EXIT)
            self.assertEqual(
                base[0][_INPUT_TOKENS_KEY],
                SKILL_STREAM_INPUT_TOKENS,
            )
            # ...and the broken trajectory wrote nothing.
            self.assertFalse(t_path.exists())

    def test_sink_failure_keeps_baseline_record(self) -> None:
        # A non-OSError escaping the sink append (a programming error past
        # the inner OSError swallow) must not drop the baseline record: the
        # outer guard logs and falls through.
        _, analytics = _reload()
        with tempfile.TemporaryDirectory() as td:
            a_path = Path(td) / _ANALYTICS_FILENAME
            with (
                patch.object(
                    analytics,
                    "append_trajectory_record",
                    side_effect=RuntimeError("sink boom"),
                ),
                self.assertLogs(analytics.log, level="ERROR"),
            ):
                self._emit(
                    analytics,
                    stdout=_claude_trajectory_stdout(),
                    prompt=_PROMPT_TEXT,
                    traj_path=Path(td) / _TRAJECTORY_FILENAME,
                    analytics_path=a_path,
                )
            base = _read_records(a_path)
            self.assertEqual(len(base), 1)
            self.assertEqual(base[0][_EVENT_KEY], _AGENT_EXIT)

    def test_absent_prompt_drops_user_input(self) -> None:
        # No prompt passed -> `user_input` is dropped (not stored as null),
        # while the rest of the trajectory still records.
        _, analytics = _reload()
        with tempfile.TemporaryDirectory() as td:
            t_path = Path(td) / _TRAJECTORY_FILENAME
            self._emit(
                analytics,
                stdout=_claude_trajectory_stdout(final_output="x"),
                prompt=None,
                traj_path=t_path,
                analytics_path=Path(td) / _ANALYTICS_FILENAME_ALTERNATE,
            )
            rec = _read_records(t_path)[0]
            self.assertNotIn(_USER_INPUT_KEY, rec)
            self.assertEqual(rec[_OUTPUT_KEY], "x")


if __name__ == "__main__":
    unittest.main()
