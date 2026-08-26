# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What one gate call is about, and the identities its records carry.

The tick's own subject and the answer it hands back sit here with the minting
that gives both a name. They are together because they are the same layer:
none of them reads a repository, writes a comment, or decides anything -- they
say what the call is ABOUT, so every owner past this one can be about the
candidate rather than about assembling the description of it.

Whether a recorded identity is one at all is answered here too, and in one
place on purpose. Every refusal in this domain is reported against a
generation, so an identity the sinks would refuse -- or one naming somebody
else's issue -- costs the report rather than merely the record: the failure
goes down with the pinned comment it was about, or is filed where nobody
looking at this issue would find it. The same answer decides whether a
recorded measurement may be acted on, so a record cannot be good enough to
publish on and too damaged to write down.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Optional

from github.Issue import Issue

from orchestrator import config
from orchestrator.github.client import GitHubClient
from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.late_split import (
    formats as _formats,
    identity as _identity,
    lineage as _lineage,
    state as _late_state,
    validation as _late_validation,
)
from orchestrator.workflow.late_split.models import LateGeneration, LatePhase

log = logging.getLogger("orchestrator.workflow")

_UNRECORDABLE_IDENTITY = (
    "the identity it would be correlated by is not one a record may carry "
    "({refusal})"
)

_FOREIGN_RECORD = (
    "it was recorded against issue #{recorded} rather than this one"
)

@dataclass(frozen=True)
class _Gate:
    """The one candidate a gate call is deciding about.

    The worktree travels with the issue because the two are read together at
    every step and neither is derivable from the other here: the commit is
    proved, the base is frozen, and the diff is counted in that checkout,
    while the record, the park, and the label all belong to the issue.
    """

    gh: GitHubClient
    spec: config.RepoSpec
    issue: Issue
    state: PinnedState
    worktree: Path
    # Whether this tick is answering a reading a previous one recorded rather
    # than disposing what a run just produced. No developer ran on a
    # reconciliation, so nothing in the checkout can be that run's output --
    # which is what makes the switch's bypass and the moved-head reading mean
    # different things here than they do on a fresh disposition.
    reconciling: bool = False


@dataclass(frozen=True)
class _GateVerdict:
    """What the gate decided, and the exact commit it decided about.

    The SHA travels because the caller's next step is a PUSH, and a push that
    named nothing would publish whatever the checkout points at when it runs.
    Everything this gate does is a claim about one object id -- it proved that
    commit, measured that commit, and recorded that commit -- so handing back
    a bare "go ahead" would drop the one fact the publication needs to be the
    same event the measurement was about.

    Empty where this gate has nothing to name: a candidate the switch kept
    out of it was never proved here, so there is no commit THIS answer can be
    published under. The publication resolves the checkout's own head there
    rather than pushing an unnamed branch -- the switch keeps candidates out
    of the measurement, not out of the record of what went out.
    """

    held: bool
    candidate_sha: str = ""


# What every held answer is, since a hold names no commit: there is nothing
# for the caller to publish and nothing for it to publish it under.
_HELD = _GateVerdict(held=True)


def _gate(
    gh: GitHubClient,
    spec: config.RepoSpec,
    issue: Issue,
    state: PinnedState,
    worktree: Path,
) -> _Gate:
    """The subject one gate call is about, from what its caller was handed.

    A factory rather than five keywords at each site: every owner in this
    domain opens by building one, and spelling the same five fields out again
    each time is how one of them ends up carrying a different worktree from
    the checkout it is reading.
    """
    return _Gate(
        gh=gh, spec=spec, issue=issue, state=state, worktree=worktree,
    )


def _minted(
    gate: _Gate,
    recorded: LateGeneration,
    candidate_sha: str,
    base_sha: str,
) -> LateGeneration:
    """The generation this freeze records, under identities nothing reused.

    The cycle is this issue's own while one is live, and the number after the
    one a retirement dropped otherwise, so two attempts at the same issue are
    never the same attempt in a record. The generation counter advances with
    every candidate frozen inside a cycle, which is what keeps a verdict
    recorded against an earlier commit from reading as an answer to this one.

    The lineage comes off the ancestry wherever there is one, because that is
    the record a split WROTE about this issue and the one the split
    transaction checks its own generation against. An issue no split created
    is the root of its own lineage at depth 0; one whose ancestry records no
    readable depth stays unknown, which reads as "may not split" rather than
    as a root with room to spare.
    """
    return replace(
        _identified(gate, recorded),
        candidate_sha=candidate_sha,
        base_sha=base_sha,
        threshold=config.MAX_ADDED_LINES,
        additions=None,
    )


