# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Stage-family adapters around the shared workflow patch context."""
from __future__ import annotations

import contextlib
from functools import partial
from types import MappingProxyType
from unittest.mock import patch

from orchestrator import analytics, workflow
from orchestrator.git.verification import runner as _verify_runner
from orchestrator.git.worktrees import terminal as _worktree_terminal

from tests.workflow_patch_builders import _build_workflow_mocks
from tests.workflow_patch_models import _WorkflowRunContext
from tests.workflow_repo_values import _TEST_SPEC

# The validating approval gate and the question / terminal cleanup callers
# reach these owners directly, so their mocks have to land on the owner --
# patching the workflow facade would not intercept the call.
_OWNER_PATCH_TARGETS = MappingProxyType(
    {
        "_run_verify_commands": _verify_runner,
        "_cleanup_question_worktree": _worktree_terminal,
        "_cleanup_terminal_branch": _worktree_terminal,
    },
)


def _patch_and_run(callable_, context: _WorkflowRunContext):
    workflow_mocks = _build_workflow_mocks(context)
    with contextlib.ExitStack() as stack:
        stack.enter_context(patch.object(
            analytics,
            "ANALYTICS_LOG_PATH",
            context.analytics_log_path,
        ))
        stack.enter_context(patch.object(
            analytics,
            "TRAJECTORY_LOG_PATH",
            context.trajectory_log_path,
        ))
        for attribute, attribute_mock in workflow_mocks.items():
            stack.enter_context(patch.object(
                _OWNER_PATCH_TARGETS.get(attribute, workflow),
                attribute,
                attribute_mock,
            ))
        callable_()
    return workflow_mocks


class _ImplementationWorkflowMixin:
    def _run_implementing(
        self,
        github,
        issue,
        *,
        run_agent,
        **run_options,
    ):
        return self._run(
            partial(
                workflow._handle_implementing,
                github,
                _TEST_SPEC,
                issue,
            ),
            run_agent=run_agent,
            **run_options,
        )

    def _run_fixing(
        self,
        github,
        issue,
        *,
        run_agent,
        **run_options,
    ):
        return self._run(
            partial(
                workflow._handle_fixing,
                github,
                _TEST_SPEC,
                issue,
            ),
            run_agent=run_agent,
            **run_options,
        )


class _ReviewWorkflowMixin:
    def _run_validating(
        self,
        github,
        issue,
        *,
        run_agent,
        **run_options,
    ):
        return self._run(
            partial(
                workflow._handle_validating,
                github,
                _TEST_SPEC,
                issue,
            ),
            run_agent=run_agent,
            **run_options,
        )

    def _run_in_review(
        self,
        github,
        issue,
        *,
        run_agent,
        **run_options,
    ):
        return self._run(
            partial(
                workflow._handle_in_review,
                github,
                _TEST_SPEC,
                issue,
            ),
            run_agent=run_agent,
            **run_options,
        )


class _ConflictWorkflowMixin:
    def _run_resolving_conflict(
        self,
        github,
        issue,
        *,
        run_agent,
        **run_options,
    ):
        return self._run(
            partial(
                workflow._handle_resolving_conflict,
                github,
                _TEST_SPEC,
                issue,
            ),
            run_agent=run_agent,
            **run_options,
        )


class _StageWorkflowMixin(
    _ImplementationWorkflowMixin,
    _ReviewWorkflowMixin,
    _ConflictWorkflowMixin,
):
    """Combine stage-family entry points."""


class _PatchedWorkflowMixin(_StageWorkflowMixin):
    """Run a workflow handler inside the standard hermetic patch set."""

    def _run(self, callable_, *, run_agent, **run_options):
        context = _WorkflowRunContext(
            run_agent=run_agent,
            **run_options,
        )
        return _patch_and_run(callable_, context)
