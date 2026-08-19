# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Analytics trajectory redaction tests."""

import json


import os


import tempfile


import unittest


from pathlib import Path


from unittest.mock import patch


from orchestrator.observability.analytics.trajectories import models as trajectory_models



from tests.observability.analytics.analytics_jsonl_helpers import (
    read_records as _read_records,
)


from tests.observability.analytics.analytics_trajectory_cases import (
    claude_trajectory_stdout as _claude_trajectory_stdout,
    codex_mcp_trajectory_stdout as _codex_mcp_trajectory_stdout,
)


from tests.observability.analytics.trajectories import (
    trajectories_test_support as _support,
)

_ANALYTICS_FILENAME_ALTERNATE = _support.ANALYTICS_FILENAME_ALTERNATE


_CONTENT_KEY = _support.CONTENT_KEY


_KIND_KEY = _support.KIND_KEY


_OUTPUT_KEY = _support.OUTPUT_KEY


_PROMPT_TEXT = _support.PROMPT_TEXT


_REDACTION_MARKER = _support.REDACTION_MARKER


_STEPS_KEY = _support.STEPS_KEY


_TOOL_CALL_KIND = _support.TOOL_CALL_KIND


_TOOL_RESULT_KIND = _support.TOOL_RESULT_KIND


_TRAJECTORY_FILENAME = _support.TRAJECTORY_FILENAME


_USER_INPUT_KEY = _support.USER_INPUT_KEY


_TYPE_KEY = "type"


_COMMAND_KEY = "command"


_TEXT_KEY = "text"


_TRUNCATION_EDGE_CHARS = 5


_LONG_TEXT_CHARS = 100


def _tool_result_body(record: dict) -> str:
    result_step = next(
        step
        for step in record[_STEPS_KEY]
        if step[_KIND_KEY] == _TOOL_RESULT_KIND
    )
    return result_step[_CONTENT_KEY]


