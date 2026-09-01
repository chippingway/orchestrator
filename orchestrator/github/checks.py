# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Status/check-run normalization, folding, and the check-read client mixin."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Iterable

from github import GithubException
from github.PullRequest import PullRequest

from orchestrator.github.pull_requests import GitHubPullRequestMixin

log = logging.getLogger("orchestrator.github")

CHECK_STATE_FAILURE = "failure"
CHECK_STATE_PENDING = "pending"
FAILED_CHECK_RUN_CONCLUSIONS = frozenset(
    (CHECK_STATE_FAILURE, "timed_out", "action_required", "cancelled"),
)
SUCCESSFUL_CHECK_RUN_CONCLUSIONS = frozenset(
    ("success", "neutral", "skipped"),
)
_HTTP_FORBIDDEN = 403


@dataclass(frozen=True)
class CheckSurfaceRead:
    """Normalized state and read outcome for one checks surface."""

    state: str | None = None
    read_failed: bool = False


def normalize_combined_status(combined_status: Any) -> str | None:
    """Convert a legacy combined status into the shared state model."""
    status = combined_status.state
    if not status or (
        status == CHECK_STATE_PENDING
        and not combined_status.total_count
    ):
        return None
    return CHECK_STATE_FAILURE if status == "error" else status


def normalize_check_runs(check_runs: Iterable[Any]) -> str | None:
    """Convert check-run conclusions into the shared state model."""
    conclusions = {check_run.conclusion for check_run in check_runs}
    if not conclusions:
        return None
    if None in conclusions:
        return CHECK_STATE_PENDING
    if conclusions & FAILED_CHECK_RUN_CONCLUSIONS:
        return CHECK_STATE_FAILURE
    if conclusions <= SUCCESSFUL_CHECK_RUN_CONCLUSIONS:
        return "success"
    return CHECK_STATE_FAILURE


def fold_check_states(
    states: Iterable[str | None],
    *,
    read_failed: bool,
) -> str:
    """Fold normalized surfaces using failure-before-pending priority."""
    observed_states = [state for state in states if state]
    if observed_states and read_failed:
        observed_states.append(CHECK_STATE_PENDING)
    if not observed_states:
        return "none"
    if CHECK_STATE_FAILURE in observed_states:
        return CHECK_STATE_FAILURE
    if CHECK_STATE_PENDING in observed_states:
        return CHECK_STATE_PENDING
    return "success"


class GitHubChecksMixin(GitHubPullRequestMixin):
    """Read both head-commit check surfaces and fold them into one state.

    The check surface is a verdict on a pull request's head, so this owner
    layers over the pull-request one rather than standing beside it.
    """

    def pr_combined_check_state(self, pr: PullRequest) -> str:
        """Fold legacy status and check-runs into one fail-closed state."""
        head_sha = pr.head.sha
        combined_surface = self._read_combined_status(head_sha)
        check_run_surface = self._read_check_runs(head_sha)
        return fold_check_states(
            (combined_surface.state, check_run_surface.state),
            read_failed=(
                combined_surface.read_failed
                or check_run_surface.read_failed
            ),
        )

    def _read_combined_status(self, head_sha: str) -> CheckSurfaceRead:
        """Read and normalize the legacy commit-status surface."""
        try:
            combined_status = (
                self.repo.get_commit(head_sha).get_combined_status()
            )
        except GithubException as error:
            log.warning(
                "could not read combined status for %s (HTTP %s); ignoring",
                head_sha,
                error.status,
            )
            return CheckSurfaceRead(read_failed=True)
        return CheckSurfaceRead(
            state=normalize_combined_status(combined_status),
        )

    def _read_check_runs(self, head_sha: str) -> CheckSurfaceRead:
        """Read and normalize the check-runs surface."""
        try:
            return CheckSurfaceRead(
                state=normalize_check_runs(
                    self.repo.get_commit(head_sha).get_check_runs(),
                ),
            )
        except GithubException as error:
            if error.status == _HTTP_FORBIDDEN:
                log.error(
                    "could not read check-runs for %s (HTTP 403). The "
                    "orchestrator PAT needs 'Checks: read' to evaluate "
                    "GitHub Actions PRs. Without it, check_state is "
                    "reported as 'none' on Actions-only PRs. Add the "
                    "permission and restart.",
                    head_sha,
                )
            else:
                log.warning(
                    "could not read check-runs for %s (HTTP %s); ignoring",
                    head_sha,
                    error.status,
                )
            return CheckSurfaceRead(read_failed=True)
