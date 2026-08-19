# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Codex source-item accounting tests."""

import json
import unittest
from types import MappingProxyType

from orchestrator.observability.usage import trajectory as _trajectory
from tests.observability.usage import usage_test_values as _usage_cases
from tests.observability.usage import usage_jsonl_helpers as _jsonl
from tests.observability.usage import usage_codex_events as _codex
from tests.observability.usage import usage_codex_tool_events as _tool_events
from tests.observability.usage import usage_trajectory_projections as _projections


_AGENT_MESSAGE_ITEM = "agent_message"
_REASONING_ITEM = "reasoning"
_COMMAND_EXECUTION_ITEM = "command_execution"
_WEB_SEARCH_ITEM = "web_search"
_FILE_CHANGE_ITEM = "file_change"
_TODO_LIST_ITEM = "todo_list"
_ERROR_ITEM = "error"
_COLLAB_TOOL_CALL_ITEM = "collab_tool_call"
_CUSTOM_TOOL_CALL_ITEM = "custom_tool_call"

# The dispositions whose items are readable back out of the ordered steps.
_RECORDED_DISPOSITIONS = frozenset((
    _usage_cases.STORED_DISPOSITION,
    _usage_cases.UNSUPPORTED_DISPOSITION,
))

_SOURCE_ITEMS_KEY = "source_items"

# The two messages the captured tool run opens and closes on.
_TOOL_RUN_OPENING_ID = "item_0"
_TOOL_RUN_CLOSING_ID = "item_7"

# The stream assembled below, item by item.
_OPENING_MESSAGE = "Looking into it."
_OPENING_MESSAGE_ID = "item_0"
_BRACKETED_COMMAND_ID = "item_1"
_PRECEDING_ITEM_ID = "item_2"
_FINAL_MESSAGE_ID = "item_3"
_TRAILING_ITEM_ID = "item_4"

# The two placements no captured run carries: an item nothing normalizes
# immediately before the message that ends the run, and one after it, where a
# reader with only the steps to go on cannot tell an item that was classified
# from one the parser never reached.
_BRACKETED_MESSAGE_STDOUT = _jsonl.jsonl(
    _codex.agent_message(_OPENING_MESSAGE_ID, _OPENING_MESSAGE),
    _codex.command(
        _BRACKETED_COMMAND_ID,
        _usage_cases.SHELL_LIST_COMMAND,
        status=_usage_cases.COMPLETED_STATUS,
        aggregated_output=_usage_cases.COMMAND_OUTPUT,
    ),
    _codex.stream_item(
        _PRECEDING_ITEM_ID,
        _COLLAB_TOOL_CALL_ITEM,
        status=_usage_cases.COMPLETED_STATUS,
    ),
    _codex.agent_message(_FINAL_MESSAGE_ID, _usage_cases.APPROVAL_MESSAGE),
    _codex.stream_item(_TRAILING_ITEM_ID, _ERROR_ITEM, message="no metadata"),
)

_SEARCH_LINES = (
    _tool_events.WEB_SEARCH_STARTED_LINE,
    _tool_events.WEB_SEARCH_COMPLETED_LINE,
)

# The wrapper frame is synthetic: `codex exec --json` publishes no custom-tool
# item type, so what a captured run cannot supply is an unclaimed frame
# reporting the id of a claimed one.
_WRAPPED_SEARCH_STREAMS = MappingProxyType({
    "wrapper opens first": "\n".join((
        _jsonl.jsonl(_codex.stream_item(
            _tool_events.SEARCH_CALL_ID,
            _CUSTOM_TOOL_CALL_ITEM,
            started=True,
            status=_usage_cases.IN_PROGRESS_STATUS,
        )),
        *_SEARCH_LINES,
    )),
    "wrapper closes last": "\n".join((
        *_SEARCH_LINES,
        _jsonl.jsonl(_codex.stream_item(
            _tool_events.SEARCH_CALL_ID,
            _CUSTOM_TOOL_CALL_ITEM,
            status=_usage_cases.COMPLETED_STATUS,
        )),
    )),
})

_WRAPPED_SEARCH_CLASSES = MappingProxyType({
    _tool_events.SEARCH_CALL_ID: (
        _WEB_SEARCH_ITEM,
        _usage_cases.STORED_DISPOSITION,
    ),
})

_SUPERSEDED_WRAPPER_ID = "item_9"

# Normalized frames that report no invocation of their own: a message with no
# text, and a plan frame that opened without a list. Each is what the wrapper's
# own status would be read as if a placeholder were merged into rather than
# replaced.
_CALL_LESS_FRAMES = MappingProxyType({
    _AGENT_MESSAGE_ITEM: _codex.agent_message(_SUPERSEDED_WRAPPER_ID, ""),
    _TODO_LIST_ITEM: _codex.stream_item(
        _SUPERSEDED_WRAPPER_ID,
        _TODO_LIST_ITEM,
        started=True,
    ),
})


