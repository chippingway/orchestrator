# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Codex item streams the trajectory sink's accounting is read from.

Two streams and what each of them contains. One identifies an item per
disposition the parser assigns, so a record built from it can be audited id by
id; the other reports its payloads as lists of dicts rather than as text, which
is the shape a secret has to be reached inside leaf by leaf.
"""

import json
from types import MappingProxyType

_ID_KEY = "id"
_TYPE_KEY = "type"
_ITEM_KEY = "item"
_USAGE_KEY = "usage"
_TEXT_KEY = "text"
_STATUS_KEY = "status"
_COMMAND_KEY = "command"
_MESSAGE_KEY = "message"
# Codex spells both a terminal item status and a plan entry's done flag
# with this one word.
_COMPLETED = "completed"
_ITEM_STARTED_EVENT = "item.started"
_ITEM_COMPLETED_EVENT = "item.completed"


CODEX_ITEM_INPUT_TOKENS = 200


CODEX_ITEM_OUTPUT_TOKENS = 80


# The ids the accounting stream numbers its items with, in stream order.
_STORED_COMMAND_ID = "item_0"


_EXCLUDED_REASONING_ID = "item_1"


_ADJACENT_UNSUPPORTED_ID = "item_2"


_STORED_MESSAGE_ID = "item_3"


_TRAILING_UNSUPPORTED_ID = "item_4"


_EMPTY_COMMAND_ID = "item_5"


# Two item types the parser normalizes nothing for: one codex ships today, and
# one only a run that ended badly reports.
_ADJACENT_UNSUPPORTED_TYPE = "collab_tool_call"


_TRAILING_UNSUPPORTED_TYPE = "error"


_COMMAND_EXECUTION_ITEM = "command_execution"


_AGENT_MESSAGE_ITEM = "agent_message"


_REASONING_ITEM = "reasoning"


_TODO_LIST_ITEM = "todo_list"


_FILE_CHANGE_ITEM = "file_change"


_STORED = "stored"


_UNSUPPORTED = "unsupported"


_EXCLUDED = "excluded"


_EMPTY = "empty"


CODEX_HIDDEN_REASONING_TEXT = "the chain of thought no record carries"


CODEX_ACCOUNTING_OUTPUT = "codex done"


# What `codex_accounting_stdout` identifies, in first-seen order: the id, the
# item type the classification settled on, and the disposition it got.
CODEX_ACCOUNTED_ITEMS = (
    (_STORED_COMMAND_ID, _COMMAND_EXECUTION_ITEM, _STORED),
    (_EXCLUDED_REASONING_ID, _REASONING_ITEM, _EXCLUDED),
    (_ADJACENT_UNSUPPORTED_ID, _ADJACENT_UNSUPPORTED_TYPE, _UNSUPPORTED),
    (_STORED_MESSAGE_ID, _AGENT_MESSAGE_ITEM, _STORED),
    (_TRAILING_UNSUPPORTED_ID, _TRAILING_UNSUPPORTED_TYPE, _UNSUPPORTED),
    (_EMPTY_COMMAND_ID, _COMMAND_EXECUTION_ITEM, _EMPTY),
)


# The whole-run totals those items add up to, spelled out rather than counted
# from the table above so the expectation cannot drift the way the code that
# produces it might.
CODEX_ACCOUNTING_COUNTS = MappingProxyType({
    "identified": 6,
    _STORED: 2,
    _UNSUPPORTED: 2,
    _EXCLUDED: 1,
    _EMPTY: 1,
})


# The steps those items contribute: a command call and its result, one
# placeholder per unsupported item, and the message the run ends on.
CODEX_ACCOUNTING_STEP_COUNT = 5


_PLAN_ITEM_ID = "item_0"


_PATCH_ITEM_ID = "item_1"


def _frame(stream_item: dict, *, started: bool = False) -> dict:
    event = _ITEM_STARTED_EVENT if started else _ITEM_COMPLETED_EVENT
    return {_TYPE_KEY: event, _ITEM_KEY: stream_item}


def _stdout(frames: list[dict]) -> str:
    """Close a codex item stream with the cumulative usage frame."""
    frames.append({
        _TYPE_KEY: "turn_complete",
        _USAGE_KEY: {
            "input_tokens": CODEX_ITEM_INPUT_TOKENS,
            "output_tokens": CODEX_ITEM_OUTPUT_TOKENS,
        },
    })
    return "\n".join(json.dumps(frame) for frame in frames)


def codex_accounting_stdout() -> str:
    """A codex stdout carrying one item per disposition the parser assigns.

    The two item types nothing normalizes sit either side of the message that
    ends the run: with only the ordered steps to read, a placeholder next to
    the final answer and one after it are exactly where a reader cannot tell
    an item that was classified from one the parser never reached. The
    reasoning item beside them is the deliberate exclusion, and the command
    that opened without a command line the item whose frames carried nothing
    to store.
    """
    return _stdout([
        _frame(
            {
                _ID_KEY: _STORED_COMMAND_ID,
                _TYPE_KEY: _COMMAND_EXECUTION_ITEM,
                _COMMAND_KEY: "ls -la",
            },
            started=True,
        ),
        _frame({
            _ID_KEY: _STORED_COMMAND_ID,
            _TYPE_KEY: _COMMAND_EXECUTION_ITEM,
            _COMMAND_KEY: "ls -la",
            "aggregated_output": "command output",
        }),
        _frame({
            _ID_KEY: _EXCLUDED_REASONING_ID,
            _TYPE_KEY: _REASONING_ITEM,
            _TEXT_KEY: CODEX_HIDDEN_REASONING_TEXT,
        }),
        _frame({
            _ID_KEY: _ADJACENT_UNSUPPORTED_ID,
            _TYPE_KEY: _ADJACENT_UNSUPPORTED_TYPE,
            _STATUS_KEY: _COMPLETED,
        }),
        _frame({
            _ID_KEY: _STORED_MESSAGE_ID,
            _TYPE_KEY: _AGENT_MESSAGE_ITEM,
            _TEXT_KEY: CODEX_ACCOUNTING_OUTPUT,
        }),
        _frame({
            _ID_KEY: _TRAILING_UNSUPPORTED_ID,
            _TYPE_KEY: _TRAILING_UNSUPPORTED_TYPE,
            _MESSAGE_KEY: "stream ended badly",
        }),
        _frame(
            {
                _ID_KEY: _EMPTY_COMMAND_ID,
                _TYPE_KEY: _COMMAND_EXECUTION_ITEM,
            },
            started=True,
        ),
    ])


def codex_structured_payload_stdout(*, plan_text: str, changed_path: str) -> str:
    """A codex stdout whose two items report lists of dicts, not text.

    A plan republished as it is worked through and a patch naming the paths it
    touched are the codex payloads a record stores as structure, so a secret
    inside one is reachable only leaf by leaf.
    """
    opened_plan = [{_TEXT_KEY: plan_text, _COMPLETED: False}]
    worked_plan = [{_TEXT_KEY: plan_text, _COMPLETED: True}]
    changes = [{"path": changed_path, "kind": "update"}]
    return _stdout([
        _frame(
            {
                _ID_KEY: _PLAN_ITEM_ID,
                _TYPE_KEY: _TODO_LIST_ITEM,
                "items": opened_plan,
            },
            started=True,
        ),
        _frame({
            _ID_KEY: _PLAN_ITEM_ID,
            _TYPE_KEY: _TODO_LIST_ITEM,
            "items": worked_plan,
        }),
        _frame(
            {
                _ID_KEY: _PATCH_ITEM_ID,
                _TYPE_KEY: _FILE_CHANGE_ITEM,
                "changes": changes,
                _STATUS_KEY: "in_progress",
            },
            started=True,
        ),
        _frame({
            _ID_KEY: _PATCH_ITEM_ID,
            _TYPE_KEY: _FILE_CHANGE_ITEM,
            "changes": changes,
            _STATUS_KEY: _COMPLETED,
        }),
    ])
