# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The tick owner's per-tick pass order."""
from __future__ import annotations

import functools
import unittest
from unittest.mock import patch

from orchestrator.skills import catalog
from orchestrator.workflow.engine import dispatch, tick
from tests.support.fakes import FakeGitHubClient
from tests.workflow.git_owners import seam_patch
from tests.workflow.repo_values import _TEST_SPEC

_EXPECTED_PASSES = ("refresh", "sweep", "catalog", "dispatch")

_REFRESH_BASE = "_refresh_base_and_worktrees"


class _PassRecorder:
    """Stands in for one tick pass and notes when it fired."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def pass_named(self, name: str):
        return functools.partial(self._record, name)

    def _record(self, name: str, *_args, **_kwargs) -> None:
        self.calls.append(name)


class TickPassOrderTest(unittest.TestCase):
    """The passes run once each, in the order the later ones depend on."""

    def test_pass_order_holds_on_both_routes(self) -> None:
        # The base fetch has to land before the two passes that read what it
        # left behind -- a handler would otherwise rebase onto the SHA its
        # worktree was created at, and the catalog would ls-tree a stale base
        # ref -- and the sweep and the catalog have to sit before the
        # scheduler / in-tick split rather than inside one branch, or a
        # scheduler-driven deployment silently stops labeling outsider PRs and
        # reporting its skill catalog.
        for scheduler in (None, object()):
            with self.subTest(scheduler=scheduler is not None):
                self.assertEqual(
                    self._passes_driven_by(scheduler), list(_EXPECTED_PASSES),
                )

    def _passes_driven_by(self, scheduler) -> list[str]:
        recorder = _PassRecorder()
        with (
            seam_patch(_REFRESH_BASE, recorder.pass_named("refresh")),
            patch.object(
                tick, "_sweep_community_contribution_prs",
                recorder.pass_named("sweep"),
            ),
            patch.object(
                catalog, "_emit_repo_skill_catalog",
                recorder.pass_named("catalog"),
            ),
            patch.object(
                dispatch, "_dispatch_via_scheduler",
                recorder.pass_named("dispatch"),
            ),
            patch.object(
                tick, "_run_sequential_tick", recorder.pass_named("dispatch"),
            ),
        ):
            tick.tick(FakeGitHubClient(), _TEST_SPEC, scheduler=scheduler)
        return recorder.calls


if __name__ == "__main__":
    unittest.main()
