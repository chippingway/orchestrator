# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The two guards a stage's borrowed-owner boundary is pinned with.

A stage that reaches a helper it does not own has exactly one right
interception point: the module its call site names. Both guards here assert
that from the other side -- the owner mock has to answer, and the mock left
sitting on `orchestrator.workflow` has to stay untouched -- so a call site that
drifts back to the facade fails the test written for it instead of passing
through the facade's cached forward to the same object.

`GIT_SEAM_OWNERS` is the one place a stage test says which git module defines
each name, so the stages that read the same probe pin it on the same module.
"""
from __future__ import annotations

import contextlib
from unittest.mock import patch

from orchestrator import workflow

from tests.workflow_git_owners import seam_patch

_READ_OFF_THE_FACADE = "{0} was read off the workflow facade"

_AUTO_REBASE_PARK_REASONS = "_AUTO_REBASE_PARK_REASONS"


class OwnerBoundaryMixin:
    """Assert a block reached no borrowed helper through the facade."""

    @contextlib.contextmanager
    def facade_out_of_the_path(self, export_name, returns=None):
        # The guard returns the shape its caller unpacks, so a regression
        # fails on the assertion below rather than on an unpack of a bare mock.
        with contextlib.ExitStack() as stack:
            guard = stack.enter_context(
                patch.object(workflow, export_name, return_value=returns),
            )
            yield
        self.assertFalse(guard.called, _READ_OFF_THE_FACADE.format(export_name))

    @contextlib.contextmanager
    def git_seams_on_owners(self, **answers):
        """Answer each named git seam on its owner, facade guarded.

        Every name is held on both sides, so a call site reading one off
        `orchestrator.workflow` gets the guard instead of the answer and the
        assertion below names it.
        """
        with contextlib.ExitStack() as stack:
            guards = {
                seam: stack.enter_context(patch.object(workflow, seam))
                for seam in answers
            }
            for seam, answer in answers.items():
                stack.enter_context(seam_patch(seam, answer))
            yield
        self._assert_owned(guards)

    def facade_park_reasons_empty(self):
        """Empty the auto-rebase park vocabulary on the facade.

        A frozenset is read rather than called, so the facade side is pinned
        by the answer it would give -- one that matches no park -- instead of
        by a guard that could record a call.
        """
        return patch.object(workflow, _AUTO_REBASE_PARK_REASONS, frozenset())

    def _assert_owned(self, guards) -> None:
        for seam, guard in guards.items():
            with self.subTest(seam=seam):
                self.assertFalse(
                    guard.called, _READ_OFF_THE_FACADE.format(seam),
                )
