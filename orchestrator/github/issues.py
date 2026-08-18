# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Issue polling and filtering, label writes, comments, and child creation.

The issue-state vocabulary lives here too -- the attribute PyGithub carries it
on and the two values it takes -- because it is the GitHub wire spelling, not a
workflow one: every reader that asks whether an issue is still open, and every
writer that closes one, has to spell it the way the API does.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Optional

from github.Issue import Issue
from github.IssueComment import IssueComment
from github.Label import Label

from orchestrator import config
from orchestrator.github import events, labels
from orchestrator.workflow.state import (
    WorkflowLabel,
    coerce_workflow_label,
    guard_transition,
    legacy_label_name,
    replaced_label_names,
    stage_name,
)

_STATE_ATTR = "state"
_ISSUE_STATE_OPEN = "open"
_ISSUE_STATE_CLOSED = "closed"
_RECORDED_EVENTS_CAP = 500

# The stages whose closed issues still have a terminal arc left to drain: an
# externally merged PR, a human closing the issue out from under a running
# agent, or -- on the two operator-applied conversation labels -- the close
# itself being the whole signal. The in-memory double sweeps this same set.
#
# What is absent is the decomposition family (`decomposing` / `ready` /
# `blocked` / `umbrella`): a closed issue there is a hard human stop with
# nothing to finalize, and it stays out until an operator relabels it.
#
# A label leaves this set by being written off the issue, which every terminal
# arc does as it fires -- so in steady state the sweep costs one pass per
# closed issue. `discussion` is the one exception, and it is deliberate: a
# discussion whose plan PR is still open holds its terminal rather than taking
# one, KEEPING the label, so the sweep goes on yielding that issue every pass
# until the humans decide the pull request. Nothing else revisits a closed
# issue, and the branch and worktree the plan lives on have nothing else that
# would reap them.
CLOSED_SWEEP_LABELS: tuple[WorkflowLabel, ...] = (
    WorkflowLabel.IMPLEMENTING,
    WorkflowLabel.DOCUMENTING,
    WorkflowLabel.VALIDATING,
    WorkflowLabel.IN_REVIEW,
    WorkflowLabel.FIXING,
    WorkflowLabel.RESOLVING_CONFLICT,
    WorkflowLabel.QUESTION,
    WorkflowLabel.DISCUSSION,
)


def _closed_sweep_lookups() -> tuple[tuple[str, bool], ...]:
    """Pair every swept label spelling with whether a miss on it is expected.

    The pre-namespace spelling is queried beside the namespaced one because a
    closed issue is the one case no other pass revisits: if the bootstrap could
    not rename the label, nothing else would ever surface that issue again.
    Both queries feed one ``seen_numbers`` set, so an issue a repository
    carries under both spellings is still yielded once.

    A miss on a legacy name is the expected answer on a migrated repository,
    so it is throttled rather than re-asked every sweep -- throttled, not
    remembered, because the label can still come back by hand.
    """
    lookups: list[tuple[str, bool]] = []
    for sweep_label in CLOSED_SWEEP_LABELS:
        lookups.append((str(sweep_label), False))
        legacy_name = legacy_label_name(sweep_label)
        if legacy_name is not None:
            lookups.append((legacy_name, True))
    return tuple(lookups)


CLOSED_SWEEP_LOOKUPS = _closed_sweep_lookups()


def iter_new_non_pr_issues(
    issues: Iterable[Issue],
    seen_numbers: set[int],
) -> Iterable[Issue]:
    """Yield unseen non-PR issues while updating the shared number set."""
    for issue in issues:
        if issue.pull_request is None and issue.number not in seen_numbers:
            seen_numbers.add(issue.number)
            yield issue


def issue_query_options(
    *,
    issue_state: str,
    since: Optional[datetime],
    label: Optional[Label] = None,
) -> dict[str, Any]:
    """Build common open/closed issue query options."""
    query_options: dict[str, Any] = {
        "state": issue_state,
        "sort": "updated",
        "direction": "desc",
    }
    if label is not None:
        query_options["labels"] = [label]
    if since is not None:
        query_options["since"] = since
    return query_options


