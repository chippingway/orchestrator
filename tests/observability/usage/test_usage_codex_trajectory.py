# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Codex trajectory step parsing tests."""

import unittest

from orchestrator.observability.usage import trajectory as _trajectory, trajectory_models as _records
from tests.observability.usage import (
    usage_codex_events as _codex,
    usage_codex_tool_events as _tool_events,
    usage_jsonl_helpers as _jsonl,
    usage_test_values as _usage_cases,
)


class CodexTrajectoryStepsTest(unittest.TestCase):
    """``_trajectory.parse_codex_trajectory`` over synthetic ``codex exec --json`` runs.

    Every operational item codex reports is one ordered pair: a
    ``command_execution`` is its ``command`` and the ``aggregated_output`` of
    the frame that completed it, an ``mcp_tool_call`` its ``arguments`` and
    its ``result``, a ``web_search`` its ``query`` and the ``action`` it
    resolved to, a ``file_change`` (codex's ``apply_patch`` custom tool) its
    ``changes`` and the status it settled on, a ``todo_list`` the plan it
    opened with and the state that plan ended in. Each pair is deduped by the
    shared ``item.id`` across the started/updated/completed frames, and each
    ``agent_message`` is one ``assistant_message`` text turn (its ``text``),
    captured in stream order. The last ``agent_message`` ``text`` is also the
    final output; ``tools`` / ``system_prompt`` stay empty (no confirmed codex
    frame exposes them).
    """

    def test_extracts_steps_skills_and_final_output(self) -> None:
        stdout = _jsonl.jsonl(
            {_usage_cases.TYPE_FIELD: _usage_cases.THREAD_STARTED_EVENT, "thread_id": _usage_cases.TASK_ONE_ID},
            _codex.command(
                _usage_cases.ITEM_ONE_ID,
                _usage_cases.DEVELOP_SKILL_READ_COMMAND,
                started=True,
                status=_usage_cases.IN_PROGRESS_STATUS,
            ),
            _codex.command(
                _usage_cases.ITEM_ONE_ID,
                _usage_cases.DEVELOP_SKILL_READ_COMMAND,
                status=_usage_cases.COMPLETED_STATUS,
                exit_code=0,
                aggregated_output="# Developer skill\n",
            ),
            _codex.command(
                _usage_cases.ITEM_TWO_ID,
                "/bin/bash -lc 'git diff -- calc.py'",
                status=_usage_cases.COMPLETED_STATUS,
                exit_code=0,
                aggregated_output="diff --git ...\n",
            ),
            _codex.agent_message(_usage_cases.ITEM_THREE_ID, _usage_cases.APPROVAL_MESSAGE),
        )
        trajectory = _trajectory.parse_codex_trajectory(stdout)
        self.assertEqual(trajectory.backend, _usage_cases.CODEX)
        self.assertIsNone(trajectory.system_prompt)
        self.assertEqual(trajectory.tools, ())
        self.assertEqual(trajectory.final_output, _usage_cases.APPROVAL_MESSAGE)
        # SKILL.md read surfaces in the names-only skills extractor.
        self.assertEqual(trajectory.skills.triggered, _usage_cases.DEVELOP_ONLY)
        # started + completed for item_1 collapse to one call + one result;
        # the trailing agent_message rides along as an assistant_message turn
        # (and is also the final output).
        self.assertEqual(
            trajectory.steps,
            (
                _records.TrajectoryStep(
                    kind=_usage_cases.TOOL_CALL_STEP,
                    name="command_execution",
                    tool_id=_usage_cases.ITEM_ONE_ID,
                    content=_usage_cases.DEVELOP_SKILL_READ_COMMAND,
                ),
                _records.TrajectoryStep(
                    kind=_usage_cases.TOOL_RESULT_STEP, tool_id=_usage_cases.ITEM_ONE_ID, content="# Developer skill\n"
                ),
                _records.TrajectoryStep(
                    kind=_usage_cases.TOOL_CALL_STEP,
                    name="command_execution",
                    tool_id=_usage_cases.ITEM_TWO_ID,
                    content="/bin/bash -lc 'git diff -- calc.py'",
                ),
                _records.TrajectoryStep(
                    kind=_usage_cases.TOOL_RESULT_STEP, tool_id=_usage_cases.ITEM_TWO_ID, content="diff --git ...\n"
                ),
                _records.TrajectoryStep(
                    kind=_usage_cases.ASSISTANT_MESSAGE_STEP, content=_usage_cases.APPROVAL_MESSAGE
                ),
            ),
        )

    def test_agent_messages_become_ordered_turns(self) -> None:
        # Each agent_message item becomes an assistant_message turn, kept in
        # stream order relative to the command steps; the last one is still the
        # final output.
        stdout = _jsonl.jsonl(
            _codex.agent_message(_usage_cases.AGENT_MESSAGE_ID, "starting"),
            _codex.command(
                "c1",
                _usage_cases.SHELL_LIST_COMMAND,
                status=_usage_cases.COMPLETED_STATUS,
                exit_code=0,
                aggregated_output=_usage_cases.COMMAND_OUTPUT,
            ),
            _codex.agent_message("a2", "all done"),
        )
        trajectory = _trajectory.parse_codex_trajectory(stdout)
        self.assertEqual(
            [(step.kind, step.content) for step in trajectory.steps],
            [
                (_usage_cases.ASSISTANT_MESSAGE_STEP, "starting"),
                (_usage_cases.TOOL_CALL_STEP, _usage_cases.SHELL_LIST_COMMAND),
                (_usage_cases.TOOL_RESULT_STEP, _usage_cases.COMMAND_OUTPUT),
                (_usage_cases.ASSISTANT_MESSAGE_STEP, "all done"),
            ],
        )
        self.assertEqual(trajectory.final_output, "all done")

    def test_started_completed_message_collapses(self) -> None:
        # A started + completed agent_message sharing an item.id is one turn
        # (last text wins), mirroring the command started/completed collapse.
        stdout = _jsonl.jsonl(
            _codex.agent_message(_usage_cases.AGENT_MESSAGE_ID, "partial", started=True),
            _codex.agent_message(_usage_cases.AGENT_MESSAGE_ID, "final text"),
        )
        trajectory = _trajectory.parse_codex_trajectory(stdout)
        self.assertEqual(
            trajectory.steps,
            (_records.TrajectoryStep(kind=_usage_cases.ASSISTANT_MESSAGE_STEP, content="final text"),),
        )
        self.assertEqual(trajectory.final_output, "final text")

    def test_skips_empty_or_nonstring_message(self) -> None:
        # An empty / non-string agent_message text creates no turn.
        stdout = _jsonl.jsonl(
            _codex.agent_message(_usage_cases.AGENT_MESSAGE_ID, ""),
            _codex.agent_message("a2", 7),
        )
        self.assertEqual(_trajectory.parse_codex_trajectory(stdout).steps, ())

    def test_started_command_emits_call_no_result(self) -> None:
        # A running command already reports an (empty) aggregated_output, as
        # every captured started frame does, so a command the stream never
        # completes is a call with no result step rather than one credited
        # with an empty output it never produced.
        stdout = _jsonl.jsonl(
            _codex.command(
                _usage_cases.ITEM_ONE_ID,
                "/bin/bash -lc 'sleep 99'",
                started=True,
                aggregated_output="",
                exit_code=None,
                status=_usage_cases.IN_PROGRESS_STATUS,
            ),
        )
        trajectory = _trajectory.parse_codex_trajectory(stdout)
        self.assertEqual(
            [(step.kind, step.tool_id) for step in trajectory.steps],
            [(_usage_cases.TOOL_CALL_STEP, _usage_cases.ITEM_ONE_ID)],
        )


