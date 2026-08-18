# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Fixtures shared across the workflow tests, re-exported explicitly.

Each name below is defined by the leaf beside it -- the event names, the two
label vocabularies, the repo spec and backend values, the pinned-state keys and
role names, the verdict messages, the value builders, and the hermetic patch
context a stage handler runs inside. This module is the one import site the
tests that span several of those leaves reach them through.
"""
from __future__ import annotations

from tests.workflow import other_labels as _other_labels
from tests.workflow import patch_models as _patch_models
from tests.workflow import patch_runner as _patch_runner
from tests.workflow import repo_values as _repo_values
from tests.workflow import stage_labels as _stage_labels
from tests.workflow import stage_names as _stage_names
from tests.workflow import state_values as _state_values
from tests.workflow import value_helpers as _value_helpers
from tests.workflow import verdict_values as _verdict_values
from tests.workflow.engine import event_values as _event_values

EVENT_AGENT_EXIT = _event_values.EVENT_AGENT_EXIT
EVENT_AGENT_SPAWN = _event_values.EVENT_AGENT_SPAWN
EVENT_AGENT_TRAJECTORY = _event_values.EVENT_AGENT_TRAJECTORY
EVENT_PR_CLOSED_WITHOUT_MERGE = _event_values.EVENT_PR_CLOSED_WITHOUT_MERGE
EVENT_PR_MERGED = _event_values.EVENT_PR_MERGED
EVENT_SKILL_TRIGGERED = _event_values.EVENT_SKILL_TRIGGERED
EVENT_STAGE_ENTER = _event_values.EVENT_STAGE_ENTER
EVENT_STAGE_EVALUATION = _event_values.EVENT_STAGE_EVALUATION

LABEL_BLOCKED = _other_labels.LABEL_BLOCKED
LABEL_DONE = _other_labels.LABEL_DONE
LABEL_READY = _other_labels.LABEL_READY
LABEL_REJECTED = _other_labels.LABEL_REJECTED
LABEL_RESOLVING_CONFLICT = _other_labels.LABEL_RESOLVING_CONFLICT
LABEL_UMBRELLA = _other_labels.LABEL_UMBRELLA

LABEL_DECOMPOSING = _stage_labels.LABEL_DECOMPOSING
LABEL_DISCUSSION = _stage_labels.LABEL_DISCUSSION
LABEL_DOCUMENTING = _stage_labels.LABEL_DOCUMENTING
LABEL_FIXING = _stage_labels.LABEL_FIXING
LABEL_IMPLEMENTING = _stage_labels.LABEL_IMPLEMENTING
LABEL_IN_REVIEW = _stage_labels.LABEL_IN_REVIEW
LABEL_QUESTION = _stage_labels.LABEL_QUESTION
LABEL_VALIDATING = _stage_labels.LABEL_VALIDATING

STAGE_DECOMPOSING = _stage_names.STAGE_DECOMPOSING
STAGE_DISCUSSION = _stage_names.STAGE_DISCUSSION
STAGE_DOCUMENTING = _stage_names.STAGE_DOCUMENTING
STAGE_FIXING = _stage_names.STAGE_FIXING
STAGE_IMPLEMENTING = _stage_names.STAGE_IMPLEMENTING
STAGE_IN_REVIEW = _stage_names.STAGE_IN_REVIEW
STAGE_QUESTION = _stage_names.STAGE_QUESTION
STAGE_RESOLVING_CONFLICT = _stage_names.STAGE_RESOLVING_CONFLICT
STAGE_VALIDATING = _stage_names.STAGE_VALIDATING

BACKEND_CLAUDE = _repo_values.BACKEND_CLAUDE
BASE_TIP_SHA = _repo_values.BASE_TIP_SHA
BACKEND_CODEX = _repo_values.BACKEND_CODEX
STATE_CLOSED = _repo_values.STATE_CLOSED
STATE_OPEN = _repo_values.STATE_OPEN
TEST_BASE_BRANCH = _repo_values.TEST_BASE_BRANCH
TEST_REPO_SLUG = _repo_values.TEST_REPO_SLUG
_FAKE_WT = _repo_values._FAKE_WT
_TEST_SPEC = _repo_values._TEST_SPEC

KEY_AWAITING_HUMAN = _state_values.KEY_AWAITING_HUMAN
KEY_ISSUE_AGENT_RUNS = _state_values.KEY_ISSUE_AGENT_RUNS
KEY_ISSUE_TOTAL_TOKENS = _state_values.KEY_ISSUE_TOTAL_TOKENS
KEY_LAST_ACTION_COMMENT_ID = _state_values.KEY_LAST_ACTION_COMMENT_ID
KEY_PARENT_NUMBER = _state_values.KEY_PARENT_NUMBER
KEY_PARK_REASON = _state_values.KEY_PARK_REASON
ROLE_DEVELOPER = _state_values.ROLE_DEVELOPER
ROLE_REVIEWER = _state_values.ROLE_REVIEWER

REVIEW_APPROVED_MESSAGE = _verdict_values.REVIEW_APPROVED_MESSAGE
REVIEW_CHANGES_REQUESTED_MESSAGE = _verdict_values.REVIEW_CHANGES_REQUESTED_MESSAGE
VERDICT_APPROVED = _verdict_values.VERDICT_APPROVED
VERDICT_CHANGES_REQUESTED = _verdict_values.VERDICT_CHANGES_REQUESTED
VERDICT_UNKNOWN = _verdict_values.VERDICT_UNKNOWN

_analytics_records = _value_helpers._analytics_records
_fake_worktree = _value_helpers._fake_worktree
_iso_hours_ago = _value_helpers._iso_hours_ago
_issue_branch = _value_helpers._issue_branch
_manifest = _value_helpers._manifest
_state_with_pr_number = _value_helpers._state_with_pr_number

_agent = _patch_models._agent
_PatchedWorkflowMixin = _patch_runner._PatchedWorkflowMixin
