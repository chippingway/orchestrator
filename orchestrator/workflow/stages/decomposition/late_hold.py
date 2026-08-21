# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The generation-marked hold a plan PR wears while adjudication runs.

An issue that reached its implementation through a design discussion can have
an open plan pull request standing when its committed candidate turns out to
be oversized. Left alone, that pull request reads as a change ready to be
merged for however long adjudication takes -- and adjudication can end by
superseding it. So its body is replaced with a hold that says what is
happening, and the body it replaced is preserved on the issue's own pinned
comment so the original can be put back.

Only a plan pull request, and the question of whether one IS a plan is not
this owner's to answer twice. `pr_number` names whichever pull request the
issue currently records, and that is an implementation PR as often as a plan
-- so the discussion provenance is read through `_recorded_pr_is_the_plan`,
the same two records the implementing stage tells them apart by. An
implementation PR is simply not held: overwriting its description would
replace a human's account of a change under review with a notice about a
different one.

One fetch answers all of it. Past the discussion handoff the plan is told from
an implementation by the commit its head is on, and a head moves whenever a
human pushes -- so the snapshot classified has to be the snapshot edited.
Reading the pull request twice would leave a window in which somebody's
implementation becomes the description this preserves and replaces.

Persist first, then mutate. The identity and the original body are written to
pinned state BEFORE the pull request is edited, so the only thing a crash can
lose is the edit -- which the next tick re-applies -- and never the original
body, which nothing else holds a copy of. A write that REFUSES is the same
rule read the other way: with no preserved copy, there is no hold to take, so
nothing is edited and the caller parks. Whether the write CAN land is asked
before it is made, and asked about the record that STARTS the run as well --
built from the spec this issue is locked to, since that spec is an operator's
command line and bounded by nothing here. That record's own write has no safe
failure, parking being another write of the same comment, so the room for it
is proved rather than reserved. That ordering is also what makes the
marker readable: a body already carrying THIS generation's marker has been
held, so the retry does nothing rather than editing a second time, and a body
carrying a hold with no preserved original beside it is refused outright
rather than captured as though the hold text were somebody's description.

The hold reads pull-request state and never writes the candidate. A human who
merges or closes the plan PR while the agent runs has decided something about
that pull request, not about the commit under adjudication: the frozen
candidate and base SHAs are the evidence every later step acts on, so nothing
here re-derives them from a pull request's head, and a plan PR that is no
longer open is simply not held -- with its recorded identity and preserved
body kept, because the outcome still has to reconcile against it.

A hold that could not be reconciled is a park, not a warning. Everything after
this point spawns an agent against work a human might be looking at through
the pull request this failed to mark, so the caller stops before the spawn and
a later tick retries the same reconciliation -- which is why every branch here
is idempotent.
"""
from __future__ import annotations

import logging
from dataclasses import replace
from typing import Optional

from github.Issue import Issue

from orchestrator.github.client import GitHubClient
from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.late_split import payloads as _payloads
from orchestrator.workflow.late_split import state as _late_state
from orchestrator.workflow.late_split.models import LateGeneration
from orchestrator.workflow.stages.decomposition import (
    late_session as _late_session,
)
from orchestrator.workflow.stages.decomposition.late_models import (
    _PlanPr,
    _PlanPrHold,
)
from orchestrator.workflow.stages.implementing import handler as _implementing

log = logging.getLogger("orchestrator.workflow")

# Whichever pull request this issue currently records. Shared with every other
# stage that reads it, and it names a plan only sometimes -- which is why the
# provenance beside it decides whether the hold may touch the description.
_PR_NUMBER = "pr_number"

_OPEN_PR_STATE = "open"

# The marker every late hold opens with. The prefix is what identifies a body
# as held at all -- by any cycle, including one an older binary wrote -- and
# the identity after it is what tells THIS generation's hold from another's.
# Both halves are load-bearing: the prefix decides whether capturing the
# current body would preserve somebody's description or a hold, and the
# identity decides whether the retry has anything left to do.
_HOLD_PREFIX = "<!--orchestrator-late-hold"


def _hold_marker(generation: LateGeneration) -> str:
    """The marker identifying one generation's hold on a plan PR body."""
    return (
        f"{_HOLD_PREFIX}:cycle={generation.cycle_id}"
        f":generation={generation.generation}-->"
    )