class CodexToolItemStepsTest(unittest.TestCase):
    """The captured ``codex exec --json`` streams, item type by item type.

    The fixtures are the raw lines codex printed, so what is pinned here is
    the parse of a real stream rather than of a rebuilt one: the frame order,
    the identifier each item is correlated under, and the payloads the pairs
    are built from.
    """

    def test_captured_run_normalizes_every_item(self) -> None:
        trajectory = _trajectory.parse_codex_trajectory(_tool_events.TOOL_RUN_STDOUT)
        # The reasoning item between the search and the MCP call leaves no
        # step at all, and the plan codex republishes as a ``todo_list``
        # collapses to one pair however many revisions it took.
        # The search pair is recorded under the provider's own ``exec-...``
        # call id rather than the synthetic ``item_N`` beside it: a web_search
        # frame serializes ``id`` twice and the provider's is written last, so
        # that is the one the decoder hands the parser.
        self.assertEqual(
            trajectory.steps,
            (
                _records.TrajectoryStep(
                    kind=_usage_cases.ASSISTANT_MESSAGE_STEP,
                    content=_tool_events.OPENING_MESSAGE,
                ),
                _records.TrajectoryStep(
                    kind=_usage_cases.TOOL_CALL_STEP,
                    name="web_search",
                    tool_id=_tool_events.SEARCH_CALL_ID,
                    content=_tool_events.SEARCH_QUERY,
                ),
                _records.TrajectoryStep(
                    kind=_usage_cases.TOOL_RESULT_STEP,
                    tool_id=_tool_events.SEARCH_CALL_ID,
                    content={"type": "search", "query": _tool_events.SEARCH_QUERY},
                ),
                _records.TrajectoryStep(
                    kind=_usage_cases.TOOL_CALL_STEP,
                    name=_tool_events.SEARCH_DOCS_NAME,
                    tool_id=_tool_events.MCP_ITEM_ID,
                    content={"query": _tool_events.SEARCH_QUERY, "limit": 5},
                ),
                _records.TrajectoryStep(
                    kind=_usage_cases.TOOL_RESULT_STEP,
                    tool_id=_tool_events.MCP_ITEM_ID,
                    content={
                        "content": [{"type": "text", "text": '{"hits":[]}'}],
                        "structured_content": None,
                    },
                ),
                _records.TrajectoryStep(
                    kind=_usage_cases.TOOL_CALL_STEP,
                    name="command_execution",
                    tool_id=_tool_events.COMMAND_ITEM_ID,
                    content=_tool_events.LIST_COMMAND,
                ),
                _records.TrajectoryStep(
                    kind=_usage_cases.TOOL_RESULT_STEP,
                    tool_id=_tool_events.COMMAND_ITEM_ID,
                    content=_tool_events.LIST_OUTPUT,
                ),
                _records.TrajectoryStep(
                    kind=_usage_cases.TOOL_CALL_STEP,
                    name="file_change",
                    tool_id=_tool_events.FILE_CHANGE_ITEM_ID,
                    content=[{"path": _tool_events.CHANGED_PATH, "kind": "update"}],
                ),
                _records.TrajectoryStep(
                    kind=_usage_cases.TOOL_RESULT_STEP,
                    tool_id=_tool_events.FILE_CHANGE_ITEM_ID,
                    content=_usage_cases.COMPLETED_STATUS,
                ),
                _records.TrajectoryStep(
                    kind=_usage_cases.TOOL_CALL_STEP,
                    name="todo_list",
                    tool_id=_tool_events.TODO_ITEM_ID,
                    content=_tool_events.plan_steps((_tool_events.TODO_TEXT, False)),
                ),
                _records.TrajectoryStep(
                    kind=_usage_cases.TOOL_RESULT_STEP,
                    tool_id=_tool_events.TODO_ITEM_ID,
                    content=_tool_events.plan_steps((_tool_events.TODO_TEXT, True)),
                ),
                _records.TrajectoryStep(
                    kind=_usage_cases.ASSISTANT_MESSAGE_STEP,
                    content=_tool_events.CLOSING_MESSAGE,
                ),
            ),
        )
        self.assertEqual(trajectory.final_output, _tool_events.CLOSING_MESSAGE)

    def test_wrapper_sharing_an_id_adds_no_step(self) -> None:
        # An outer tool call reporting the id of the search nested inside it
        # describes one operation, not two. The parser has no normalizer for
        # such a wrapper -- ``codex exec --json`` publishes no custom-tool
        # item type -- so what has to hold is that its placeholder never
        # lands beside the normalized pair nor replaces it, whether it opens
        # before the search or closes after it.
        wrapper = _jsonl.jsonl(
            _codex.stream_item(
                _tool_events.SEARCH_CALL_ID,
                "custom_tool_call",
                started=True,
                status=_usage_cases.IN_PROGRESS_STATUS,
            ),
        )
        closing_wrapper = _jsonl.jsonl(
            _codex.stream_item(
                _tool_events.SEARCH_CALL_ID,
                "custom_tool_call",
                status=_usage_cases.COMPLETED_STATUS,
            ),
        )
        stdout = _jsonl.stdout_lines(
            wrapper,
            _tool_events.WEB_SEARCH_STARTED_LINE,
            _tool_events.WEB_SEARCH_COMPLETED_LINE,
            closing_wrapper,
        )
        trajectory = _trajectory.parse_codex_trajectory(stdout)
        self.assertEqual(
            trajectory.steps,
            (
                _records.TrajectoryStep(
                    kind=_usage_cases.TOOL_CALL_STEP,
                    name="web_search",
                    tool_id=_tool_events.SEARCH_CALL_ID,
                    content=_tool_events.SEARCH_QUERY,
                ),
                _records.TrajectoryStep(
                    kind=_usage_cases.TOOL_RESULT_STEP,
                    tool_id=_tool_events.SEARCH_CALL_ID,
                    content={"type": "search", "query": _tool_events.SEARCH_QUERY},
                ),
            ),
        )

    def test_unfinished_calls_get_no_invented_result(self) -> None:
        # The failed MCP call keeps the payload the server answered with; the
        # search the stream never completed keeps its call and gets no result
        # invented for it; the unclaimed ``error`` item still shows up.
        trajectory = _trajectory.parse_codex_trajectory(_tool_events.FAILED_RUN_STDOUT)
        self.assertEqual(
            [(step.kind, step.name, step.tool_id) for step in trajectory.steps],
            [
                (
                    _usage_cases.TOOL_CALL_STEP,
                    _tool_events.FETCH_DOC_NAME,
                    _tool_events.FAILED_MCP_ITEM_ID,
                ),
                (
                    _usage_cases.TOOL_RESULT_STEP,
                    "",
                    _tool_events.FAILED_MCP_ITEM_ID,
                ),
                (
                    _usage_cases.TOOL_CALL_STEP,
                    "web_search",
                    _tool_events.ABANDONED_SEARCH_CALL_ID,
                ),
                (_usage_cases.UNSUPPORTED_ITEM_STEP, "error", "item_2"),
            ],
        )
        self.assertIn(
            _tool_events.FETCHED_URL,
            str(trajectory.steps[1].content),
        )
        self.assertIsNone(trajectory.final_output)
