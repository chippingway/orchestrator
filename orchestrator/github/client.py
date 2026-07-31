# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Authenticated repository client composed from the owner mixins.

``GitHubClient`` is the one concrete client workflow and operator code
construct: it resolves the token, opens the PyGithub connection, and owns the
seams that cut across the domain owners -- the per-worker clone, the label read
cache, and the paired audit / analytics stage-enter hook.
"""
from __future__ import annotations

import logging
from typing import Optional

from github import Auth, Github, GithubException
from github.Issue import Issue
from github.Label import Label
from github.Repository import Repository

from orchestrator import config
from orchestrator.github.checks import GitHubChecksMixin
from orchestrator.github.labels import GitHubLabelMixin
from orchestrator.github.reviews import GitHubReviewMixin
from orchestrator.observability.analytics import recording

log = logging.getLogger("orchestrator.github")


class GitHubClient(
    GitHubReviewMixin,
    GitHubLabelMixin,
    GitHubChecksMixin,
):
    """Authenticated repository client with a worker-safe clone seam.

    The review and label collaborators stand beside the check / pull-request
    chain rather than inside it: neither needs a check or PR method, and keeping
    them independent lets each own its surface without a leaf-to-leaf import.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        repo_slug: Optional[str] = None,
        repo_spec: Optional["config.RepoSpec"] = None,
        *,
        bot_login: Optional[str] = None,
    ) -> None:
        slug = repo_slug or config.REPO if repo_spec is None else repo_spec.slug
        if token is None:
            token = config._resolve_github_token(slug)
        if not token:
            raise RuntimeError(
                "GITHUB_TOKEN is empty. Export it in the orchestrator's "
                "environment or write it to "
                f"~/.config/{slug}/token "
                "(override path with ORCHESTRATOR_TOKEN_FILE). "
                "Do NOT put it in REPO_ROOT/.env -- the implementer agent "
                "can read that file.",
            )
        self._gh = Github(auth=Auth.Token(token))
        self.repo: Repository = self._gh.get_repo(slug)
        self._repo_slug = slug
        self._token = token
        self._bot_login = (
            self._gh.get_user().login
            if bot_login is None
            else bot_login
        )
        self.recorded_events: list[dict] = []
        self._label_cache: dict[str, Label] = {}
        self._pollable_calls = 0

    def _for_worker_thread(self) -> "GitHubClient":
        """Build a fresh requester/repository pair for one worker thread."""
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
        recording.record_stage_enter(
            repo=self._repo_slug,
            issue=issue_number,
            stage=stage,
        )