def set_workflow_label(
    client: Any,
    issue: Issue,
    new_label: Optional[str],
) -> None:
    """Replace only the workflow label and emit its stage-enter event."""
    new_workflow_label = (
        coerce_workflow_label(new_label) if new_label else None
    )
    if new_workflow_label is not None:
        guard_transition(
            client.workflow_label(issue),
            new_workflow_label,
            config.WORKFLOW_TRANSITION_GUARD,
        )
    # Only the labels this write actually owns come off. A bare tag beside a
    # namespaced one belongs to the repository, not to the orchestrator, so it
    # survives -- see `replaced_label_names`.
    label_names = [issue_label.name for issue_label in issue.labels]
    replaced = replaced_label_names(label_names)
    kept_labels = [name for name in label_names if name not in replaced]
    if new_workflow_label is not None:
        kept_labels.append(new_workflow_label)
    issue.set_labels(*kept_labels)
    if new_workflow_label is not None:
        # The event and the analytics row name the state by its bare tag: the
        # namespace is a GitHub label spelling, and every reader downstream of
        # here keys on the tag under it.
        client._emit_stage_enter(issue, stage_name(new_workflow_label))


class GitHubIssueMixin:
    """Issue-facing methods shared by the concrete GitHub client."""

    workflow_label = labels.WORKFLOW_LABEL_METHOD
    set_workflow_label = set_workflow_label

    def list_pollable_issues(
        self,
        since: Optional[datetime] = None,
    ) -> Iterable[Issue]:
        """Yield open issues plus recoverable closed workflow issues."""
        seen_numbers: set[int] = set()
        self._pollable_calls += 1
        yield from iter_new_non_pr_issues(
            self.repo.get_issues(
                **issue_query_options(
                    issue_state=_ISSUE_STATE_OPEN,
                    since=since,
                ),
            ),
            seen_numbers,
        )
        sweep_cadence = config.CLOSED_ISSUE_SWEEP_EVERY_N_TICKS
        if (
            sweep_cadence > 1
            and (self._pollable_calls - 1) % sweep_cadence != 0
        ):
            return
        # Counted past the cadence gate, not beside `_pollable_calls`: the
        # absent-label window is denominated in sweeps, and under `N>1` most
        # polls never reach this loop at all.
        self._closed_sweeps += 1
        for label_name, absence_is_expected in CLOSED_SWEEP_LOOKUPS:
            label_object = self._cached_label(
                label_name, throttle_absent=absence_is_expected,
            )
            if label_object is None:
                continue
            yield from iter_new_non_pr_issues(
                self.repo.get_issues(
                    **issue_query_options(
                        issue_state="closed",
                        since=since,
                        label=label_object,
                    ),
                ),
                seen_numbers,
            )

    def emit_event(
        self,
        event: str,
        *,
        issue_number: int,
        stage: Optional[str] = None,
        **extras: Any,
    ) -> None:
        """Record an event in memory and in the optional audit JSONL sink."""
        event_record = events.build_event_record(
            repo=self._repo_slug,
            issue_number=issue_number,
            event=event,
            stage=stage,
            **extras,
        )
        self.recorded_events.append(event_record)
        if len(self.recorded_events) > _RECORDED_EVENTS_CAP:
            self.recorded_events = self.recorded_events[-_RECORDED_EVENTS_CAP:]
        events.write_event_record(event_record)

    def comment(self, issue: Issue, body: str) -> IssueComment:
        """Post one issue comment."""
        return issue.create_comment(body)

    def get_issue(self, number: int) -> Issue:
        """Return one issue by repository number."""
        return self.repo.get_issue(number)

    def create_child_issue(
        self,
        *,
        title: str,
        body: str,
        parent_number: int,
        labels: list[str],
    ) -> Issue:
        """Create a child with validated workflow labels and a parent link."""
        validated_labels = [
            coerce_workflow_label(label_name)
            for label_name in labels
        ]
        parent_body = (body or "").rstrip()
        full_body = f"{parent_body}\n\nParent: #{parent_number}"
        return self.repo.create_issue(
            title=title,
            body=full_body,
            labels=validated_labels,
        )
