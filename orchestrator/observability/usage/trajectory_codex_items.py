# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What one `codex exec --json` stream item normalizes to.

Codex reports its whole operational surface as `item.started` / `item.updated`
/ `item.completed` frames over a small set of typed items, so this owner
decides, per item type, which trajectory step family an item belongs to and
which of its own fields are the invocation and the outcome. The builder in
`trajectory_codex` correlates the frames of one item by `item.id` and orders
what comes back, which is what collapses a started/completed pair into one
call and one result.

Each family here is one operation the run can be read back from: the shell
command the agent ran, the web search it issued, the MCP tool it called, the
patch it applied, and the plan it worked to. The patch is codex's *custom*
(freeform) tool surface -- the model calls `apply_patch`, and the exec stream
reports the call and its outcome as a `file_change` item -- so a custom tool
call normalizes to a pair here like any other. `codex exec --json` publishes no
separate custom / dynamic tool item type: its whole item vocabulary is
`agent_message`, `reasoning`, `command_execution`, `file_change`,
`mcp_tool_call`, `collab_tool_call`, `web_search`, `todo_list`, and `error`
(verified against codex-cli 0.148.0); `custom_tool_call` is a raw
model-response / rollout spelling that never reaches this stream.

An item type nothing here claims becomes a metadata-only placeholder naming the
type, the id, and the status, so an operational surface a later codex release
adds stays visible in the timeline instead of dropping out of it silently.
Reasoning is the one deliberate exclusion: its text is hidden model content no
record may carry, and a placeholder per reasoning item would be noise rather
than a diagnostic. The exclusion is still named rather than silent --
`trajectory_codex` accounts every identified item by id, so a reasoning item
is a recorded classification there while neither its text nor any other field
of it leaves this module.

Nothing here fabricates an outcome. A result payload is contributed only by the
frame that actually carries one, which is what leaves a call the stream failed
or never completed visible as an invocation with no result beneath it. Which
frame that is differs by item: an item codex ends with `item.completed` is
read from that frame, while a patch states how it ended in a `status` it
carries either way, so the terminal status is what ends it.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from orchestrator.observability.usage import (
    protocol,
    skills_codex,
)
from orchestrator.observability.usage.trajectory_models import TrajectoryStep


AGENT_MESSAGE = "agent_message"
COMMAND_EXECUTION = skills_codex.COMMAND_EXECUTION
FILE_CHANGE = "file_change"
MCP_TOOL_CALL = "mcp_tool_call"
REASONING = "reasoning"
TODO_LIST = "todo_list"
WEB_SEARCH = "web_search"

ITEM_COMPLETED = "item.completed"

ASSISTANT_MESSAGE = "assistant_message"
TOOL_CALL = "tool_call"
TOOL_RESULT = "tool_result"
UNSUPPORTED_ITEM = "unsupported_item"

ACTION = "action"
AGGREGATED_OUTPUT = "aggregated_output"
ARGUMENTS = "arguments"
CHANGES = "changes"
COMMAND = "command"
ERROR = "error"
PLAN_STEPS = "items"
QUERY = "query"
SERVER = "server"
STATUS = "status"
TEXT = "text"
TOOL = "tool"
NAME_SEPARATOR = "."

# A patch reports `in_progress` until it has ended, so these two are the whole
# of what one says about its outcome -- and saying it is what ends it.
TERMINAL_STATUSES = frozenset(("completed", "failed"))

MISSING = object()


@dataclass
class CodexItemPayloads:
    """The step family one item belongs to and the payloads it carries.

    `MISSING` is what separates a field a frame did not carry from one it
    carried empty: the builder merges frame by frame and only overwrites what
    a frame actually reported, so a completed frame that omits a field leaves
    the started frame's value standing.
    """

    kind: str
    name: str = ""
    call_payload: Any = MISSING
    result_payload: Any = MISSING
    keeps_first_call: bool = False

    def contributes_call(self, recorded_call: Any) -> bool:
        """Whether this frame's invocation replaces the one already recorded.

        An item codex republishes whole on every frame -- a plan, rewritten as
        it is worked through -- is invoked once, by the frame that opened it,
        so a later frame revises the outcome rather than the call. Every other
        item is named by whichever frame filled the field last, which is how a
        search that announces itself with an empty query is still recorded
        under the one it ran.
        """
        if self.call_payload is MISSING:
            return False
        return not (self.keeps_first_call and recorded_call is not MISSING)

    def steps(self, tool_id: str) -> tuple[TrajectoryStep, ...]:
        """Order what this item accumulated into the steps it contributes."""
        if self.kind == ASSISTANT_MESSAGE:
            if self.call_payload is MISSING:
                return ()
            return (
                TrajectoryStep(
                    kind=ASSISTANT_MESSAGE,
                    content=self.call_payload,
                ),
            )
        if self.kind == UNSUPPORTED_ITEM:
            return (
                TrajectoryStep(
                    kind=UNSUPPORTED_ITEM,
                    name=self.name,
                    tool_id=tool_id,
                    content=self.call_payload,
                ),
            )
        return self._tool_steps(tool_id)

    def _tool_steps(self, tool_id: str) -> tuple[TrajectoryStep, ...]:
        tool_steps: list[TrajectoryStep] = []
        if self.call_payload is not MISSING:
            tool_steps.append(
                TrajectoryStep(
                    kind=TOOL_CALL,
                    name=self.name,
                    tool_id=tool_id,
                    content=self.call_payload,
                ),
            )
        if self.result_payload is not MISSING:
            tool_steps.append(
                TrajectoryStep(
                    kind=TOOL_RESULT,
                    tool_id=tool_id,
                    content=self.result_payload,
                ),
            )
        return tuple(tool_steps)


