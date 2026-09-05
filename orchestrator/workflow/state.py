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

The labels the orchestrator writes itself are namespaced `workflow:<tag>` so a
repository's own vocabulary cannot collide with them; the ones a human also
applies or reads on their own (`in_review`, `question`, `discussion`, `done`,
`rejected`, and the `backlog` / `paused` controls) keep their bare spelling.
`stage_name` strips the namespace back off a workflow label, because the tag --
not the label -- is what analytics rows, audit events, and agent sessions have
always recorded, and `label_for_name` accepts a bare tag as well so an issue
labeled before the namespace still resolves to its member.
"""
from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Any

log = logging.getLogger("orchestrator.state_machine")
_MISSING_LABEL = object()
_LABEL_NAMESPACE = "workflow:"


class WorkflowLabel(StrEnum):
    """Workflow states whose values are the GitHub label strings."""

    DECOMPOSING = "workflow:decomposing"
    READY = "workflow:ready"
    BLOCKED = "workflow:blocked"
    UMBRELLA = "workflow:umbrella"
    IMPLEMENTING = "workflow:implementing"
    VALIDATING = "workflow:validating"
    DOCUMENTING = "workflow:documenting"
    IN_REVIEW = "in_review"
    FIXING = "workflow:fixing"
    RESOLVING_CONFLICT = "workflow:resolving_conflict"
    QUESTION = "question"
    DISCUSSION = "discussion"
    DONE = "done"
    REJECTED = "rejected"


class ControlLabel(StrEnum):
    """Modifiers that coexist with a workflow state.

    These values gate or redirect processing while leaving the underlying
    ``WorkflowLabel`` intact. They never enter the workflow transition table.

    ``BACKLOG`` and ``PAUSED`` are the operator's own controls and keep their
    bare spelling for a human to type; ``COMMUNITY_CONTRIBUTION`` is written by
    the orchestrator's open-PR sweep, so it is namespaced with everything else
    the orchestrator applies.
    """

    BACKLOG = "backlog"
    PAUSED = "paused"
    COMMUNITY_CONTRIBUTION = "workflow:community_contribution"


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

# The states a candidate the remote ALREADY carries can be measured from:
# every one that pushes onto an open pull request -- the reviewer's own fix
# loop, the human one, the body-edit resume an open PR takes, the conflict
# rebase's, and the final documentation pass. The size gate holds an oversized
# one off the pull request and hands the issue to the same adjudication an
# unpublished candidate gets, so each of them owes the edge `implementing`
# already has -- and owes it for the label a human moved by hand too, which
# the relabel guard puts back on `decomposing` from wherever it landed.
_ENTER_ADJUDICATION_PUBLISHED: frozenset[WorkflowLabel] = frozenset(
    (
        WorkflowLabel.VALIDATING,
        WorkflowLabel.DOCUMENTING,
        WorkflowLabel.IN_REVIEW,
        WorkflowLabel.FIXING,
        WorkflowLabel.RESOLVING_CONFLICT,
    ),
)

_FORWARD: Mapping[
    WorkflowLabel | None, frozenset[WorkflowLabel]
] = MappingProxyType({
    None: frozenset((WorkflowLabel.DECOMPOSING, WorkflowLabel.IMPLEMENTING)),
    # The published states are the size gate's way BACK. An adjudication
    # entered on work the remote already carries settles at the stage it was
    # taken out of, because that stage is the only owner of the completion the
    # candidate still owes -- the docs watermark and its `in_review` handoff,
    # a conflict round, another reviewer look. Sending every one of them to
    # `implementing` instead would walk the issue back to a point it had
    # already passed.
    WorkflowLabel.DECOMPOSING: frozenset(
        (
            WorkflowLabel.READY,
            WorkflowLabel.IMPLEMENTING,
            WorkflowLabel.BLOCKED,
            WorkflowLabel.UMBRELLA,
        ),
    ) | _ENTER_ADJUDICATION_PUBLISHED,
    WorkflowLabel.READY: frozenset(
        (WorkflowLabel.IMPLEMENTING, WorkflowLabel.DECOMPOSING),
    ),
    WorkflowLabel.BLOCKED: frozenset(
        (WorkflowLabel.READY, WorkflowLabel.DECOMPOSING),
    ),
    WorkflowLabel.UMBRELLA: frozenset(
        (WorkflowLabel.DONE, WorkflowLabel.DECOMPOSING),
    ),
    # `decomposing` is the late gate's edge: a clean committed candidate
    # measured past the size threshold is adjudicated before anything is
    # pushed, and the adjudication runs under the decomposing label rather
    # than a state of its own.
    WorkflowLabel.IMPLEMENTING: frozenset(
        (WorkflowLabel.VALIDATING, WorkflowLabel.DECOMPOSING),
    ),
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
    # Nothing routes an issue into `discussion`, so the only edges it needs are
    # its two endings: the design was taken, or it was not. A human applies
    # either by hand, and the stage writes the same two itself once they have
    # decided somewhere it can read -- by merging or closing the plan PR, or by
    # closing the issue before one exists.
    WorkflowLabel.DISCUSSION: frozenset(
        (WorkflowLabel.DONE, WorkflowLabel.REJECTED),
    ),
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
    # The last three are the late gate's cancellation: an issue whose owner is
    # observed closed mid-adjudication finishes its external cleanup and stops
    # there, under whichever label the adjudication had reached --
    # `decomposing` before a split, `umbrella` once one converted it, and
    # `done` for an owner a human moved onto the terminal over a cycle that
    # still has an ending to reach. That last one is the only edge out of a
    # terminal the orchestrator takes. The umbrella's own terminal needs none
    # of it: the write that records the resolution retires the cycle with it,
    # so a close arriving past that write finds nothing left to cancel and
    # nothing is ever left under `done` for a later pass to correct.
    WorkflowLabel.REJECTED: frozenset(
        (
            WorkflowLabel.IMPLEMENTING,
            WorkflowLabel.VALIDATING,
            WorkflowLabel.DOCUMENTING,
            WorkflowLabel.IN_REVIEW,
            WorkflowLabel.FIXING,
            WorkflowLabel.RESOLVING_CONFLICT,
            WorkflowLabel.DECOMPOSING,
            WorkflowLabel.UMBRELLA,
            WorkflowLabel.DONE,
        ),
    ),
    WorkflowLabel.RESOLVING_CONFLICT: _DETOUR_TO_RESOLVING,
    WorkflowLabel.DECOMPOSING: _ENTER_ADJUDICATION_PUBLISHED,
})


def stage_name(label: str | WorkflowLabel | None) -> str | None:
    """Return the bare tag a workflow label names its state by.

    Analytics rows, audit event payloads, and the stage an agent session is
    attributed to are their own compatibility contract, independent of how the
    label is spelled on GitHub, so each of those sinks is handed the tag rather
    than the label carrying it.
    """
    if label is None:
        return None
    return str(label).removeprefix(_LABEL_NAMESPACE)


def legacy_label_name(
    label: str | WorkflowLabel | ControlLabel,
) -> str | None:
    """Return the pre-namespace spelling of a label, or None if it has none.

    Every namespaced label has one, control labels included: the namespace is
    exactly what the migration adds, so what it strips is what the repository
    carried before. A label already spelled bare is not one this ever renamed.
    """
    label_name = str(label)
    if not label_name.startswith(_LABEL_NAMESPACE):
        return None
    return label_name.removeprefix(_LABEL_NAMESPACE)


def _canonical_label_names() -> Mapping[str, WorkflowLabel]:
    """Map each label the orchestrator writes to its member."""
    return MappingProxyType({str(member): member for member in WorkflowLabel})


def _legacy_label_names() -> Mapping[str, WorkflowLabel]:
    """Map each pre-namespace spelling to the member that replaced it."""
    return MappingProxyType({
        legacy_name: member
        for member in WorkflowLabel
        for legacy_name in (legacy_label_name(member),)
        if legacy_name is not None
    })


CANONICAL_LABELS = _canonical_label_names()
LEGACY_LABELS = _legacy_label_names()


def label_for_name(label_name: str | WorkflowLabel) -> WorkflowLabel | None:
    """Return the workflow member a GitHub label denotes, or None if it is not one.

    Both spellings resolve, so an issue still carrying the pre-namespace label
    keeps routing. Which of the two an issue is actually IN, when it carries
    one of each, is `issue_workflow_label`'s question -- not this one's.
    """
    wanted_name = str(label_name)
    return CANONICAL_LABELS.get(wanted_name) or LEGACY_LABELS.get(wanted_name)


def issue_workflow_label(
    label_names: Iterable[str],
) -> WorkflowLabel | None:
    """Return the workflow state one issue's labels put it in.

    A namespaced label outranks a pre-namespace one no matter which order
    GitHub lists them in. The orchestrator only ever writes the namespaced
    spelling and strips the rest as it goes, so a bare tag sitting beside one
    is never the current state: it is a leftover the migration has not reached,
    or a name the repository uses for something of its own. Reading it as the
    state would route the issue to the wrong handler.
    """
    names = list(label_names)
    for lookup in (CANONICAL_LABELS, LEGACY_LABELS):
        for name in names:
            resolved_label = lookup.get(name)
            if resolved_label is not None:
                return resolved_label
    return None


def replaced_label_names(label_names: Iterable[str]) -> frozenset[str]:
    """Return the labels a workflow-label write on this issue replaces.

    Always the namespaced ones -- those are the orchestrator's own. A bare tag
    joins them when it names a state being replaced anyway: either because the
    namespaced spelling of that same state is on the issue beside it (one
    state, two spellings, and the migration exists to end that), or because
    the issue carries no namespaced label at all and the bare one is therefore
    its pre-migration state.

    What survives is a bare tag naming some OTHER state than the one being
    replaced, on an issue that already has its state namespaced. Nothing the
    orchestrator wrote could have left that behind, so it belongs to the
    repository and is not this write's to delete.
    """
    names = list(label_names)
    canonical = {name for name in names if name in CANONICAL_LABELS}
    if not canonical:
        return frozenset(name for name in names if name in LEGACY_LABELS)
    replaced_states = {CANONICAL_LABELS[name] for name in canonical}
    return frozenset(canonical | {
        name for name in names
        if LEGACY_LABELS.get(name) in replaced_states
    })


def coerce_label_name(label_name: str | WorkflowLabel) -> WorkflowLabel:
    """Return the workflow member for a wire label or raise ``ValueError``."""
    resolved_label = label_for_name(label_name)
    if resolved_label is None:
        valid_labels = ", ".join(
            repr(str(member)) for member in WorkflowLabel
        )
        raise ValueError(
            f"{label_name!r} is not a valid workflow label; "
            f"expected one of: {valid_labels}",
        )
    return resolved_label


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
) -> dict[WorkflowLabel | None, set[WorkflowLabel]]:
    """Copy the forward graph into mutable target sets."""
    return {
        forward_source: set(forward_targets)
        for forward_source, forward_targets in _FORWARD.items()
    }


def _add_interrupt_transitions(
    allowed: dict[WorkflowLabel | None, set[WorkflowLabel]],
) -> None:
    """Fold each target's exact interrupt sources into the graph."""
    for target, sources in _INTERRUPT_SOURCES.items():
        for interrupt_source in sources:
            allowed[interrupt_source].add(target)


