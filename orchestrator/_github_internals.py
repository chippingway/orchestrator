# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Composed client base: per-worker cloning, cached reads, analytics hooks."""
from __future__ import annotations

import logging
from typing import Optional

from github import GithubException
from github.Issue import Issue
from github.Label import Label

from orchestrator import analytics
from orchestrator.github.checks import GitHubChecksMixin
from orchestrator.github.labels import GitHubLabelMixin
from orchestrator.github.reviews import GitHubReviewMixin

log = logging.getLogger("orchestrator.github")


class GitHubInternalsMixin(
    GitHubReviewMixin,
    GitHubLabelMixin,
    GitHubChecksMixin,
):
    """Internal seams used by polling, analytics, and worker isolation.

    The review and label collaborators stand beside the check / pull-request
    chain rather than inside it: neither needs a check or PR method, and keeping
    them independent lets each own its surface without a leaf-to-leaf import.
    """

    def _for_worker_thread(self):
        """Build a fresh requester/repository pair for one worker thread."""
        from orchestrator.github import GitHubClient

        return GitHubClient(
            token=self._token,
            repo_slug=self._repo_slug,
            bot_login=self._bot_login,
        )

    def _cached_label(self, name: str) -> Optional[Label]:
        """Resolve and cache a label, while leaving failures retryable."""
        cached_label = self._label_cache.get(name)
        if cached_label is not None:
            return cached_label
        try:
            label_object = self.repo.get_label(name)
        except GithubException as error:
            log.warning(
                "could not look up %r label for closed-issue sweep "
                "(HTTP %s); skipping. Externally-merged %s issues will "
                "not finalize to `done` until the label exists.",
                name,
                error.status,
                name,
            )
            return None
        self._label_cache[name] = label_object
        return label_object

    def _emit_stage_enter(self, issue: Issue, stage: str) -> None:
        """Record matching audit and analytics stage-enter events."""
        issue_number = getattr(issue, "number", 0) or 0
        self.emit_event(
            "stage_enter",
            issue_number=issue_number,
            stage=stage,
        )
        analytics.record_stage_enter(
            repo=self._repo_slug,
            issue=issue_number,
            stage=stage,
        )
