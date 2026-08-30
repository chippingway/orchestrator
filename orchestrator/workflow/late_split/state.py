# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The pinned fields a late generation round-trips through.

Every late field is additive: an issue that never entered the late gate
carries none of them, reads back as an absent generation, and is written back
untouched, so no migration reaches a live issue and an older pinned comment
stays exactly as valid as it was. The key spellings are the compatibility
contract live issues would carry, so they are spelled once here and named
nowhere else -- `LATE_STATE_KEYS` is the whole of what one GENERATION owns
inside the pinned comment, and clearing late mode is defined as dropping
exactly it.

A record with no cycle identity is not a generation, so the write clears the
late fields rather than recording a half-record no later tick could correlate
to an audit line or a child's lineage. The two external ledgers are what it
does not clear: an obligation the remote is owed does not stop being owed
because the identity beside it was damaged, and dropping it would leave a
snapshot or a branch with nothing on the issue to reclaim it by. So an
uncorrelatable record still writes what it owes, and nothing else. Past that
gate each field says for itself what "unset" means: an identity or a SHA at
its empty value is dropped, a lineage depth of 0 is a root and is kept, and
every flag is written only while it is set. What survives the round trip is
therefore exactly what a caller put in.

The publication provenance is additive twice over, and this write is what
makes the second half of that true: a generation entered before the work was
published records none of the group, which is the same pinned comment a binary
that never had the group writes. One state, one spelling -- so reading an
absent flag as a pre-publication entry is right about a live issue without a
migration having reached it.