def _superseded_wrapper_cases() -> dict[str, tuple[str, str]]:
    """One case per call-less frame per side of the wrapper sharing its id."""
    opening = _codex.stream_item(
        _SUPERSEDED_WRAPPER_ID,
        _CUSTOM_TOOL_CALL_ITEM,
        started=True,
        status=_usage_cases.IN_PROGRESS_STATUS,
    )
    closing = _codex.stream_item(
        _SUPERSEDED_WRAPPER_ID,
        _CUSTOM_TOOL_CALL_ITEM,
        status=_usage_cases.COMPLETED_STATUS,
    )
    cases: dict[str, tuple[str, str]] = {}
    for item_type, frame in _CALL_LESS_FRAMES.items():
        cases[f"{item_type} after the wrapper"] = (
            item_type,
            _jsonl.jsonl(opening, frame),
        )
        cases[f"{item_type} before the wrapper"] = (
            item_type,
            _jsonl.jsonl(frame, closing),
        )
    return cases


_SUPERSEDED_WRAPPER_CASES = MappingProxyType(_superseded_wrapper_cases())


def _streamed_item_ids(stdout: str) -> tuple[str, ...]:
    """Every `item.id` a decoder reads out of one stream, first seen first."""
    seen: dict[str, None] = {}
    for line in stdout.splitlines():
        stream_item = json.loads(line).get(_usage_cases.ITEM_FIELD)
        if not isinstance(stream_item, dict):
            continue
        item_id = stream_item.get(_usage_cases.IDENTIFIER_FIELD)
        if isinstance(item_id, str):
            seen[item_id] = None
    return tuple(seen)


def _expects_tool_step(source_item) -> bool:
    """Whether a step should carry this item's id as its `tool_id`."""
    # A message turn is the one stored item with no step to find it under: it
    # is not a tool call, so it carries no `tool_id` to be found by.
    if source_item.item_type == _AGENT_MESSAGE_ITEM:
        return False
    return source_item.disposition in _RECORDED_DISPOSITIONS


def _assert_accounting_matches_steps(
    test_case: unittest.TestCase,
    stdout: str,
) -> None:
    """Every id is accounted once, and its disposition matches the steps."""
    trajectory = _trajectory.parse_codex_trajectory(stdout)
    accounted = tuple(
        source_item.item_id for source_item in trajectory.source_items
    )
    test_case.assertEqual(accounted, _streamed_item_ids(stdout))
    step_ids = {step.tool_id for step in trajectory.steps if step.tool_id}
    # A step recorded under an id nothing accounts would be the accounting
    # missing an item the trajectory itself kept.
    test_case.assertLessEqual(step_ids, set(accounted))
    for source_item in trajectory.source_items:
        with test_case.subTest(item_id=source_item.item_id):
            test_case.assertEqual(
                source_item.item_id in step_ids,
                _expects_tool_step(source_item),
            )


