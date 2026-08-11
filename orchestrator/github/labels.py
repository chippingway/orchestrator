# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""GitHub label vocabulary, bootstrap specifications, and predicates.

The bootstrap is also the migration off the pre-namespace vocabulary: a
repository that still carries the bare label is renamed rather than given a
second one, so every issue holding it -- including the closed ones no sweep
would surface again -- moves across in one edit. That covers the automatic
control label alongside the workflow states, because the rename is driven by
the spelling rather than by which table a spec came from; `backlog` and
`paused` are the operator's to type and were never namespaced, so neither has
a rename to make. `workflow_label` reads the bare spelling too, which is what
keeps an issue routing on a repository the rename could not reach.
"""
from __future__ import annotations

import logging
from typing import Optional

from github import GithubException
from github.Issue import Issue
from github.Label import Label

from orchestrator.github.aliases import StaticMethodAlias
from orchestrator.workflow.state import (
    ControlLabel,
    WorkflowLabel,
    issue_workflow_label,
    legacy_label_name,
)

log = logging.getLogger("orchestrator.github")

WORKFLOW_LABEL_SPECS: tuple[tuple[WorkflowLabel, str, str], ...] = (
    (WorkflowLabel.DECOMPOSING, "fbca04", "Orchestrator is breaking this issue into sub-issues"),
    (WorkflowLabel.READY, "0e8a16", "Decomposed and ready for implementation"),
    (WorkflowLabel.BLOCKED, "b60205", "Blocked on another issue"),
    (WorkflowLabel.UMBRELLA, "ededed", "Parent of child issues with no implementation of its own"),
    (WorkflowLabel.IMPLEMENTING, "1d76db", "A coding agent is working on this"),
    (WorkflowLabel.VALIDATING, "8a2be2", "Reviewer agent is checking the diff; verify gate runs on approval"),
    (
        WorkflowLabel.DOCUMENTING,
        "c2e0c6",
        "Documentation pass after reviewer approval (final-docs hop), before in_review",
    ),
    (WorkflowLabel.IN_REVIEW, "d93f0b", "PR is open, awaiting human review"),
    (
        WorkflowLabel.FIXING,
        "fef2c0",
        "Dev fix-loop addressing reviewer changes or in_review PR feedback before re-validation",
    ),
    (
        WorkflowLabel.RESOLVING_CONFLICT,
        "e99695",
        "Resolving an actual rebase conflict (clean rebases route straight to validating)",
    ),
    (WorkflowLabel.QUESTION, "d876e3", "Awaiting a clarifying answer from a human before the orchestrator can advance"),
    (WorkflowLabel.DONE, "cccccc", "Merged to main"),
    (WorkflowLabel.REJECTED, "5c0000", "Issue rejected / closed without merge"),
)
assert {spec[0] for spec in WORKFLOW_LABEL_SPECS} == set(WorkflowLabel)
WORKFLOW_LABELS = frozenset(WorkflowLabel)

BACKLOG_LABEL = ControlLabel.BACKLOG
PAUSED_LABEL = ControlLabel.PAUSED
COMMUNITY_CONTRIBUTION_LABEL = ControlLabel.COMMUNITY_CONTRIBUTION
# Every spelling the sweep's own label can be found under. The label is the
# sweep's dedup marker, so a PR still carrying the bare one -- on a repository
# the bootstrap rename could not reach -- has to read as already marked, or the
# HITL ping fires a second time on a PR a human was already asked to review.
COMMUNITY_CONTRIBUTION_LABEL_NAMES: tuple[str, ...] = tuple(
    label_name
    for label_name in (
        COMMUNITY_CONTRIBUTION_LABEL,
        legacy_label_name(COMMUNITY_CONTRIBUTION_LABEL),
    )
    if label_name is not None
)
CONTROL_LABEL_SPECS: tuple[tuple[ControlLabel, str, str], ...] = (
    (
        BACKLOG_LABEL,
        "c5def5",
        "Skip orchestrator processing entirely until the label is removed",
    ),
    (
        PAUSED_LABEL,
        "d4c5f9",
        "Pause an in-flight issue: skip orchestrator processing entirely until the label is removed",
    ),
    (
        COMMUNITY_CONTRIBUTION_LABEL,
        "7057ff",
        "PR opened by an author outside ALLOWED_ISSUE_AUTHORS; human review requested",
    ),
)
HARD_SKIP_CONTROL_LABELS: tuple[ControlLabel, ...] = (
    BACKLOG_LABEL,
    PAUSED_LABEL,
)


def issue_has_label(issue: Issue, label_name: str) -> bool:
    """Return whether an issue has a case-insensitive label name."""
    wanted_label = (label_name or "").lower()
    return any(
        ((getattr(label, "name", "") or "").lower() == wanted_label)
        for label in (issue.labels or [])
    )


def hard_skip_control_label(issue: Issue) -> Optional[str]:
    """Return the first control label that suppresses issue processing."""
    for control_label in HARD_SKIP_CONTROL_LABELS:
        if issue_has_label(issue, control_label):
            return control_label
    return None


def workflow_label(issue: Issue) -> Optional[WorkflowLabel]:
    """Return an issue's workflow label, excluding control labels.

    The namespaced spelling wins over a pre-namespace one on the same issue,
    whichever order GitHub lists them in -- see `issue_workflow_label`.
    """
    return issue_workflow_label(
        issue_label.name for issue_label in issue.labels
    )


WORKFLOW_LABEL_METHOD = StaticMethodAlias(workflow_label)


class GitHubLabelMixin:
    """Repository-side bootstrap of the workflow and control vocabulary."""

    def ensure_workflow_labels(self) -> None:
        """Best-effort provisioning of missing workflow and control labels."""
        existing_labels = self._existing_labels()
        if existing_labels is None:
            return
        label_specs = WORKFLOW_LABEL_SPECS + CONTROL_LABEL_SPECS
        for name, color, description in label_specs:
            if name in existing_labels:
                continue
            if not self._provision_label(
                existing_labels, name, color, description,
            ):
                return

    def _existing_labels(self) -> Optional[dict[str, Label]]:
        """Return the repository's labels by name, or None if unreadable."""
        try:
            return {
                repo_label.name: repo_label
                for repo_label in self.repo.get_labels()
            }
        except GithubException as error:
            log.warning(
                "could not list labels (HTTP %s); skipping label bootstrap. "
                "Grant the PAT 'Issues: Read and write' to enable.",
                error.status,
            )
            return None

    def _provision_label(
        self,
        existing_labels: dict[str, Label],
        name: str,
        color: str,
        description: str,
    ) -> bool:
        """Rename the pre-namespace label into place, or create a fresh one.

        Renaming carries every issue already holding the old label across in
        one edit, which is the only migration path for an issue no polling
        pass revisits -- a closed one mid-sweep, or one parked under
        `backlog`. Returns False once a refusal has been logged, so the caller
        stops rather than retrying the same denied permission per spec.
        """
        legacy_name = legacy_label_name(name)
        legacy_label = (
            None if legacy_name is None else existing_labels.get(legacy_name)
        )
        try:
            if legacy_label is None:
                self.repo.create_label(
                    name=name, color=color, description=description,
                )
            else:
                legacy_label.edit(
                    name=name, color=color, description=description,
                )
        except GithubException as error:
            log.error(
                "could not provision label %r (HTTP %s). "
                "Fine-grained PAT needs 'Issues: Read and write'. "
                "Skipping remaining label bootstrap; orchestrator will "
                "keep running and may retry on the next restart.",
                name,
                error.status,
            )
            return False
        if legacy_label is None:
            log.info("created label %r", name)
        else:
            log.info("renamed label %r to %r", legacy_name, name)
        return True