The two external ledgers are the one pair of fields this owner does not
rewrite from the typed record. A ledger the reader could not fully type comes
back verbatim beside the typed view, and the verbatim copy is what is written:
an obligation an older or newer binary recorded is still owed, and a write
that reduced the ledger to the entries this binary understood would delete it
-- leaving a cleanup looking complete and a snapshot looking reclaimable. The
`restart` owner beside this one moves the pending marker; the marker is a
pinned field, but minting and validating an identity is its own contract. The
`exemption` owner beside it holds the one late key that is deliberately NOT in
this group: the commit an accepted candidate publishes under has to survive
the clear that ends the generation which earned it, so it is spelled there and
this list drops it no more than it drops another stage's keys.
"""
from __future__ import annotations

import json
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Optional

from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.late_split import formats as _formats
from orchestrator.workflow.late_split import ledgers as _ledgers
from orchestrator.workflow.late_split import payloads as _payloads
from orchestrator.workflow.late_split import restart as _restart
from orchestrator.workflow.late_split.models import LateGeneration, LatePhase
from orchestrator.workflow.state import WorkflowLabel

_CYCLE_ID = "late_cycle_id"
_GENERATION = "late_generation"
_ROOT_ISSUE = "late_root_issue"
_CURRENT_ISSUE = "late_current_issue"
_LINEAGE_DEPTH = "late_lineage_depth"
_SCOPE = "late_scope"
_CANDIDATE_SHA = "late_candidate_sha"
_BASE_SHA = "late_base_sha"
_THRESHOLD = "late_threshold"
_ADDITIONS = "late_additions"
_PHASE = "late_phase"
_TITLE_BODY_HASH = "late_title_body_hash"
_COMMENT_HASH = "late_comment_hash"
_COMMENT_WATERMARK_ID = "late_comment_watermark_id"
_PLAN_PR_NUMBER = "late_plan_pr_number"
_PLAN_PR_HEAD = "late_plan_pr_head"
_PLAN_PR_BODY = "late_plan_pr_body"
_POST_PUBLICATION = "late_post_publication"
_SOURCE_STAGE = "late_source_stage"
_PUBLISHED_PR_NUMBER = "late_published_pr_number"
_PUBLISHED_SHA = "late_published_sha"
_RESOURCES = "late_resources"
_CONSUMERS = "late_consumers"
_SPLIT_CHILDREN = "late_split_children"
_LINKS_ANNOUNCED = "late_links_announced"
_OWNER_CHECK_PENDING = "late_owner_check_pending"
_CANCELLED = "late_cancelled"
_CANCELLED_AT = "late_cancelled_at"
_CANCELLED_PHASE = "late_cancelled_phase"
_RESTART_PENDING = "late_restart_pending"
_RESTART_TARGET = "late_restart_target"
_RESTART_CYCLE_ID = "late_restart_cycle_id"
_RESTART_PREDECESSOR = "late_restart_predecessor"

_SPENDS = "late_spends"

LATE_STATE_KEYS = (
    _CYCLE_ID,
    _GENERATION,
    _ROOT_ISSUE,
    _CURRENT_ISSUE,
    _LINEAGE_DEPTH,
    _SCOPE,
    _CANDIDATE_SHA,
    _BASE_SHA,
    _THRESHOLD,
    _ADDITIONS,
    _PHASE,
    _TITLE_BODY_HASH,
    _COMMENT_HASH,
    _COMMENT_WATERMARK_ID,
    _PLAN_PR_NUMBER,
    _PLAN_PR_HEAD,
    _PLAN_PR_BODY,
    _POST_PUBLICATION,
    _SOURCE_STAGE,
    _PUBLISHED_PR_NUMBER,
    _PUBLISHED_SHA,
    _RESOURCES,
    _CONSUMERS,
    _SPLIT_CHILDREN,
    _LINKS_ANNOUNCED,
    _OWNER_CHECK_PENDING,
    _CANCELLED,
    _CANCELLED_AT,
    _CANCELLED_PHASE,
    _RESTART_PENDING,
    _RESTART_TARGET,
    _RESTART_CYCLE_ID,
    _RESTART_PREDECESSOR,
    _SPENDS,
)


# The cycle a retirement dropped, kept OUTSIDE `LATE_STATE_KEYS` on purpose.
# Clearing late mode is defined as dropping exactly the generation's own group,
# and this is the one fact about that generation which has to outlive the drop:
# a close observed INSIDE the retirement write leaves a receipt scoped to a
# cycle the record no longer names, and without this there is nothing left to
# adopt it against.
LATE_RETIRED_CYCLE_ID = "late_retired_cycle_id"

# How many members a recorded spend pair has: the field and what it is set to.
_PAIR = 2

# How long an outcome a conflict round settles on may be. Every one this
# workflow writes is a short word; the bound is what keeps a hand-edited record
# from putting a body-sized string on the pinned comment through a retry.
_OUTCOME_LIMIT = 64


def _cleared(spent: Any) -> bool:
    """Whether a bookmark was recorded as CLEARED, which is all it may be."""
    return spent is None


def _counted(spent: Any) -> bool:
    """Whether a counter was recorded as a real, non-negative count."""
    return _formats.whole_number(spent) and spent >= 0


def _named_outcome(spent: Any) -> bool:
    """Whether an outcome was recorded as one bounded, single-line name."""
    return _formats.is_bounded_text(spent, _OUTCOME_LIMIT)


def _settled_commit(spent: Any) -> bool:
    """Whether a settled head was recorded as a commit, or as none at all."""
    return spent == "" or _formats.is_hex_of(spent, _formats.COMMIT_LENGTHS)


# Every pinned field a hold's route bookkeeping may close, with what each one
# may be set TO. Spelled as literals rather than imported from the four stage
# packages that own them: a stage's bookkeeping stays that stage's to describe
# and this owner stays free of the packages that import it.
# `tests/workflow/test_spend_vocabulary.py` proves the two lists agree, so a
# key added to a route without being added here fails there rather than
# silently at a retry.
#
# The table is what turns a restored spend from "whatever the comment says"
# into a bounded claim, and it is per KEY rather than per type because what
# comes back is APPLIED to the pinned comment and then read by owners that
# know what each field is. An arbitrary key is a write into any field the
# workflow has -- a label, a watermark, a park flag. A key with the wrong
# SHAPE is the same damage one step in: `["review_round", "later"]` passes any
# check that only asks whether a comment can carry the value, and fails at the
# `int(...)` the cap is counted with, on a tick nobody is watching.
_SPENDABLE_FIELDS = MappingProxyType({
    "review_round": _counted,
    "pending_fix_at": _cleared,
    "pending_fix_issue_max_id": _cleared,
    "pending_fix_review_max_id": _cleared,
    "pending_fix_review_summary_max_id": _cleared,
    "pending_fix_issue_ids": _cleared,
    "pending_fix_review_ids": _cleared,
    "pending_fix_review_summary_ids": _cleared,
    "pending_fix_reviewer_comment_id": _cleared,
    "conflict_settled_outcome": _named_outcome,
    "conflict_settled_sha": _settled_commit,
    "docs_settled_sha": _settled_commit,
})


# The fields themselves, for the guard that proves every route spends one this
# table knows.
SPENDABLE_FIELDS = frozenset(_SPENDABLE_FIELDS)


def read_retired_cycle(state: PinnedState) -> Optional[int]:
    """The cycle a retirement dropped off this record, if one did.

    Read through the domain's own identity reader, so a hand-edited value
    reads back as no retirement at all rather than as a cycle nothing can be
    correlated with.
    """
    return _payloads.as_identity(state.get(LATE_RETIRED_CYCLE_ID))


def record_retired_cycle(state: PinnedState, cycle_id: int) -> None:
    """Say which cycle the write that clears late mode is dropping.

    Written in the SAME pinned write as the clear, because what it exists for
    is the window between that write and the barrier behind it: a poll
    observing the close in there receipts a cycle the record has stopped
    naming, and a process that dies before the barrier runs leaves the receipt
    with nothing to be adopted against.

    It names ONE such window and outlives no other. The receipt it correlates
    to is a comment, and comments are append-only, so a correlation left
    standing past its window would let a cycle-scoped receipt be adopted
    against a record whose cycle is two generations newer. What ends it is
    `clear_retired_cycle` and the write below, between them.
    """
    state.set(LATE_RETIRED_CYCLE_ID, int(cycle_id))


def clear_retired_cycle(state: PinnedState) -> None:
    """Drop the retirement correlation, leaving every other field alone.

    Asked by the write that records a generation with an IDENTITY, which is
    the one state that says the window a correlation names is over: either
    the adoption itself put the cycle back, or an operator authorized a fresh
    one. Left standing past that, a cycle-scoped receipt could be adopted
    against a record whose cycle is generations newer -- moving a completed
    owner to `rejected` on a close that ended something else entirely.

    Every retirement that DROPS a cycle records one instead, the umbrella's
    terminal included: the barrier that answers a close observed inside such
    a write belongs to the process that made it, so a process that dies first
    leaves the correlation and the receipt as the only pair a later one can
    read the ending back from.
    """
    state.data.pop(LATE_RETIRED_CYCLE_ID, None)


# What one cycle's `rejected` terminal is recorded by, kept OUTSIDE
# `LATE_STATE_KEYS` for the reason the retired cycle is: clearing late mode is
# defined as dropping exactly the generation's own group, and this is a fact
# about the generation that the ENDING writes and a later tick has to read
# back.
#
# Two fields because it is a two-phase record, exactly as an external
# obligation is: the identity says which cycle the terminal is about and goes
# down BEFORE the label write, so a tick that died in between has something
# durable to come back to; the flag says the label was PROVED to be on the
# issue and goes down after. Only the pair authorizes a restart. An attempt is
# not a terminal -- a write GitHub refused leaves an owner that is unlabeled
# for the reason it always was, and treating the intent as proof would start a
# fresh cycle on a gesture nobody made.
#
# The proof is that the label IS on the issue, and it is reached three ways.
# The pass that made the write takes it returning, and has to: a client's
# cached labels survive the write that changes them, so reading the issue back
# would answer with the label it wore a moment ago -- and a closed owner
# leaves the sweep on that write with no second visit to correct it. Any later
# pass takes it by SEEING `rejected` on the issue, which is what backfills a
# cancellation that ended before this record existed. And where the decision
# stands with neither -- a process that died between the label and the flag --
# the remote's own label history is asked, because that window is the one
# thing no local record can answer for and an operator's removal would
# otherwise be spent re-applying a terminal that had already landed.
LATE_TERMINAL_CYCLE_ID = "late_terminal_cycle_id"

LATE_TERMINAL_CONFIRMED = "late_terminal_confirmed"


def terminal_confirmed(state: PinnedState, cycle_id: int) -> bool:
    """Whether THIS cycle's terminal is recorded as proved on the issue.

    Both halves, and the identity first: a flag left by an earlier cycle says
    nothing about this one, and an issue reaches a terminal more than once.
    Read through the domain's own readers, so a hand-edited identity or a
    `"true"` string reads back as no proof -- which refuses a restart rather
    than authorizing one on a field anybody could have typed.

    The absence of it is the whole question a caller asks. Whether the
    decision half is there beside it separates a terminal this binary
    attempted from one an older one wrote, and neither is proof -- so nothing
    reads the decision on its own.
    """
    if _payloads.as_identity(state.get(LATE_TERMINAL_CYCLE_ID)) != cycle_id:
        return False
    return _payloads.as_flag(state.get(LATE_TERMINAL_CONFIRMED))


def record_terminal(
    state: PinnedState, cycle_id: int, *, confirmed: bool,
) -> None:
    """Record which cycle the terminal is about, and whether it is proved.

    The unconfirmed write is the decision, made durable before the label it
    carries out; the confirmed one is the receipt. An unconfirmed record
    DROPS the flag rather than leaving it, because the same field is reused by
    every cycle this issue ends: a confirmation left standing from the cycle
    before would authorize a restart over an attempt that has not landed yet.
    """
    state.set(LATE_TERMINAL_CYCLE_ID, int(cycle_id))
    if confirmed:
        state.set(LATE_TERMINAL_CONFIRMED, True)
    else:
        state.data.pop(LATE_TERMINAL_CONFIRMED, None)


def read_late_generation(state: PinnedState) -> LateGeneration:
    """Return the late generation a pinned comment records.

    An issue with no late fields reads back as the record's defaults, which
    `LateGeneration.is_present` answers False on -- the one reading that keeps
    a legacy issue out of every late decision without a migration.

    Which reader a field is read through is the field's contract, not its
    Python type: an identity has to be positive, a measurement non-negative, a
    frozen commit a whole object id and a fingerprint a whole digest, a flag
    literally `true`, a source stage one of this workflow's own labels, and a
    restart target one of the two labels a restart may apply. Anything else
    reads back absent, so a hand-edited or older value never becomes live
    state -- a threshold of -1 does not make an unmeasured candidate oversized,
    and a `"false"` string does not arm a cancellation or a pending restart.

    The lineage depth is the one field with no safe substitute for an
    unreadable value, so it has none: a damaged or missing depth on a recorded
    cycle reads back as unknown rather than as the root's 0, and a lineage
    already at the bound therefore stays unsplittable while its field is
    damaged. The write leaves it unknown too, so nothing normalizes the gap
    away on the next pass.
    """
    resources, opaque_resources = _ledgers.read_resources(
        state.get(_RESOURCES),
    )
    consumers, opaque_consumers = _ledgers.read_consumers(
        state.get(_CONSUMERS),
    )
    return LateGeneration(
        cycle_id=_payloads.as_identity(state.get(_CYCLE_ID)) or 0,
        generation=_payloads.as_count(state.get(_GENERATION)) or 0,
        root_issue=_payloads.as_identity(state.get(_ROOT_ISSUE)) or 0,
        current_issue=_payloads.as_identity(state.get(_CURRENT_ISSUE)) or 0,
        lineage_depth=_payloads.as_depth(state.get(_LINEAGE_DEPTH)),
        scope=_payloads.as_text(state.get(_SCOPE)) or "",
        candidate_sha=_payloads.as_hex(
            state.get(_CANDIDATE_SHA), _formats.COMMIT_LENGTHS,
        ) or "",
        base_sha=_payloads.as_hex(
            state.get(_BASE_SHA), _formats.COMMIT_LENGTHS,
        ) or "",
        threshold=_payloads.as_count(state.get(_THRESHOLD)),
        additions=_payloads.as_count(state.get(_ADDITIONS)),
        phase=_payloads.as_member(LatePhase, state.get(_PHASE)),
        title_body_hash=_payloads.as_hex(
            state.get(_TITLE_BODY_HASH), _formats.DIGEST_LENGTHS,
        ),
        comment_hash=_payloads.as_hex(
            state.get(_COMMENT_HASH), _formats.DIGEST_LENGTHS,
        ),
        comment_watermark_id=_payloads.as_identity(
            state.get(_COMMENT_WATERMARK_ID),
        ),
        plan_pr_number=_payloads.as_identity(state.get(_PLAN_PR_NUMBER)),
        plan_pr_head=_payloads.as_hex(
            state.get(_PLAN_PR_HEAD), _formats.COMMIT_LENGTHS,
        ) or "",
        plan_pr_body=_payloads.as_text(state.get(_PLAN_PR_BODY)),
        post_publication=_payloads.as_flag(state.get(_POST_PUBLICATION)),
        source_stage=_payloads.as_member(
            WorkflowLabel, state.get(_SOURCE_STAGE),
        ),
        published_pr_number=_payloads.as_identity(
            state.get(_PUBLISHED_PR_NUMBER),
        ),
        published_sha=_payloads.as_hex(
            state.get(_PUBLISHED_SHA), _formats.COMMIT_LENGTHS,
        ) or "",
        resources=resources,
        consumers=consumers,
        split_children=_ledgers.read_register(state.get(_SPLIT_CHILDREN)),
        links_announced=_payloads.as_flag(state.get(_LINKS_ANNOUNCED)),
        opaque_resources=opaque_resources,
        opaque_consumers=opaque_consumers,
        owner_check_pending=_payloads.as_flag(
            state.get(_OWNER_CHECK_PENDING),
        ),
        cancelled=_payloads.as_flag(state.get(_CANCELLED)),
        cancelled_at=_payloads.as_text(state.get(_CANCELLED_AT)),
        cancelled_phase=_payloads.as_member(
            LatePhase, state.get(_CANCELLED_PHASE),
        ),
        restart_pending=_payloads.as_flag(state.get(_RESTART_PENDING)),
        restart_target=_restart.restart_target(state.get(_RESTART_TARGET)),
        restart_cycle_id=_payloads.as_identity(
            state.get(_RESTART_CYCLE_ID),
        ),
        restart_predecessor=_payloads.as_identity(
            state.get(_RESTART_PREDECESSOR),
        ),
    )


def write_late_generation(
    state: PinnedState,
    generation: LateGeneration,
) -> None:
    """Record one late generation, replacing whatever late fields were there.

    Every late key is dropped first, so a field a caller cleared leaves no
    stale value behind for the next tick to reconcile against. Keys outside
    this domain are not read or written: the pinned comment is shared with
    every other stage, and a late write is only ever about its own fields.

    With one exception, and it is the retirement correlation's own rule: a
    generation with an IDENTITY supersedes it. That correlation names the
    cycle a retirement dropped so a close observed inside that write can
    still be adopted, and a record carrying a live cycle is one where that
    window is over -- either the adoption itself put the cycle back, or an
    operator authorized a fresh one. Leaving it would let a later reader
    correlate an append-only receipt to a cycle the record has long moved
    past. A write with no identity leaves it exactly as the caller set it,
    which is what makes recording it and clearing late mode one write.
    """
    clear_late_generation(state)
    if generation.is_present:
        clear_retired_cycle(state)
    for key, written in _written_fields(generation).items():
        state.set(key, written)


def read_late_spends(state: PinnedState) -> tuple:
    """The route bookkeeping a hold on this frozen pair still owes.

    All of it or none of it. What a hold owed is ONE claim -- the round a fix
    spends together with the feedback bookmarks that round consumed -- and the
    caller that restores it cannot tell which half it got. Dropping members
    individually is what turns a damaged record into a half-applied one: the
    round advances, the bookmark it was spent for stays pending, the spend
    record is discarded as paid, and the next in_review re-entry correlates
    the same comments again and reruns a developer over feedback that was
    already answered. So a single member the comment cannot vouch for refuses
    the whole group, and `late_claims` parks on the raw key still being there.

    What a member may be is bounded on both ends. The key has to name a field
    this domain knows a route closes, because what comes back is APPLIED to
    the pinned comment and an arbitrary one is a write into any field the
    workflow has -- a label, a watermark, a park flag -- made by a retry
    nobody is watching. The value has to be one that FIELD may take, since the
    owners behind the write read each one for what it is: a round is counted,
    a settled head is compared against a commit, a bookmark is only ever
    cleared.

    Empty for every generation frozen by a seam with no bookkeeping behind it,
    which is the whole implementing side: there is no reviewer to have spent a
    round and no stage tail to have been interrupted.
    """
    recorded = state.get(_SPENDS)
    if not isinstance(recorded, list) or not recorded:
        return ()
    if not all(_spendable(pair) for pair in recorded):
        return ()
    return tuple(tuple(pair) for pair in recorded)


def _spendable(pair: Any) -> bool:
    """Whether one recorded pair is a field a write may set, at a value it may.

    Both halves, because the field is what says what the value MEANS: a
    counter that came back as text is not a smaller claim than an unknown key,
    it is the same damage one owner further on -- applied to the comment and
    then read by the cap that counts rounds.
    """
    if not isinstance(pair, list) or len(pair) != _PAIR:
        return False
    field, spent = pair
    spendable = _SPENDABLE_FIELDS.get(field)
    return spendable is not None and spendable(spent)


def write_late_spends(state: PinnedState, fields: tuple) -> None:
    """Record what a hold on this pair owes, or drop the key where nothing is.

    Written beside the generation and inside `LATE_STATE_KEYS`, so it lives
    and dies with the pair it is about: the retirement that ends a generation
    drops it in the same write, and no later cycle can be handed a round an
    earlier one was owed.
    """
    if not fields:
        state.data.pop(_SPENDS, None)
        return
    state.set(_SPENDS, [[key, spent] for key, spent in fields])


def clear_late_generation(state: PinnedState) -> None:
    """Drop every late field, leaving the rest of the pinned state alone."""
    for key in LATE_STATE_KEYS:
        state.data.pop(key, None)


def _written_fields(generation: LateGeneration) -> dict[str, Any]:
    """Return the pinned fields this generation records, unset ones out.

    A record with no cycle identity records only what it owes: the two
    ledgers, if either holds anything. Everything else on such a record is a
    half-record nothing could correlate, while an obligation stays an
    obligation whatever happened to the identity that was written beside it.

    A field at its own empty value -- an absent identity, an empty SHA, a
    ledger with nothing in it, a flag that is not set -- names itself None
    here and is dropped, so the pinned comment carries what this generation
    actually knows. A lineage depth of 0 is not one of them: it is the root of
    a lineage, and it is written as itself. What is dropped there is an
    unknown depth, which is not the same thing and must not be recorded as if
    it were.
    """
    ledgers = _ledger_fields(generation)
    if not generation.is_present:
        return ledgers
    fields = {
        **_evidence_fields(generation),
        **_publication_fields(generation),
        **ledgers,
        _SPLIT_CHILDREN: list(generation.split_children) or None,
        _LINKS_ANNOUNCED: generation.links_announced or None,
        _OWNER_CHECK_PENDING: generation.owner_check_pending or None,
        _CANCELLED: generation.cancelled or None,
        _CANCELLED_AT: generation.cancelled_at,
        _CANCELLED_PHASE: _wire(generation.cancelled_phase),
        _RESTART_PENDING: generation.restart_pending or None,
        _RESTART_TARGET: generation.restart_target,
        _RESTART_CYCLE_ID: generation.restart_cycle_id,
        _RESTART_PREDECESSOR: generation.restart_predecessor,
    }
    return {
        key: written
        for key, written in fields.items()
        if written is not None
    }


def _wire(member: Optional[StrEnum]) -> Optional[str]:
    """Return the wire string one vocabulary field is recorded under, or None.

    Every field holding a member goes through it -- the boundary a generation
    reached, the one it was cancelled from, and the stage it was entered at --
    so each is written exactly as the vocabulary that reads it back spells it.
    """
    return None if member is None else str(member)


def _evidence_fields(generation: LateGeneration) -> dict[str, Any]:
    """Return the identity, the frozen commits, and what they measured.

    A lineage depth of 0 is written as itself: it is the root of a lineage,
    and what is dropped instead is an unknown depth, which is not the same
    thing and must not be recorded as if it were.
    """
    return {
        _CYCLE_ID: generation.cycle_id or None,
        _GENERATION: generation.generation or None,
        _ROOT_ISSUE: generation.root_issue or None,
        _CURRENT_ISSUE: generation.current_issue or None,
        _LINEAGE_DEPTH: generation.lineage_depth,
        _SCOPE: generation.scope or None,
        _CANDIDATE_SHA: generation.candidate_sha or None,
        _BASE_SHA: generation.base_sha or None,
        _THRESHOLD: generation.threshold,
        _ADDITIONS: generation.additions,
        _PHASE: _wire(generation.phase),
        _TITLE_BODY_HASH: generation.title_body_hash,
        _COMMENT_HASH: generation.comment_hash,
        _COMMENT_WATERMARK_ID: generation.comment_watermark_id,
        _PLAN_PR_NUMBER: generation.plan_pr_number,
        _PLAN_PR_HEAD: generation.plan_pr_head or None,
        _PLAN_PR_BODY: generation.plan_pr_body,
    }


def _publication_fields(generation: LateGeneration) -> dict[str, Any]:
    """Return how this generation was entered, absent context dropped.

    A generation entered before anything was published records none of it, so
    the flag goes down only while it is set and the three fields beside it
    only while they hold something. That is what keeps a pre-publication entry
    and a record written without this group the same pinned comment, rather
    than two spellings a later reader would have to tell apart.
    """
    return {
        _POST_PUBLICATION: generation.post_publication or None,
        _SOURCE_STAGE: _wire(generation.source_stage),
        _PUBLISHED_PR_NUMBER: generation.published_pr_number,
        _PUBLISHED_SHA: generation.published_sha or None,
    }


def _ledger_fields(generation: LateGeneration) -> dict[str, Any]:
    """Return what the two external ledgers are written back as, unset out."""
    owed = {
        _RESOURCES: _ledger_written(
            generation.opaque_resources,
            _resource_payloads(generation.resources),
        ),
        _CONSUMERS: _ledger_written(
            generation.opaque_consumers, list(generation.consumers),
        ),
    }
    return {key: ledger for key, ledger in owed.items() if ledger is not None}


def _ledger_written(opaque: Optional[str], typed: list) -> Any:
    """Return what one external ledger is written back as.

    The verbatim copy outranks the typed view wherever there is one: the typed
    view is only the entries this binary could make sense of, and writing that
    in place of the ledger is how an obligation nobody here understands would
    disappear from the issue that still owes it.
    """
    if opaque is not None:
        return json.loads(opaque)
    return typed or None


def _resource_payloads(resources: tuple) -> list:
    """Return the JSON entries a typed obligation ledger is written as."""
    return [
        {
            _ledgers.KIND_KEY: str(resource.kind),
            _ledgers.TARGET_KEY: resource.target,
            _ledgers.STATE_KEY: str(resource.resource_state),
        }
        for resource in resources
    ]
