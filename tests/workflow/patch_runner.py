# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Stage-family adapters around the shared workflow patch context."""
from __future__ import annotations

from functools import partial

from orchestrator.workflow.stages.conflicts import handler as _conflicts
from orchestrator.workflow.stages.fixing import handler as _fixing
from orchestrator.workflow.stages.implementing import handler as _implementing
from orchestrator.workflow.stages.in_review import handler as _in_review
from orchestrator.workflow.stages.validating import handler as _validating
from tests.workflow.patch_context import _patch_and_run
from tests.workflow.patch_models import _WorkflowRunContext
from tests.workflow.repo_values import _TEST_SPEC


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
                _implementing._handle_implementing,
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
                _fixing._handle_fixing,
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
                _validating._handle_validating,
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
                _in_review._handle_in_review,
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
                _conflicts._handle_resolving_conflict,
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