class CodexSourceItemAccountingTest(unittest.TestCase):
    """Every identified item is classified, and the classification holds.

    A codex stream identifies an item once and reports it over as many frames
    as it takes, so the accounting is one ``SourceItem`` per ``item.id`` in
    first-seen order. Its disposition says where the item went: ``stored``
    when its own steps are in the trajectory, ``unsupported`` when the
    placeholder step is what names it, ``excluded`` for the reasoning the
    parser keeps out whole, and ``empty`` when its frames carried nothing to
    store. What the accounting is for is the item a reader cannot find in the
    steps: an id that reaches no step is a decision recorded here rather than
    one that has to be inferred from a gap.
    """

    def test_captured_runs_account_for_every_item(self) -> None:
        captured_runs = (
            _tool_events.TOOL_RUN_STDOUT,
            _tool_events.FAILED_RUN_STDOUT,
            _tool_events.LIFECYCLE_RUN_STDOUT,
        )
        for stdout in captured_runs:
            with self.subTest(items=_streamed_item_ids(stdout)):
                _assert_accounting_matches_steps(self, stdout)

    def test_captured_run_classifies_every_item(self) -> None:
        # The search is accounted under the provider's own `exec-...` call id,
        # the one the decoder hands the parser, so it is the same identifier
        # its pair of steps is recorded under.
        trajectory = _trajectory.parse_codex_trajectory(
            _tool_events.TOOL_RUN_STDOUT,
        )
        stored = _usage_cases.STORED_DISPOSITION
        self.assertEqual(
            _projections.source_item_classes(trajectory),
            {
                _TOOL_RUN_OPENING_ID: (_AGENT_MESSAGE_ITEM, stored),
                _tool_events.SEARCH_CALL_ID: (_WEB_SEARCH_ITEM, stored),
                _usage_cases.ITEM_TWO_ID: (
                    _REASONING_ITEM,
                    _usage_cases.EXCLUDED_DISPOSITION,
                ),
                _tool_events.MCP_ITEM_ID: (
                    _usage_cases.MCP_TOOL_CALL_ITEM,
                    stored,
                ),
                _tool_events.COMMAND_ITEM_ID: (_COMMAND_EXECUTION_ITEM, stored),
                _tool_events.FILE_CHANGE_ITEM_ID: (_FILE_CHANGE_ITEM, stored),
                _tool_events.TODO_ITEM_ID: (_TODO_LIST_ITEM, stored),
                _TOOL_RUN_CLOSING_ID: (_AGENT_MESSAGE_ITEM, stored),
            },
        )

    def test_reasoning_keeps_nothing_of_the_item(self) -> None:
        # The reasoning item is named as a decision and nothing else: the
        # hidden text the exclusion exists for is not in a step, not in the
        # accounting, and not in the final output.
        trajectory = _trajectory.parse_codex_trajectory(
            _tool_events.TOOL_RUN_STDOUT,
        )
        self.assertNotIn(
            _tool_events.REASONING_TEXT,
            json.dumps(trajectory.to_dict(), default=str),
        )

    def test_message_ids_are_accounted_off_the_steps(self) -> None:
        # A text turn is not a tool call, so its provider id rides the
        # accounting rather than the step's `tool_id`, which a downstream
        # reader joins a result to its invocation by.
        trajectory = _trajectory.parse_codex_trajectory(
            _tool_events.TOOL_RUN_STDOUT,
        )
        message_steps = [
            step
            for step in trajectory.steps
            if step.kind == _usage_cases.ASSISTANT_MESSAGE_STEP
        ]
        self.assertEqual([step.tool_id for step in message_steps], ["", ""])
        self.assertEqual(
            [
                source_item.item_id
                for source_item in trajectory.source_items
                if source_item.item_type == _AGENT_MESSAGE_ITEM
            ],
            [_TOOL_RUN_OPENING_ID, _TOOL_RUN_CLOSING_ID],
        )

    def test_normalized_frame_outranks_a_wrapper(self) -> None:
        # An outer tool call reporting the id of the search nested inside it
        # describes one operation, and the accounting says which one: the
        # normalized frame names the item whichever side of the pair the
        # wrapper the parser cannot claim arrives on.
        for order, stdout in _WRAPPED_SEARCH_STREAMS.items():
            with self.subTest(order=order):
                trajectory = _trajectory.parse_codex_trajectory(stdout)
                self.assertEqual(
                    _projections.source_item_classes(trajectory),
                    dict(_WRAPPED_SEARCH_CLASSES),
                )

    def test_normalized_frame_replaces_a_placeholder(self) -> None:
        # A placeholder is named after the wrapper's own item type and
        # payloaded with the wrapper's own status, neither of which describes
        # the call underneath, so a normalized frame that reported no
        # invocation of its own leaves the item with none -- rather than
        # speaking an assistant message, or opening a plan, that reads back as
        # the wrapper's `in_progress`.
        for case, (item_type, stdout) in _SUPERSEDED_WRAPPER_CASES.items():
            with self.subTest(case=case):
                trajectory = _trajectory.parse_codex_trajectory(stdout)
                self.assertEqual(trajectory.steps, ())
                self.assertEqual(
                    _projections.source_item_classes(trajectory),
                    {
                        _SUPERSEDED_WRAPPER_ID: (
                            item_type,
                            _usage_cases.EMPTY_DISPOSITION,
                        ),
                    },
                )