def _hold_body(generation: LateGeneration) -> str:
    """The temporary description a held plan PR carries."""
    return (
        f"{_hold_marker(generation)}\n"
        ":hourglass: **Held by the orchestrator.** The committed "
        f"implementation for issue #{generation.current_issue} measures "
        f"{generation.additions} added lines against a ceiling of "
        f"{generation.threshold}, so it is being adjudicated before anything "
        "is published. Do not merge this pull request while the hold "
        "stands.\n\n"
        "This description is temporary. The original is preserved in the "
        "issue's pinned orchestrator state and is restored when adjudication "
        "finishes."
    )


def _reconcile_plan_pr_hold(
    gh: GitHubClient,
    issue: Issue,
    state: PinnedState,
    generation: LateGeneration,
) -> _PlanPrHold:
    """Bring this generation's hold on any reusable plan PR up to date.

    Answers three ways. Nothing to hold -- no recorded pull request, one that
    is not the plan, or one that is no longer open -- leaves the generation
    exactly as it arrived and lets the caller spawn. A reconciled hold reports
    `held`. A pull request that could not be read, whose provenance could not
    be established, that already wears a hold nothing preserved a body for, or
    that refused the edit reports `failed`, and the caller parks without
    spawning.

    The pull request is fetched ONCE and everything is decided about that one
    snapshot -- its provenance, its state, and the body preserved from it --
    because a head is a mutable thing. Past the discussion handoff a plan is
    told from an implementation by the commit its head is on, so a tick that
    classified one read and then edited another could preserve and overwrite a
    description a human pushed in between.
    """
    pr_number = _payloads.as_identity(state.get(_PR_NUMBER))
    if pr_number is None:
        return _PlanPrHold(generation=generation)
    plan_pr = _readable_plan_pr(gh, issue, pr_number)
    if plan_pr is None:
        return _PlanPrHold(generation=generation, failed=True)
    if not _plan_provenance(gh, issue, state, plan_pr):
        return _PlanPrHold(generation=generation)
    if plan_pr.pr_state != _OPEN_PR_STATE:
        log.info(
            "issue=#%d plan PR #%d is not open; leaving the frozen candidate "
            "and any recorded hold exactly as they are",
            issue.number, pr_number,
        )
        return _PlanPrHold(generation=generation)
    return _reconciled_hold(gh, issue, state, generation, plan_pr)


def _plan_provenance(
    gh: GitHubClient, issue: Issue, state: PinnedState, plan_pr: _PlanPr,
) -> bool:
    """Whether THIS snapshot of the recorded pull request is the plan.

    Read through the implementing stage's own answer rather than re-derived,
    so what counts as a plan is decided in one place: while the discussion's
    plan path stands nothing has pushed, and past that handoff the recorded
    plan commit is compared against the pull request's head.

    Asked about the snapshot the hold is holding, which is what removes the
    window between deciding and acting. It also removes the third answer that
    question can have: "could not ask" belongs to a fetch, and the fetch has
    already happened and already failed closed if it was going to.
    """
    is_plan = _implementing._recorded_pr_is_the_plan(
        gh, issue, state, plan_pr.head_sha,
    )
    if not is_plan:
        log.info(
            "issue=#%d PR #%d is not this issue's plan; leaving its "
            "description alone",
            issue.number, plan_pr.number,
        )
    return bool(is_plan)


def _reconciled_hold(
    gh: GitHubClient,
    issue: Issue,
    state: PinnedState,
    generation: LateGeneration,
    plan_pr: _PlanPr,
) -> _PlanPrHold:
    """Decide what an open plan PR needs: a retry, a refusal, or a hold.

    The middle one is the crash window the persist-first order leaves no room
    for: a body already carrying a hold that this issue preserved no original
    for was held by something else -- an older cycle, another binary -- and
    capturing it would record the hold text as somebody's description,
    destroying the only copy of it. A human settles that; this refuses it.
    """
    if (
        generation.plan_pr_number == plan_pr.number
        and generation.plan_pr_body is not None
    ):
        return _applied_hold(gh, issue, generation, plan_pr)
    if _HOLD_PREFIX in plan_pr.body:
        log.error(
            "issue=#%d plan PR #%d already carries a late hold this issue "
            "preserved no body for; refusing to overwrite it",
            issue.number, plan_pr.number,
        )
        return _PlanPrHold(generation=generation, failed=True)
    return _taken_hold(gh, issue, state, generation, plan_pr)


