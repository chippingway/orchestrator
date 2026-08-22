# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The cycle-marked hold a plan PR wears while adjudication runs.

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
is proved rather than reserved. The prefix is still what the capture reads:
a body carrying a hold with no preserved original beside it is refused
outright rather than captured as though the hold text were somebody's
description.

What a retry and a release are allowed to touch is decided by the WHOLE body,
not by the hidden marker inside it. Exactly two bodies are this issue's to
replace -- the hold it wrote, verbatim, and the description recorded beside
the identity, which is what a crash between the persist and the edit leaves
and what the first application starts from. Anything else is somebody writing
over the notice, the marker they happened to leave in place included: a
sentence changed inside the hold is their edit as surely as a wholesale
rewrite is, and treating the marker as proof of an unchanged body would have
the release put a stale copy back over their words a step later.

That comparison is only affordable because the hold body is exactly
reconstructible, which is why it is scoped to the CYCLE and quotes nothing
that moves inside one. The generation counter advances on every reconciliation
that lands, so a body keyed to it would leave every re-measured candidate
wearing a notice its own record could no longer recognize -- and the
measurement belongs on the issue thread, where each new reading is announced
anyway.

Being reconstructible is a property of a SPELLING, though, and a hold outlives
the binary that wrote it: an orchestrator restarted mid-adjudication meets
descriptions its predecessor left on somebody's pull request. So the spelling
before this one is kept as something to recognize and never to write, and a
body found in it is rewritten in the current one by the same edit that would
have applied a fresh hold. A hold a binary cannot reconstruct is a "do not
merge" notice nothing can ever take back off.

Leaving a body alone is not the same as being held, and the answer says so. An
OPEN pull request whose notice a human rewrote is a change they can merge with
nothing on it saying an adjudication is open -- the precise state the hold
exists to prevent -- so the reconciliation reports it DISPLACED and the caller
starts no new agent under it. What it may still do is settle an answer it
already has, since that releases a hold which is already gone.

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

The release is the same reconciliation read backwards, and it is here rather
than beside the outcome that asks for it because what a hold is allowed to
touch is one question with one answer. A body that IS this cycle's hold,
verbatim, is one this issue displaced, so the description it replaced is
written back over it. Everything else is left exactly as it stands -- a body a
human rewrote or edited while the hold stood is theirs, and a preserved copy
of what it replaced is stale beside it. What those cases leave is the ordinary path: the
publication that follows reconciles this issue's pull request against the
exact committed candidate the way it does for any other change.

What a failed release may STOP is narrower than what the hold's own failure
stops, and for the reason the hold exists: the danger is a change a human can
merge while it still wears a notice saying not to, which is a property of an
OPEN pull request. So only a reusable one can hold the accepted candidate
back. A plan PR somebody has already merged or closed is tidied where the
edit lands and stepped over where it does not -- refusing to publish an
adjudicated candidate over the description of a settled pull request would be
a permanent block bought for nothing.
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
# it is what decides whether capturing the current body would preserve
# somebody's description or a hold.
_HOLD_PREFIX = "<!--orchestrator-late-hold"


def _hold_marker(generation: LateGeneration) -> str:
    """The marker identifying one CYCLE's hold on a plan PR body.

    Scoped to the cycle and not to the generation inside it, because what the
    hold says is true of the whole adjudication rather than of one attempt at
    it: the generation counter advances on every reconciliation that lands,
    and a marker that moved with it would leave every re-measured candidate
    wearing a notice its own record no longer recognized.
    """
    return f"{_HOLD_PREFIX}:cycle={generation.cycle_id}-->"


def _hold_body(generation: LateGeneration) -> str:
    """The temporary description a held plan PR carries.

    Every part of it is derived from fields that do not move inside a cycle,
    which is the property both the retry and the release are built on: the
    body this issue wrote is reconstructible EXACTLY, so "is this still ours?"
    is one comparison rather than a guess from a hidden marker somebody could
    have left in place while rewriting the sentence around it. What the
    candidate currently measures is deliberately not in here for that reason
    -- it moves with every revision, and the issue thread is where each new
    measurement is announced.
    """
    return (
        f"{_hold_marker(generation)}\n"
        ":hourglass: **Held by the orchestrator.** The committed "
        f"implementation for issue #{generation.current_issue} measured past "
        "the size ceiling, so it is being adjudicated before anything is "
        "published. Do not merge this pull request while the hold "
        "stands.\n\n"
        "This description is temporary. The original is preserved in the "
        "issue's pinned orchestrator state and is restored when adjudication "
        "finishes."
    )


