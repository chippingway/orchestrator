# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""One `discussion` tick, which is deliberately nothing at all.

The label is an operator's hold on an issue whose scope is still being settled
between humans, so the correct amount of work for a tick to do is none: no
agent, no worktree, no comment, and above all no label write. Only a human ends
the hold, by relabeling the issue to `done` or `rejected` -- the two edges
`ALLOWED_TRANSITIONS` grants it -- or by taking the label off and letting the
issue route as whatever it becomes.

Doing nothing still needs a handler, because the alternative is the dispatcher
falling through to its unrecognized-label branch and warning about the same
issue on every tick. Routing the label here is what makes an operator applying
it a quiet, reversible act.
"""
from __future__ import annotations

from github.Issue import Issue

from orchestrator import config
from orchestrator.github.client import GitHubClient


def _handle_discussion(
    gh: GitHubClient, spec: config.RepoSpec, issue: Issue,
) -> None:
    """Leave the issue exactly as the operator labeled it.

    The dispatcher already logs the issue and its label before calling here, so
    the tick is accounted for without this owner writing anything of its own.
    """
