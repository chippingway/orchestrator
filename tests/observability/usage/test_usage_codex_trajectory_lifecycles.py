# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Codex plan and patch lifecycle tests."""

import unittest

from orchestrator.observability.usage import trajectory as _trajectory, trajectory_models as _records
from tests.observability.usage import (
    usage_codex_tool_events as _tool_events,
    usage_jsonl_helpers as _jsonl,
    usage_test_values as _usage_cases,
)

_TODO_LIST_NAME = "todo_list"
_FILE_CHANGE_NAME = "file_change"
_ITEM_UPDATED_EVENT = "item.updated"
_CHANGES_FIELD = "changes"


class CodexPlanAndPatchLifecycleTest(unittest.TestCase):
    """The two items codex republishes in full, over every way they end.

    A plan is one operation however often it is rewritten: it is invoked with
    the list it opened on, and the state it settled in is its outcome, which
    only the frame that completes the item reports. A patch states how it
    ended in the ``status`` it carries either way, so a terminal status is its
    outcome. Neither an unfinished plan nor a patch still being applied is
    credited with one, and every revision in between folds into the item's own
    pair rather than adding a step beside it.
    """

    def test_captured_lifecycles_pair_once(self) -> None:
        trajectory = _trajectory.parse_codex_trajectory(
            _tool_events.LIFECYCLE_RUN_STDOUT,
        )
        self.assertEqual(
            trajectory.steps,
            (
                # The plan the run opened with, not the revision that followed
                # it, and the state its completing frame reported.
                _records.TrajectoryStep(
                    kind=_usage_cases.TOOL_CALL_STEP,
                    name=_TODO_LIST_NAME,
                    tool_id=_tool_events.PLAN_ITEM_ID,
                    content=_tool_events.plan_steps(
                        (_tool_events.TODO_TEXT, False),
                        (_tool_events.DOCS_TODO_TEXT, False),
                    ),
                ),
                _records.TrajectoryStep(
                    kind=_usage_cases.TOOL_RESULT_STEP,
                    tool_id=_tool_events.PLAN_ITEM_ID,
                    content=_tool_events.plan_steps(
                        (_tool_events.TODO_TEXT, True),
                        (_tool_events.DOCS_TODO_TEXT, True),
                    ),
                ),
                # A patch reported on one frame is still a pair, built from
                # the fields that frame carried.
                _records.TrajectoryStep(
                    kind=_usage_cases.TOOL_CALL_STEP,
                    name=_FILE_CHANGE_NAME,
                    tool_id=_tool_events.PATCH_ITEM_ID,
                    content=_tool_events.change_list(
                        _tool_events.CHANGED_PATH,
                        _tool_events.UPDATE_CHANGE_KIND,
                    ),
                ),
                _records.TrajectoryStep(
                    kind=_usage_cases.TOOL_RESULT_STEP,
                    tool_id=_tool_events.PATCH_ITEM_ID,
                    content=_usage_cases.COMPLETED_STATUS,
                ),
                _records.TrajectoryStep(
                    kind=_usage_cases.TOOL_CALL_STEP,
                    name=_FILE_CHANGE_NAME,
                    tool_id=_tool_events.FAILED_PATCH_ITEM_ID,
                    content=_tool_events.change_list(
                        _tool_events.DOCS_PATH,
                        _tool_events.ADD_CHANGE_KIND,
                    ),
                ),
                _records.TrajectoryStep(
                    kind=_usage_cases.TOOL_RESULT_STEP,
                    tool_id=_tool_events.FAILED_PATCH_ITEM_ID,
                    content=_usage_cases.FAILED_STATUS,
                ),
                # What the stream stopped on: a plan and a patch the run never
                # reported an outcome for, each an invocation with nothing
                # under it.
                _records.TrajectoryStep(
                    kind=_usage_cases.TOOL_CALL_STEP,
                    name=_TODO_LIST_NAME,
                    tool_id=_tool_events.ABANDONED_PLAN_ITEM_ID,
                    content=_tool_events.plan_steps(
                        (_tool_events.RETRY_TODO_TEXT, False),
                    ),
                ),
                _records.TrajectoryStep(
                    kind=_usage_cases.TOOL_CALL_STEP,
                    name=_FILE_CHANGE_NAME,
                    tool_id=_tool_events.ABANDONED_PATCH_ITEM_ID,
                    content=_tool_events.change_list(
                        _tool_events.DOCS_PATH,
                        _tool_events.ADD_CHANGE_KIND,
                    ),
                ),
            ),
        )

    def test_patch_outcome_follows_the_status(self) -> None:
        # Which frame ends a patch is the status's answer rather than the
        # event's: a failure reported before the item completes is still the
        # outcome, and a patch that has not ended yet has none however its
        # frame is typed.
        failed_steps = self._patch_steps(
            _ITEM_UPDATED_EVENT,
            _usage_cases.FAILED_STATUS,
        )
        self.assertEqual(
            failed_steps,
            [
                (_usage_cases.TOOL_CALL_STEP, self._patched_changes()),
                (_usage_cases.TOOL_RESULT_STEP, _usage_cases.FAILED_STATUS),
            ],
        )
        self.assertEqual(
            self._patch_steps(
                _usage_cases.ITEM_COMPLETED_EVENT,
                _usage_cases.IN_PROGRESS_STATUS,
            ),
            [(_usage_cases.TOOL_CALL_STEP, self._patched_changes())],
        )

    def _patched_changes(self) -> list[dict]:
        return _tool_events.change_list(
            _tool_events.CHANGED_PATH,
            _tool_events.UPDATE_CHANGE_KIND,
        )

    def _patch_steps(self, event_type: str, status: str) -> list:
        stdout = _jsonl.jsonl({
            _usage_cases.TYPE_FIELD: event_type,
            _usage_cases.ITEM_FIELD: {
                _usage_cases.IDENTIFIER_FIELD: _usage_cases.ITEM_ONE_ID,
                _usage_cases.TYPE_FIELD: _FILE_CHANGE_NAME,
                _CHANGES_FIELD: self._patched_changes(),
                _usage_cases.STATUS_FIELD: status,
            },
        })
        trajectory = _trajectory.parse_codex_trajectory(stdout)
        return [(step.kind, step.content) for step in trajectory.steps]