def _superseded_hold_body(generation: LateGeneration) -> str:
    """The same hold as an earlier binary of ours spelled it.

    A hold is bytes on somebody else's pull request, which makes its wording a
    compatibility contract rather than a detail: an orchestrator upgraded
    mid-adjudication meets descriptions its predecessor wrote, and a spelling
    it cannot reconstruct is one it reads as a human's own words -- refusing
    to restore the preserved copy and refusing to start anything under the
    pull request, for good.

    So the older spelling is kept, exactly, as something to RECOGNIZE. It is
    never written: a body found in it is rewritten in the current one by the
    same reconciliation that would have applied a fresh hold, which is one
    edit and leaves every later comparison with a single answer to make.

    It is marked by generation as well as cycle and quotes the measurement,
    which is why it was replaced -- both move inside a cycle, so a
    re-measurement left the pull request wearing a notice the next tick could
    no longer rebuild. Reconstructible here for the generation that is
    actually recorded, which is the upgrade this exists for: the binary
    changed under a hold, and nothing about the candidate did.
    """
    return (
        f"{_HOLD_PREFIX}:cycle={generation.cycle_id}"
        f":generation={generation.generation}-->\n"
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


def _wears_our_hold(generation: LateGeneration, body: str) -> bool:
    """Whether this description is a hold THIS generation wrote, any spelling.

    The one question both the retry and the release ask, so an upgrade is
    handled in one place rather than in two that could disagree about it. Two
    spellings are reconstructible and no others: what this binary writes, and
    what the binary before it wrote. Anything else is a human's, whatever
    hidden marker it happens to carry.
    """
    return body in (_hold_body(generation), _superseded_hold_body(generation))


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


def _release_plan_pr_hold(
    gh: GitHubClient, issue: Issue, generation: LateGeneration,
) -> _PlanPrHold:
    """Take this generation's hold off the plan PR it marked, if it still is.

    Which pull request is asked is the generation's own record, not whichever
    one the issue currently points at: the hold was taken on exactly the
    pull request `plan_pr_number` names, the body beside it is the only copy
    of the description that hold displaced, and a `pr_number` the issue has
    since been re-pointed at is a different change nothing here marked.

    Provenance is deliberately NOT re-asked. It decided whether the
    description could be replaced, and it was decided on the snapshot that was
    replaced; asking again means a human pushing onto the plan branch while
    the adjudication ran would leave the "do not merge" notice standing
    forever on a pull request nothing is adjudicating any more. What proves
    the current text is this generation's to overwrite is the marker in it,
    which is a fact about the body rather than about the head above it.

    Only a REUSABLE pull request can hold the caller up. `failed` is what
    parks it, and what parking is for is a change a human can still merge
    while it wears a "do not merge" notice this generation put there -- which
    is a description of an OPEN pull request and of no other kind. One a human
    has already merged or closed is settled, so its description is tidied on a
    best-effort basis and an edit GitHub refuses is logged and stepped over
    rather than being allowed to hold an accepted candidate back for good. A
    pull request that could not be read at all fails closed with the open
    ones: what could not be read might be open.

    Everything else leaves the generation exactly as it arrived with nothing
    touched -- nothing recorded, a body somebody rewrote while the hold stood,
    and one already released, since a preserved copy that is no longer what
    the description says is stale and a human's own words are not this
    generation's to replace.
    """
    pr_number = generation.plan_pr_number
    if pr_number is None or generation.plan_pr_body is None:
        return _PlanPrHold(generation=generation)
    plan_pr = _readable_plan_pr(gh, issue, pr_number)
    if plan_pr is None:
        return _PlanPrHold(generation=generation, failed=True)
    if not _wears_our_hold(generation, plan_pr.body):
        log.info(
            "issue=#%d plan PR #%d does not carry this cycle's hold "
            "verbatim; leaving its description alone",
            issue.number, pr_number,
        )
        return _PlanPrHold(generation=generation)
    return _restored_body(gh, issue, generation, plan_pr)


def _restored_body(
    gh: GitHubClient,
    issue: Issue,
    generation: LateGeneration,
    plan_pr: _PlanPr,
) -> _PlanPrHold:
    """Write the preserved description back, and say whether it had to land.

    The reusability of the pull request is what decides that, and it is read
    off the same snapshot the edit is made against. A refused edit on an open
    plan PR is a hold still standing on a change somebody can merge, so the
    caller parks; a refused edit on one already merged or closed is untidy and
    nothing more, so the accepted candidate goes on publishing.
    """
    reusable = plan_pr.pr_state == _OPEN_PR_STATE
    try:
        gh.edit_pr_body(plan_pr.pull_request, generation.plan_pr_body)
    except Exception:
        log.exception(
            "issue=#%d could not restore the description of plan PR #%d "
            "(state=%s)",
            issue.number, plan_pr.number, plan_pr.pr_state,
        )
        return _PlanPrHold(generation=generation, failed=reusable)
    return _PlanPrHold(generation=generation)


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
    """Write the hold over a body this issue wrote or preserved, and no other.

    The one place the retry is made idempotent, and the one place a crash is
    told apart from a human. Three bodies can be on the pull request when this
    runs, and each answers differently:

    * this cycle's hold, VERBATIM -- the edit already landed, so the retry
      does nothing rather than editing a second time. Verbatim and not "wears
      the marker", because a sentence somebody changed inside the notice is
      their edit, and calling it held is what would have the release put the
      preserved copy back over their words;
    * the description recorded beside the identity -- exactly what a crash
      between the persist and the edit leaves behind, and the first
      application besides;
    * the same hold in the spelling an earlier binary used, which is the
      upgrade case: the notice is ours and stands, so it is rewritten in the
      current spelling by the very edit that would have applied a fresh one;
    * anything else -- a human writing over the notice. That body is theirs,
      the preserved copy is no longer a description of it, and the release
      beside this one already refuses to overwrite it.

    A generation that advanced needs no case of its own: the hold is keyed to
    the cycle and quotes nothing that moves inside one, so a re-measured
    candidate leaves its pull request wearing the same body this reconstructs.
    """
    if plan_pr.body == _hold_body(generation):
        return _PlanPrHold(generation=generation, held=True)
    if not _wears_our_hold(generation, plan_pr.body) and (
        plan_pr.body != generation.plan_pr_body
    ):
        log.warning(
            "issue=#%d plan PR #%d carries a description this issue did not "
            "displace; leaving it alone and reporting the hold displaced",
            issue.number, plan_pr.number,
        )
        return _PlanPrHold(
            generation=generation,
            displaced=plan_pr.pr_state == _OPEN_PR_STATE,
        )
    try:
        gh.edit_pr_body(plan_pr.pull_request, _hold_body(generation))
    except Exception:
        log.exception(
            "issue=#%d could not hold plan PR #%d",
            issue.number, plan_pr.number,
        )
        return _PlanPrHold(generation=generation, failed=True)
    return _PlanPrHold(generation=generation, held=True)