def _readable_plan_pr(
    gh: GitHubClient, issue: Issue, pr_number: int,
) -> Optional[_PlanPr]:
    """Read the recorded plan PR, or None when GitHub could not be asked.

    The fetch and every field the hold decides on are read together, inside
    one guard, because a PyGithub pull request is lazy: `get_pr` asks GitHub
    nothing and the request that can fail is the first attribute read. A guard
    around the fetch alone would catch almost nothing -- the failure would
    land on the head, the state, or the body instead, halfway through deciding
    whether to replace a human's description, and escape as an exception no
    tick could park on.

    Fail closed: a pull request that cannot be read is one the hold cannot be
    proven on, and the alternative to parking is spawning an agent while a
    human still sees an unmarked, apparently-ready change.
    """
    try:
        return _read_plan_pr(gh, pr_number)
    except Exception:
        log.exception(
            "issue=#%d could not read plan PR #%d for the late hold",
            issue.number, pr_number,
        )
        return None


def _read_plan_pr(gh: GitHubClient, pr_number: int) -> _PlanPr:
    """Fetch one pull request and read every field a decision is made on.

    Every read is here so every read is inside the caller's guard. The head
    defaults to empty rather than raising on a shape without one, since a head
    nobody can name is not the plan commit either way -- what must not happen
    is the read itself escaping.
    """
    plan_pr = gh.get_pr(pr_number)
    return _PlanPr(
        pull_request=plan_pr,
        number=plan_pr.number,
        body=plan_pr.body or "",
        head_sha=getattr(plan_pr.head, "sha", "") or "",
        pr_state=gh.pr_state(plan_pr),
    )


def _taken_hold(
    gh: GitHubClient,
    issue: Issue,
    state: PinnedState,
    generation: LateGeneration,
    plan_pr: _PlanPr,
) -> _PlanPrHold:
    """Record the identity and the original body, then apply the hold.

    A write that does not land is a hold that may not be taken. The preserved
    body is the only copy of the description the edit is about to replace, so
    editing on the strength of a record nobody kept would destroy it. Nothing
    is edited and the caller parks.

    Whether it CAN land is asked before anything is written, and asked about
    the whole of what follows rather than about this write alone. A body that
    fits the comment exactly is the worst case, not the safe one: the write
    that STARTS the run comes next and has no safe failure of its own, since
    parking is another write of the same oversized comment. So the run record
    that write would make -- built from the spec this issue is locked to,
    which is an operator's command line and bounded by nothing here -- is
    measured beside the preserved body, and a description too long to hold
    with it is refused while nothing has been touched and a park is still
    small enough to land.
    """
    holding = replace(
        generation,
        plan_pr_number=plan_pr.number,
        plan_pr_body=plan_pr.body,
    )
    prospective = PinnedState(data=dict(state.data))
    _late_state.write_late_generation(prospective, holding)
    if not _late_session._holdable(prospective.data, holding):
        log.error(
            "issue=#%d cannot preserve the body of plan PR #%d and still "
            "record the run; refusing to hold it",
            issue.number, plan_pr.number,
        )
        return _PlanPrHold(generation=generation, failed=True)
    _late_state.write_late_generation(state, holding)
    try:
        gh.write_pinned_state(issue, state)
    except Exception:
        log.exception(
            "issue=#%d could not preserve the body of plan PR #%d; refusing "
            "to hold it", issue.number, plan_pr.number,
        )
        return _PlanPrHold(generation=generation, failed=True)
    return _applied_hold(gh, issue, holding, plan_pr)


def _applied_hold(
    gh: GitHubClient,
    issue: Issue,
    generation: LateGeneration,
    plan_pr: _PlanPr,
) -> _PlanPrHold:
    """Write the hold body unless this generation's marker is already there.

    The one place the retry is made idempotent. A body a human replaced while
    the hold stood is re-marked -- the preserved original stays the one
    captured first, since the replacement is not a description this generation
    ever displaced.
    """
    if _hold_marker(generation) in plan_pr.body:
        return _PlanPrHold(generation=generation, held=True)
    try:
        gh.edit_pr_body(plan_pr.pull_request, _hold_body(generation))
    except Exception:
        log.exception(
            "issue=#%d could not hold plan PR #%d",
            issue.number, plan_pr.number,
        )
        return _PlanPrHold(generation=generation, failed=True)
    return _PlanPrHold(generation=generation, held=True)
