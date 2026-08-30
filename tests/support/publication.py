# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The push double that moves the pull request it publishes onto.

A lease is a claim about the remote, and the size gate compares the head its
caller leases against with the head the pull request is standing on. One push
in a tick needs no more than a static seed for that, but a tick that pushes
TWICE -- a crash-recovered head and then the rebase behind it -- does: the
second push is leased against the head the first one left, so a pull request
frozen at its pre-tick value would make a tick behaving exactly as it should
look like one whose publication moved under it.

So the double here is the remote's own bookkeeping rather than a mock's return
value: what lands becomes what the pull request is standing on, named by the
commit the push was named against.
"""
from __future__ import annotations

from typing import Optional


class LandingPush:
    """A `_push_branch` that lands and advances its pull request's head."""

    def __init__(self, github, pr_number: int, *, lands: bool = True) -> None:
        self._github = github
        self._pr_number = pr_number
        self._lands = lands

    def __call__(
        self,
        _spec,
        _worktree,
        _branch,
        *,
        revision: Optional[str] = None,
        force_with_lease: Optional[str] = None,
    ) -> bool:
        """Publish the named commit, leaving the pull request standing on it.

        An unnamed push is one the size gate never froze anything for, so
        there is no commit for the remote to be moved to and the seeded head
        stands.
        """
        if not self._lands:
            return False
        if revision:
            self._github.get_pr(self._pr_number).head.sha = revision
        return True
