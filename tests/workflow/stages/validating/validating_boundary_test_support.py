# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Fixtures for the borrowed-owner boundary cases.

`_facade_out_of_the_path` is the shape those cases share: patching the owner
alone would not pin a boundary, because the facade resolves each export by
`getattr` on that same owner at first read and would hand back the owner's mock
too. Seating a distinct mock in the facade namespace decides the read instead,
so a call site that still goes through `_wf` trips the guard.
"""
from __future__ import annotations

import contextlib
from typing import NamedTuple
from unittest.mock import patch

from orchestrator import workflow
from orchestrator.workflow.stages.validating import models as _models

from tests.fakes import FakeComment, FakeGitHubClient, FakeUser, make_issue
from tests.workflow_helpers import _FAKE_WT, _agent

BOUNDARY_ISSUE = 770
BOUNDARY_PR = 771
BOUNDARY_BRANCH = "orchestrator/geserdugarov__agent-orchestrator/issue-770"
BEFORE_SHA = "beforeAA"
PARK_COMMENT_ID = 900
HUMAN_REPLY_ID = 901


class _Scenario(NamedTuple):
    """One parked `validating` issue and the state its owners read."""

    gh: FakeGitHubClient
    issue: object
    state: object


def _seeded(**state_fields) -> _Scenario:
    """A `validating` issue carrying one human reply, and its pinned state."""
    gh = FakeGitHubClient()
    issue = make_issue(
        BOUNDARY_ISSUE,
        label="validating",
        comments=[
            FakeComment(
                id=PARK_COMMENT_ID,
                body="park",
                user=FakeUser("orchestrator"),
            ),
            FakeComment(
                id=HUMAN_REPLY_ID,
                body="fix the import",
                user=FakeUser("geserdugarov"),
            ),
        ],
    )
    gh.add_issue(issue)
    gh.seed_state(
        BOUNDARY_ISSUE,
        pr_number=BOUNDARY_PR,
        last_action_comment_id=PARK_COMMENT_ID,
        **state_fields,
    )
    return _Scenario(gh, issue, gh.read_pinned_state(issue))


def _dev_run() -> _models._DevFixRun:
    return _models._DevFixRun(_FAKE_WT, _agent(), BEFORE_SHA)


class _OwnerBoundaryMixin:
    """Assert a block reached no borrowed helper through the facade."""

    @contextlib.contextmanager
    def _facade_out_of_the_path(self, *export_names, returns=None):
        # Each guard returns the shape its caller unpacks, so a regression
        # fails on the assertion below rather than on an unpack of a bare mock.
        shapes = returns or {}
        with contextlib.ExitStack() as stack:
            guards = [
                (
                    name,
                    stack.enter_context(patch.object(
                        workflow, name, return_value=shapes.get(name),
                    )),
                )
                for name in export_names
            ]
            yield
        for name, guard in guards:
            self.assertFalse(
                guard.called, f"{name} was read off the workflow facade",
            )