def _freeze_transitions(
    allowed: dict[WorkflowLabel | None, set[WorkflowLabel]],
) -> dict[WorkflowLabel | None, frozenset[WorkflowLabel]]:
    """Freeze target sets so the exported graph is immutable."""
    return {
        allowed_source: frozenset(edges)
        for allowed_source, edges in allowed.items()
    }


def build_allowed_transitions(
) -> dict[WorkflowLabel | None, frozenset[WorkflowLabel]]:
    """Compose the forward spine with exact interrupt sources."""
    allowed = _mutable_forward_transitions()
    _add_interrupt_transitions(allowed)
    return _freeze_transitions(allowed)


ALLOWED_TRANSITIONS = build_allowed_transitions()


def is_allowed_transition(
    current: WorkflowLabel | None,
    new: WorkflowLabel,
) -> bool:
    """Return whether relabeling ``current`` to ``new`` is legal."""
    if current == new:
        return True
    return new in ALLOWED_TRANSITIONS.get(current, frozenset())


def publishes_onto_a_pull_request(label: WorkflowLabel | None) -> bool:
    """Whether this stage pushes onto a pull request the remote already has.

    The five the size gate can take an issue out of, named off the same set
    the edges to the adjudication are built from so the two cannot drift.
    Derived instead -- from "has an edge to `workflow:decomposing`" -- it
    would admit `workflow:implementing`, whose own gate routes there too and
    whose approval carries no pull-request head because its push is the one
    that opens the pull request.
    """
    return label in _ENTER_ADJUDICATION_PUBLISHED


def rebased_by_the_base_refresh(label: WorkflowLabel | None) -> bool:
    """Whether the per-tick base refresh drives this stage's own rebase.

    The four states that detour to `workflow:resolving_conflict` when that
    rebase leaves conflicted files, named off the same set those edges are
    built from so the two cannot drift. It is the five above minus
    `workflow:resolving_conflict` itself, which owns its rebase rather than
    being driven through one -- and telling them apart is what says which
    rewrite kind a record naming a rebase may have come from.
    """
    return label in _DETOUR_TO_RESOLVING


def guard_transition(
    current: WorkflowLabel | None,
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
