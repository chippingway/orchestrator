# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Typed workflow state: the label vocabulary, its graph, and the write guard.

This owner defines them and every in-tree caller names it; the package
initializer beside it re-exports the two vocabularies, the guard and its
predicate, and `IllegalTransition` for callers outside the tree, handing back
these exact objects rather than rebuilding any of them.

Two of the values here are a public contract that the module path must not be
able to rename. The label members are the GitHub label strings live issues
already carry, and the logger name is what operator log filters select on, so
both are spelled out literally rather than derived from where this owner sits.
"""
from __future__ import annotations

import logging
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping, Optional

log = logging.getLogger("orchestrator.state_machine")
_MISSING_LABEL = object()


class WorkflowLabel(StrEnum):
    """Workflow states whose values are the GitHub label strings."""

    DECOMPOSING = "decomposing"
    READY = "ready"
    BLOCKED = "blocked"
    UMBRELLA = "umbrella"
    IMPLEMENTING = "implementing"
    VALIDATING = "validating"
    DOCUMENTING = "documenting"
    IN_REVIEW = "in_review"
    FIXING = "fixing"
    RESOLVING_CONFLICT = "resolving_conflict"
    QUESTION = "question"
    DONE = "done"
    REJECTED = "rejected"


class ControlLabel(StrEnum):
    """Operator modifiers that coexist with a workflow state.

    These values gate or redirect processing while leaving the underlying
    ``WorkflowLabel`` intact. They never enter the workflow transition table.
    """

    BACKLOG = "backlog"
    PAUSED = "paused"
    COMMUNITY_CONTRIBUTION = "community_contribution"


class IllegalTransition(Exception):
    """A workflow-label write is absent from ``ALLOWED_TRANSITIONS``."""


_DETOUR_TO_RESOLVING: frozenset[WorkflowLabel] = frozenset(
    (
        WorkflowLabel.VALIDATING,
        WorkflowLabel.DOCUMENTING,
        WorkflowLabel.IN_REVIEW,
        WorkflowLabel.FIXING,
    ),
)

_FORWARD: Mapping[
    Optional[WorkflowLabel], frozenset[WorkflowLabel]
] = MappingProxyType({
    None: frozenset((WorkflowLabel.DECOMPOSING, WorkflowLabel.IMPLEMENTING)),
    WorkflowLabel.DECOMPOSING: frozenset(
        (
            WorkflowLabel.READY,
            WorkflowLabel.IMPLEMENTING,
            WorkflowLabel.BLOCKED,
            WorkflowLabel.UMBRELLA,
        ),
    ),
    WorkflowLabel.READY: frozenset(
        (WorkflowLabel.IMPLEMENTING, WorkflowLabel.DECOMPOSING),
    ),
    WorkflowLabel.BLOCKED: frozenset(
        (WorkflowLabel.READY, WorkflowLabel.DECOMPOSING),
    ),
    WorkflowLabel.UMBRELLA: frozenset(
        (WorkflowLabel.DONE, WorkflowLabel.DECOMPOSING),
    ),
    WorkflowLabel.IMPLEMENTING: frozenset((WorkflowLabel.VALIDATING,)),
    WorkflowLabel.VALIDATING: frozenset(
        (WorkflowLabel.DOCUMENTING, WorkflowLabel.FIXING),
    ),
    WorkflowLabel.DOCUMENTING: frozenset(
        (WorkflowLabel.IN_REVIEW, WorkflowLabel.VALIDATING),
    ),
    WorkflowLabel.IN_REVIEW: frozenset(
        (WorkflowLabel.FIXING, WorkflowLabel.VALIDATING),
    ),
    WorkflowLabel.FIXING: frozenset(
        (
            WorkflowLabel.VALIDATING,
            WorkflowLabel.RESOLVING_CONFLICT,
            WorkflowLabel.IN_REVIEW,
        ),
    ),
    WorkflowLabel.RESOLVING_CONFLICT: frozenset((WorkflowLabel.VALIDATING,)),
    WorkflowLabel.QUESTION: frozenset((WorkflowLabel.DONE,)),
    WorkflowLabel.DONE: frozenset(),
    WorkflowLabel.REJECTED: frozenset(),
})

_INTERRUPT_SOURCES: Mapping[
    WorkflowLabel, frozenset[WorkflowLabel]
] = MappingProxyType({
    WorkflowLabel.DONE: frozenset(
        (
            WorkflowLabel.IMPLEMENTING,
            WorkflowLabel.VALIDATING,
            WorkflowLabel.DOCUMENTING,
            WorkflowLabel.IN_REVIEW,
            WorkflowLabel.FIXING,
            WorkflowLabel.RESOLVING_CONFLICT,
        ),
    ),
    WorkflowLabel.REJECTED: frozenset(
        (
            WorkflowLabel.IMPLEMENTING,
            WorkflowLabel.VALIDATING,
            WorkflowLabel.DOCUMENTING,
            WorkflowLabel.IN_REVIEW,
            WorkflowLabel.FIXING,
            WorkflowLabel.RESOLVING_CONFLICT,
        ),
    ),
    WorkflowLabel.RESOLVING_CONFLICT: _DETOUR_TO_RESOLVING,
})


def coerce_label_name(label_name: str | WorkflowLabel) -> WorkflowLabel:
    """Return the workflow member for a wire label or raise ``ValueError``."""
    try:
        return WorkflowLabel(label_name)
    except ValueError:
        valid_labels = ", ".join(
            repr(str(member)) for member in WorkflowLabel
        )
        raise ValueError(
            f"{label_name!r} is not a valid workflow label; "
            f"expected one of: {valid_labels}",
        ) from None


def coerce_workflow_label(
    label_name: str | WorkflowLabel | object = _MISSING_LABEL,
    **legacy_fields: Any,
) -> WorkflowLabel:
    """Coerce a workflow label while accepting the historical ``value=``.

    ``label_name`` is the descriptive keyword for new callers. The adapter
    keeps existing keyword calls working and rejects duplicate or unknown
    arguments with ``TypeError`` before delegating to the typed label parser.
    """
    legacy_label = legacy_fields.pop("value", _MISSING_LABEL)
    if legacy_fields:
        unexpected_name = next(iter(legacy_fields))
        raise TypeError(
            "coerce_workflow_label() got an unexpected keyword argument "
            f"{unexpected_name!r}",
        )
    if label_name is not _MISSING_LABEL and legacy_label is not _MISSING_LABEL:
        raise TypeError(
            "coerce_workflow_label() got multiple values for the label",
        )
    selected_label = legacy_label if label_name is _MISSING_LABEL else label_name
    if selected_label is _MISSING_LABEL:
        raise TypeError(
            "coerce_workflow_label() missing required argument: 'label_name'",
        )
    return coerce_label_name(selected_label)


def _mutable_forward_transitions(
) -> dict[Optional[WorkflowLabel], set[WorkflowLabel]]:
    """Copy the forward graph into mutable target sets."""
    return {
        forward_source: set(forward_targets)
        for forward_source, forward_targets in _FORWARD.items()
    }


def _add_interrupt_transitions(
    allowed: dict[Optional[WorkflowLabel], set[WorkflowLabel]],
) -> None:
    """Fold each target's exact interrupt sources into the graph."""
    for target, sources in _INTERRUPT_SOURCES.items():
        for interrupt_source in sources:
            allowed[interrupt_source].add(target)