class CodexUnstoredItemAccountingTest(unittest.TestCase):
    """The items a reader would otherwise have to notice as missing.

    An item nothing normalizes, one whose frames carried no payload, and one
    too malformed to name a type each reach the trajectory differently, and
    the accounting is where all three are said out loud -- including in the
    record the run is persisted from.
    """

    def test_unsupported_items_around_the_message(self) -> None:
        # An item nothing normalizes neither swallows the message that follows
        # it nor falls off the end of the accounting when it is what the
        # stream stops on.
        trajectory = _trajectory.parse_codex_trajectory(
            _BRACKETED_MESSAGE_STDOUT,
        )
        unsupported = _usage_cases.UNSUPPORTED_DISPOSITION
        stored = _usage_cases.STORED_DISPOSITION
        self.assertEqual(
            [
                (source_item.item_id, source_item.item_type, source_item.disposition)
                for source_item in trajectory.source_items
            ],
            [
                (_OPENING_MESSAGE_ID, _AGENT_MESSAGE_ITEM, stored),
                (_BRACKETED_COMMAND_ID, _COMMAND_EXECUTION_ITEM, stored),
                (_PRECEDING_ITEM_ID, _COLLAB_TOOL_CALL_ITEM, unsupported),
                (_FINAL_MESSAGE_ID, _AGENT_MESSAGE_ITEM, stored),
                (_TRAILING_ITEM_ID, _ERROR_ITEM, unsupported),
            ],
        )
        self.assertEqual(
            [(step.kind, step.tool_id) for step in trajectory.steps],
            [
                (_usage_cases.ASSISTANT_MESSAGE_STEP, ""),
                (_usage_cases.TOOL_CALL_STEP, _BRACKETED_COMMAND_ID),
                (_usage_cases.TOOL_RESULT_STEP, _BRACKETED_COMMAND_ID),
                (_usage_cases.UNSUPPORTED_ITEM_STEP, _PRECEDING_ITEM_ID),
                (_usage_cases.ASSISTANT_MESSAGE_STEP, ""),
                (_usage_cases.UNSUPPORTED_ITEM_STEP, _TRAILING_ITEM_ID),
            ],
        )
        self.assertEqual(trajectory.final_output, _usage_cases.APPROVAL_MESSAGE)
        _assert_accounting_matches_steps(self, _BRACKETED_MESSAGE_STDOUT)

    def test_items_storing_nothing_are_empty(self) -> None:
        # An item the parser would have recorded but whose frames carried no
        # payload, and one too malformed to name a type at all, are both
        # classified rather than left to a reader to notice as missing.
        stdout = _jsonl.jsonl(
            _codex.agent_message(_usage_cases.ITEM_ONE_ID, ""),
            {
                _usage_cases.TYPE_FIELD: _usage_cases.ITEM_COMPLETED_EVENT,
                _usage_cases.ITEM_FIELD: {
                    _usage_cases.IDENTIFIER_FIELD: _usage_cases.ITEM_TWO_ID,
                    _usage_cases.STATUS_FIELD: _usage_cases.COMPLETED_STATUS,
                },
            },
        )
        trajectory = _trajectory.parse_codex_trajectory(stdout)
        self.assertEqual(trajectory.steps, ())
        self.assertEqual(
            _projections.source_item_classes(trajectory),
            {
                _usage_cases.ITEM_ONE_ID: (
                    _AGENT_MESSAGE_ITEM,
                    _usage_cases.EMPTY_DISPOSITION,
                ),
                _usage_cases.ITEM_TWO_ID: ("", _usage_cases.EMPTY_DISPOSITION),
            },
        )

    def test_accounting_is_carried_by_the_record(self) -> None:
        # The classification is only worth making if it reaches the record a
        # run is persisted from, under the field names a reader joins on.
        trajectory = _trajectory.parse_codex_trajectory(
            _BRACKETED_MESSAGE_STDOUT,
        )
        payload = json.loads(json.dumps(trajectory.to_dict(), default=str))
        self.assertEqual(
            len(payload[_SOURCE_ITEMS_KEY]),
            len(trajectory.source_items),
        )
        self.assertEqual(
            payload[_SOURCE_ITEMS_KEY][-1],
            {
                "item_id": _TRAILING_ITEM_ID,
                "item_type": _ERROR_ITEM,
                "disposition": _usage_cases.UNSUPPORTED_DISPOSITION,
            },
        )

    def test_unidentified_frames_are_not_accounted(self) -> None:
        # The accounting is keyed by the id, so a frame the stream left
        # unidentified still contributes its steps and nothing else -- every
        # such frame would otherwise be accounted under one shared name.
        stdout = _jsonl.jsonl({
            _usage_cases.TYPE_FIELD: _usage_cases.ITEM_COMPLETED_EVENT,
            _usage_cases.ITEM_FIELD: {
                _usage_cases.TYPE_FIELD: _COMMAND_EXECUTION_ITEM,
                _usage_cases.COMMAND_FIELD: _usage_cases.SHELL_LIST_COMMAND,
                "aggregated_output": _usage_cases.COMMAND_OUTPUT,
            },
        })
        trajectory = _trajectory.parse_codex_trajectory(stdout)
        self.assertEqual(
            [step.kind for step in trajectory.steps],
            [_usage_cases.TOOL_CALL_STEP, _usage_cases.TOOL_RESULT_STEP],
        )
        self.assertEqual(trajectory.source_items, ())


if __name__ == "__main__":
    unittest.main()