class RecordAgentExitTrajectoryRedactionTest(_support.RecordAgentExitTrajectorySupport):
    def test_secrets_redacted_in_every_field(self) -> None:
        # The secret env value must not survive in user_input, the tool_call
        # input, the tool_result content, or the output. `redact_secrets`
        # reads the live os.environ, so set a secret-shaped var around the
        # call and assert it is masked everywhere.
        secret = "sk-ant-DEADBEEF-secret-value-0123456789"
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"ANTHROPIC_API_KEY": secret}):
            t_path = Path(td) / _TRAJECTORY_FILENAME
            self._emit(
                stdout=_claude_trajectory_stdout(
                    tool_input={_COMMAND_KEY: f"echo {secret}"},
                    tool_result=f"leaked {secret} here",
                    final_output=f"the answer is {secret}",
                ),
                prompt=f"use token {secret}",
                traj_path=t_path,
                analytics_path=Path(td) / _ANALYTICS_FILENAME_ALTERNATE,
            )
            rec = _read_records(t_path)[0]
            self.assertNotIn(secret, json.dumps(rec))
            # The masking marker landed in each field that carried it.
            self.assertIn(_REDACTION_MARKER, rec[_USER_INPUT_KEY])
            self.assertIn(_REDACTION_MARKER, rec[_OUTPUT_KEY])
            self.assertIn(_REDACTION_MARKER, rec[_STEPS_KEY][0][_CONTENT_KEY])
            self.assertIn(_REDACTION_MARKER, rec[_STEPS_KEY][1][_CONTENT_KEY])

    def test_multiline_tool_secret_is_redacted(self) -> None:
        # Regression: dict / list tool payloads are redacted leaf-by-leaf
        # BEFORE JSON serialization. A multiline secret env value would
        # otherwise have its newlines escaped by `json.dumps` (`\n` -> the
        # two-char escape), leaving `redact_secrets`' literal `str.replace`
        # unable to match the raw value -- so the secret would leak into
        # `steps[].content`. Redacting raw leaves first keeps it masked, for
        # both the dict tool_call input and the list tool_result content.
        secret = "topsecretvalue\nwith-newline-marker-0123456789"
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"MULTILINE_SECRET_KEY": secret}):
            t_path = Path(td) / _TRAJECTORY_FILENAME
            self._emit(
                stdout=_claude_trajectory_stdout(
                    tool_input={_COMMAND_KEY: f"echo {secret}"},
                    tool_result=[{_TYPE_KEY: _TEXT_KEY, _TEXT_KEY: f"saw {secret}"}],
                    final_output="done",
                ),
                prompt=_PROMPT_TEXT,
                traj_path=t_path,
                analytics_path=Path(td) / _ANALYTICS_FILENAME_ALTERNATE,
            )
            rec = _read_records(t_path)[0]
            # Neither the raw value nor its distinctive post-newline marker
            # survives anywhere in the record.
            self.assertNotIn("with-newline-marker-0123456789", json.dumps(rec))
            self.assertNotIn("topsecretvalue", json.dumps(rec))
            # Both the dict input and the list content carry the mask.
            self.assertIn(_REDACTION_MARKER, rec[_STEPS_KEY][0][_CONTENT_KEY])
            self.assertIn(_REDACTION_MARKER, rec[_STEPS_KEY][1][_CONTENT_KEY])

    def test_codex_nested_tool_payloads_are_redacted(self) -> None:
        # A codex MCP call reports its arguments and its result as nested
        # JSON, not as text, so the leaf-by-leaf walk is the only thing that
        # can reach a secret inside them -- serializing first would leave the
        # writer masking an already-escaped string.
        secret = "sk-ant-CODEXLEAK-secret-value-0123456789"
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"CODEX_TOOL_SECRET_KEY": secret}):
            t_path = Path(td) / _TRAJECTORY_FILENAME
            self._emit(
                backend=_support.CODEX,
                stdout=_codex_mcp_trajectory_stdout(
                    arguments={"url": f"https://example.invalid/?token={secret}"},
                    result_content=[{_TYPE_KEY: _TEXT_KEY, _TEXT_KEY: f"saw {secret}"}],
                ),
                prompt=_PROMPT_TEXT,
                traj_path=t_path,
            )
            rec = _read_records(t_path)[0]
            self.assertNotIn(secret, json.dumps(rec))
            self.assertEqual(
                [step[_KIND_KEY] for step in rec[_STEPS_KEY]],
                [_TOOL_CALL_KIND, _TOOL_RESULT_KIND],
            )
            for step in rec[_STEPS_KEY]:
                with self.subTest(kind=step[_KIND_KEY]):
                    self.assertIn(_REDACTION_MARKER, step[_CONTENT_KEY])

    def test_per_step_content_head_tail_truncated(self) -> None:
        # A long field is redacted then truncated to head + tail chars with
        # an elision marker, so a single huge tool output cannot bloat one
        # step. Shrink the caps so the test stays small.
        with (
            tempfile.TemporaryDirectory() as td,
            patch.object(
                trajectory_models,
                "TRAJECTORY_FIELD_HEAD",
                _TRUNCATION_EDGE_CHARS,
            ),
            patch.object(
                trajectory_models,
                "TRAJECTORY_FIELD_TAIL",
                _TRUNCATION_EDGE_CHARS,
            ),
        ):
            t_path = Path(td) / _TRAJECTORY_FILENAME
            self._emit(
                stdout=_claude_trajectory_stdout(
                    tool_result="A" * _LONG_TEXT_CHARS,
                    final_output="done",
                ),
                prompt=_PROMPT_TEXT,
                traj_path=t_path,
                analytics_path=Path(td) / _ANALYTICS_FILENAME_ALTERNATE,
            )
            body = _tool_result_body(_read_records(t_path)[0])
            self.assertLess(len(body), _LONG_TEXT_CHARS)
            edge = "A" * _TRUNCATION_EDGE_CHARS
            self.assertTrue(body.startswith(edge))
            self.assertTrue(body.endswith(edge))
            self.assertIn("chars elided", body)


if __name__ == "__main__":
    unittest.main()