def _freeze_transitions(
    allowed: dict[Optional[WorkflowLabel], set[WorkflowLabel]],
) -> dict[Optional[WorkflowLabel], frozenset[WorkflowLabel]]:
    """Freeze target sets so the exported graph is immutable."""
    return {
        allowed_source: frozenset(edges)
        for allowed_source, edges in allowed.items()
    }


def build_allowed_transitions(
) -> dict[Optional[WorkflowLabel], frozenset[WorkflowLabel]]:
    """Compose the forward spine with exact interrupt sources."""
    allowed = _mutable_forward_transitions()
    _add_interrupt_transitions(allowed)
    return _freeze_transitions(allowed)


ALLOWED_TRANSITIONS = build_allowed_transitions()


def is_allowed_transition(
    current: Optional[WorkflowLabel],
    new: WorkflowLabel,
) -> bool:
    """Return whether relabeling ``current`` to ``new`` is legal."""
    if current == new:
        return True
    return new in ALLOWED_TRANSITIONS.get(current, frozenset())


def guard_transition(
    current: Optional[WorkflowLabel],
    new: WorkflowLabel,
    mode: str,
) -> None:
    """Warn or raise when a workflow-label write is illegal."""
    if mode == "off" or is_allowed_transition(current, new):
        return
    allowed = ", ".join(
        sorted(
            str(state)
            for state in ALLOWED_TRANSITIONS.get(current, frozenset())
        ),
    )
    current_label = None if current is None else str(current)
    allowed_text = allowed or "(none -- terminal state)"
    detail = (
        "illegal workflow transition "
        f"{current_label!r} -> {str(new)!r}; "
        f"allowed from there: {allowed_text}"
    )
    if mode == "enforce":
        raise IllegalTransition(detail)
    log.warning("%s", detail)