def _agent_message(
    stream_item: dict[str, Any],
    completed: bool,
) -> CodexItemPayloads:
    """The agent's own text turn."""
    message = stream_item.get(TEXT)
    spoken = isinstance(message, str) and message
    return CodexItemPayloads(
        kind=ASSISTANT_MESSAGE,
        call_payload=message if spoken else MISSING,
    )


def _command_execution(
    stream_item: dict[str, Any],
    completed: bool,
) -> CodexItemPayloads:
    """A shell command: what was run, and the output it aggregated.

    A running command already carries the `aggregated_output` field, empty,
    so it is the completing frame rather than the field's presence that says
    there is an output to record -- a command still running, or one killed
    before it exited, would otherwise be credited with an empty result it
    never produced.
    """
    command = stream_item.get(COMMAND)
    return CodexItemPayloads(
        kind=TOOL_CALL,
        name=COMMAND_EXECUTION,
        call_payload=command if isinstance(command, str) else MISSING,
        result_payload=(
            stream_item.get(AGGREGATED_OUTPUT, MISSING) if completed else MISSING
        ),
    )


def _web_search(
    stream_item: dict[str, Any],
    completed: bool,
) -> CodexItemPayloads:
    """A web search: the query it ran, and the action it resolved to.

    A search announces itself with an empty query and an unresolved action and
    only names itself on the frame that completes it, so the completed frame
    is both what the call is read from -- it is merged last -- and the only one
    that reports an outcome.
    """
    return CodexItemPayloads(
        kind=TOOL_CALL,
        name=WEB_SEARCH,
        call_payload=stream_item.get(QUERY, MISSING),
        result_payload=(
            stream_item.get(ACTION, MISSING) if completed else MISSING
        ),
    )


def _mcp_tool_call(
    stream_item: dict[str, Any],
    completed: bool,
) -> CodexItemPayloads:
    """An MCP tool call: its arguments, and the result or error it ended on.

    A call that failed reports it either way -- the server's own error
    payload, or a result the server marked as the failure -- so the outcome is
    whichever of the two the frame filled in.
    """
    outcome = stream_item.get(protocol.RESULT_KEY)
    if outcome is None:
        outcome = stream_item.get(ERROR)
    name_parts = [
        part
        for part in (stream_item.get(SERVER), stream_item.get(TOOL))
        if isinstance(part, str) and part
    ]
    return CodexItemPayloads(
        kind=TOOL_CALL,
        name=NAME_SEPARATOR.join(name_parts) or MCP_TOOL_CALL,
        call_payload=stream_item.get(ARGUMENTS, MISSING),
        result_payload=MISSING if outcome is None else outcome,
    )


def _file_change(
    stream_item: dict[str, Any],
    completed: bool,
) -> CodexItemPayloads:
    """A patch application: the paths it touched and how it ended.

    The change list is recorded as the structure codex reports -- one entry
    per path, each naming the kind of edit that path received -- so a
    downstream walk reaches a path as a field rather than having to read it
    back out of prose. The `status` is the whole of what a patch says about
    its outcome, and it says `in_progress` until there is one, so a terminal
    status is the result and nothing else is: that is what keeps a patch that
    failed, which reports it on whichever frame ends the item, apart from one
    the run left half applied.
    """
    status = stream_item.get(STATUS)
    ended = isinstance(status, str) and status in TERMINAL_STATUSES
    return CodexItemPayloads(
        kind=TOOL_CALL,
        name=FILE_CHANGE,
        call_payload=stream_item.get(CHANGES, MISSING),
        result_payload=status if ended else MISSING,
    )


def _todo_list(
    stream_item: dict[str, Any],
    completed: bool,
) -> CodexItemPayloads:
    """A plan: the list it opened with, and the state it ended in.

    Codex republishes the whole plan on every revision, so one plan is one
    operation however often it is rewritten: the opening frame's list is the
    call, the frame that completes the item carries the state the plan settled
    in, and the revisions between them fold into that same pair rather than
    each becoming a step of its own. A plan the run never completed keeps its
    call alone -- where a plan stood when the stream stopped is not where it
    ended.
    """
    plan = stream_item.get(PLAN_STEPS, MISSING)
    return CodexItemPayloads(
        kind=TOOL_CALL,
        name=TODO_LIST,
        call_payload=plan,
        result_payload=plan if completed else MISSING,
        keeps_first_call=True,
    )


ItemNormalizer = Callable[[dict[str, Any], bool], CodexItemPayloads]
NORMALIZERS: Mapping[str, ItemNormalizer] = MappingProxyType({
    AGENT_MESSAGE: _agent_message,
    COMMAND_EXECUTION: _command_execution,
    FILE_CHANGE: _file_change,
    MCP_TOOL_CALL: _mcp_tool_call,
    TODO_LIST: _todo_list,
    WEB_SEARCH: _web_search,
})


def normalize_item(
    stream_item: dict[str, Any],
    completed: bool,
) -> CodexItemPayloads | None:
    """Normalize one item frame, or `None` for one no record carries.

    An unclaimed item type yields the placeholder rather than nothing, so the
    only frames that leave no trace are reasoning and an item too malformed to
    name a type.
    """
    item_type = stream_item.get(protocol.TYPE)
    if not isinstance(item_type, str) or item_type == REASONING:
        return None
    normalizer = NORMALIZERS.get(item_type)
    if normalizer is None:
        status = stream_item.get(STATUS)
        return CodexItemPayloads(
            kind=UNSUPPORTED_ITEM,
            name=item_type,
            call_payload=status if isinstance(status, str) else None,
        )
    return normalizer(stream_item, completed)