def _identified(gate: _Gate, recorded: LateGeneration) -> LateGeneration:
    """The identities and the lineage a record of this attempt is joined by.

    Everything a record needs to be correlatable and nothing about a commit,
    so a failure taken before either end of the diff was established is still
    reportable under the cycle a later freeze writes.
    """
    ancestry = _lineage.read_late_ancestry(gate.state)
    root, depth = _lineage_of(gate, recorded, ancestry)
    return replace(
        recorded,
        cycle_id=recorded.cycle_id or _identity.next_identity(
            _late_state.read_retired_cycle(gate.state),
        ),
        generation=_identity.next_identity(recorded.generation),
        root_issue=root,
        current_issue=gate.issue.number,
        lineage_depth=depth,
        scope=recorded.scope or ancestry.scope,
        phase=LatePhase.MEASURING,
    )


def _lineage_of(
    gate: _Gate, recorded: LateGeneration, ancestry: _lineage.LateAncestry,
) -> tuple:
    """The root and the depth this generation is minted at.

    Both together because both come from the same place and have to agree: the
    ancestry is the record a SPLIT wrote about this issue, and the split
    transaction later checks its own generation against exactly that pair. A
    root taken from one source and a depth from another is the disagreement
    that refusal exists to catch.

    An issue no split created is the root of its own lineage at depth 0. One
    whose ancestry records no readable depth keeps that unknown rather than
    being read as a root, because a lineage that cannot show it has room may
    not split -- and reading a damaged field as 0 is how one buys itself
    another generation past the bound.
    """
    if ancestry.is_present:
        return ancestry.root_issue, ancestry.lineage_depth
    root = recorded.root_issue or gate.issue.number
    return root, (recorded.lineage_depth if recorded.is_present else 0)


def _unusable_identity(gate: _Gate, recorded: LateGeneration) -> Optional[str]:
    """Why this record is no generation of THIS issue, or None if it is.

    Asked through the domain's own record gate rather than by a second reading
    of the same fields, so the identity a record may be ACTED on under is
    exactly the identity a record of it may be WRITTEN under -- a rule spelled
    twice would let the pinned comment publish what the sinks refuse.

    The issue is the one part that gate cannot ask, because it does not know
    which issue is being decided. A positive `late_current_issue` is not the
    same claim as one naming this one: a record carrying somebody else's
    number describes a reading taken over there, and both sinks would file
    this issue's failure against that one.
    """
    try:
        _late_validation.check_generation(recorded)
    except _formats.InvalidLateValue as refused:
        return _UNRECORDABLE_IDENTITY.format(refusal=refused)
    if recorded.current_issue != gate.issue.number:
        return _FOREIGN_RECORD.format(recorded=recorded.current_issue)
    return None


def _named(
    gate: _Gate, recorded: LateGeneration, candidate_sha: str,
) -> LateGeneration:
    """The record an attempt that NAMED a commit is retried under.

    A reading can fail with an id in hand: a revision that resolved and would
    not peel is the commonest, and the id it resolved to is the only record of
    which commit the attempt was about. Minting a generation around it is what
    turns "we could not read something" into "we could not read THIS", which
    is the difference between a retry that asks for one exact object and one
    that proves whatever the checkout points at by then.

    An attempt that named nothing, and one whose id the record already
    carries, are both left as they are: the first has no commit to mint
    around, and the second is already the record the retry will read.
    """
    if not candidate_sha or recorded.candidate_sha == candidate_sha:
        return _reportable(gate, recorded)
    return _minted(gate, recorded, candidate_sha, "")


def _reportable(gate: _Gate, recorded: LateGeneration) -> LateGeneration:
    """The identity a failure is reported under, minted where there is none.

    A candidate the gate could not name is one no generation has been written
    for, and a record with no cycle is exactly what the sinks may not carry --
    so the identity is minted here rather than the failure going unreported.
    A DAMAGED record is the same problem wearing a cycle: the record gate
    refuses it just as flatly, and a record whose `late_current_issue` names
    another issue is worse than refused, since both sinks would accept it and
    file this issue's failure over there. Either way the refusal would be lost
    with the record it is about -- which is precisely the failure an operator
    has to be told about -- so the whole identity is asked, not just the
    cycle.

    Minted identities are deliberately not PERSISTED: a pinned record naming a
    cycle and no candidate freezes nothing, reconciles nothing, and would be
    read as a live cycle by the guard that ends one when the issue is closed.
    Minting is stable across retries -- the cycle is derived from what the
    record already says -- so a reading that keeps failing reports the same
    correlation each time rather than a new attempt per tick.
    """
    if _unusable_identity(gate, recorded) is None:
        return recorded
    return _identified(gate, recorded)
