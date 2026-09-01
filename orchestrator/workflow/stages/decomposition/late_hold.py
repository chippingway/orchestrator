# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The cycle-marked hold a pull request wears while adjudication runs.

An oversized committed candidate can have an open pull request standing over
it, and which one that is depends on the side of publication the generation
was entered on. Before the first push it is the plan pull request a design
discussion left behind. Past it, it is the implementation pull request the
work is already on -- the one the gate measured the candidate against, and the
one a split ends by superseding. Left alone, either reads as a change ready to
be merged for however long adjudication takes. So its body is replaced with a
hold that says what is happening, and the body it replaced is preserved on the
issue's own pinned comment so the original can be put back.

Which pull request that is, this owner decides once and from the record. A
generation carrying a publication entry names its own: the gate proved that
pull request open and froze it there, so nothing here re-derives it and
nothing looks it up. A generation entered before publication has only
`pr_number`, which names whichever pull request the issue currently records
and is an implementation PR as often as a plan -- so the discussion provenance
is read through `_recorded_pr_is_the_plan`, the same two records the
implementing stage tells them apart by. An implementation PR no entry says the
candidate was measured against is still not held: overwriting its description
would replace a human's account of a change under review with a notice about a
different one.

A hold this generation already took outranks both, up to a point. The identity
and the body it displaced are written as ONE thing and that body is the only
copy there is, so the pull request the record names is the pull request every
later tick reconciles rather than one it went looking for -- an issue
re-pointed at another change would otherwise have a second hold overwrite the
first one's only copy.

The point it stops at is a record that has MOVED. A generation re-measured
past its own push is adjudicating the change on the published pull request,
and its entry says so; a "do not merge" left standing on the plan one marks
nothing while the change a human could actually merge carries no notice at
all. So a stale hold is settled before anything else is decided -- the old one
released, the slot freed, the new one taken -- and never both at once, since
there is one identity and one preserved body to hold them in. A release that
could not be made on a reusable pull request parks the caller instead: the
alternative is a second hold taken over the only copy of the first one's
description.

One fetch answers all of it. Past the discussion handoff the plan is told from
an implementation by the commit its head is on, and a head moves whenever a
human pushes -- so the snapshot classified has to be the snapshot edited.
Reading the pull request twice would leave a window in which somebody's
implementation becomes the description this preserves and replaces.

The head that snapshot stands on is read with the body, recorded beside it,
and required for the hold to be taken at all. A head this reading cannot name
is refused where the rest of the record is: the pinned write drops an empty
one, so persisting it would leave the description replaced and an agent
started under a notice nothing could later say which change it was written
over -- the same answer a body nothing could preserve gets, and for the same
reason.

What the head IS is a reading rather than a claim. What it says is which change
wore the notice: an adjudication runs for as long as an agent takes, and
somebody pushing to the branch underneath leaves the same pull request standing
on a different commit. That movement decides nothing here -- what the hold is
about is a description a human could merge under, and the frozen candidate and
base commits are the evidence every later step acts on -- so it is reported and
the record is left exactly as the hold took it. It is also why the published
head one field over is never written from here: that one is the tip the GATE
was entered on and what a settlement pins its push to, and re-stamping it from
whatever this owner happened to read would move the evidence under the verdict.

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

What the notice SAYS is decided by the side of publication and by nothing
else. A pull request nothing has pushed to is being adjudicated before
anything is published; the one the work is already ON was published long
before this, and a notice telling its author their change is held "before
anything is published" describes a change that is not theirs. So there are two
current spellings, one per side -- both recognized, only ever one written,
which is what makes a record that crosses publication mid-cycle an upgrade
rather than a hold this issue would read as somebody else's words.

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
merges or closes the held pull request while the agent runs has decided
something about that pull request, not about the commit under adjudication:
the frozen candidate and base SHAs are the evidence every later step acts on,
so nothing here re-derives them from a pull request's head, and one that is no
longer open is simply not held -- with its recorded identity, head, and
preserved body kept, because the outcome still has to reconcile against it.

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
back. One somebody has already merged or closed is tidied where the edit
lands and stepped over where it does not -- refusing to publish an
adjudicated candidate over the description of a settled pull request would be
a permanent block bought for nothing.
"""
from __future__ import annotations

import logging
from dataclasses import replace

from github.Issue import Issue

from orchestrator.github.client import GitHubClient
from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.late_split import formats as _formats
from orchestrator.workflow.late_split import payloads as _payloads
from orchestrator.workflow.late_split import state as _late_state
from orchestrator.workflow.late_split.models import LateGeneration
from orchestrator.workflow.stages.decomposition import (
    late_session as _late_session,
)
from orchestrator.workflow.stages.decomposition.late_models import (
    _HeldPr,
    _HeldPrHold,
)
from orchestrator.workflow.stages.implementing import handler as _implementing

log = logging.getLogger("orchestrator.workflow")

# Whichever pull request this issue currently records. Shared with every other
# stage that reads it, and it names a plan only sometimes -- which is why the
# provenance beside it decides whether the hold may touch the description. It
# is the last place a target is looked for, since a record naming one of its
# own names it better.
_PR_NUMBER = "pr_number"

_OPEN_PR_STATE = "open"

# The marker every late hold opens with. The prefix is what identifies a body
# as held at all -- by any cycle, including one an older binary wrote -- and
# it is what decides whether capturing the current body would preserve
# somebody's description or a hold.
_HOLD_PREFIX = "<!--orchestrator-late-hold"

# What every hold says once it has said which change it is holding. Shared
# rather than repeated because it is the part that is true on both sides of
# publication, and because the older spelling below has to reproduce it
# exactly.
_HOLD_TAIL = (
    "Do not merge this pull request while the hold stands.\n\n"
    "This description is temporary. The original is preserved in the issue's "
    "pinned orchestrator state and is restored when adjudication finishes."
)


def _hold_marker(generation: LateGeneration) -> str:
    """The marker identifying one CYCLE's hold on a held PR body.

    Scoped to the cycle and not to the generation inside it, because what the
    hold says is true of the whole adjudication rather than of one attempt at
    it: the generation counter advances on every reconciliation that lands,
    and a marker that moved with it would leave every re-measured candidate
    wearing a notice its own record no longer recognized.
    """
    return f"{_HOLD_PREFIX}:cycle={generation.cycle_id}-->"


def _hold_body(generation: LateGeneration) -> str:
    """The temporary description a held pull request carries.

    Every part of it is derived from fields that do not move inside a cycle,
    which is the property both the retry and the release are built on: the
    body this issue wrote is reconstructible EXACTLY, so "is this still ours?"
    is one comparison rather than a guess from a hidden marker somebody could
    have left in place while rewriting the sentence around it. What the
    candidate currently measures is deliberately not in here for that reason
    -- it moves with every revision, and the issue thread is where each new
    measurement is announced.

    Which of the two it writes is the side of publication the generation was
    entered on, because the sentence a human reads has to be true of the
    change they are looking at. A pull request nothing has pushed to is
    adjudicated before anything is published; one the work is already ON was
    published a while ago, and telling its author their change is being held
    "before anything is published" describes somebody else's.
    """
    if generation.has_publication_context:
        return _published_hold_body(generation)
    return _unpublished_hold_body(generation)


def _unpublished_hold_body(generation: LateGeneration) -> str:
    """The notice a pull request nothing has pushed to carries.

    Byte-for-byte what this hold has always said, because a spelling is a
    compatibility contract: holds written by earlier binaries are standing on
    live pull requests right now, and a word changed here would read every one
    of them as a human's own description -- refusing to restore the copy it
    replaced, and refusing to start anything under it, for good.
    """
    return (
        f"{_hold_marker(generation)}\n"
        ":hourglass: **Held by the orchestrator.** The committed "
        f"implementation for issue #{generation.current_issue} measured past "
        "the size ceiling, so it is being adjudicated before anything is "
        f"published. {_HOLD_TAIL}"
    )


def _published_hold_body(generation: LateGeneration) -> str:
    """The notice the pull request the work is already on carries.

    What the gate measured on this side is not the commit's own diff but
    everything the pull request comes to with the commit in it, and the commit
    is not on it yet -- so what the notice names is the push the adjudication
    stands in front of, rather than a publication that already happened.

    Cycle-stable like the other one, and for the same comparison: the pull
    request it is written onto, the ceiling it is measured against, and what
    it currently comes to are all left out, since every one of them can move
    while a hold stands.
    """
    return (
        f"{_hold_marker(generation)}\n"
        ":hourglass: **Held by the orchestrator.** The committed "
        f"implementation for issue #{generation.current_issue} takes this "
        "pull request past the size ceiling, so it is being adjudicated "
        f"before that commit is pushed onto it. {_HOLD_TAIL}"
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

    There is no published counterpart to reconstruct. No binary that wrote
    this spelling ever marked a pull request the work was already on, so a
    body found in it was written before publication whatever the record beside
    it says now.
    """
    return (
        f"{_HOLD_PREFIX}:cycle={generation.cycle_id}"
        f":generation={generation.generation}-->\n"
        ":hourglass: **Held by the orchestrator.** The committed "
        f"implementation for issue #{generation.current_issue} measures "
        f"{generation.additions} added lines against a ceiling of "
        f"{generation.threshold}, so it is being adjudicated before anything "
        f"is published. {_HOLD_TAIL}"
    )


def _wears_our_hold(generation: LateGeneration, body: str) -> bool:
    """Whether this description is a hold THIS generation wrote, any spelling.

    The one question both the retry and the release ask, so an upgrade is
    handled in one place rather than in two that could disagree about it.
    Three spellings are reconstructible and no others: the two this binary
    writes, one per side of publication, and the one the binary before it
    wrote. Anything else is a human's, whatever hidden marker it happens to
    carry.

    Both current spellings are recognized, and only ever one of them written.
    That is what makes a record that crosses publication mid-cycle -- a
    developer resumed on guidance, a push, a re-measurement entered past it --
    an upgrade like any other rather than a hold this issue reads as somebody
    else's: the notice already standing is still ours, so the same edit that
    would have applied a fresh one rewrites it in the side the record now
    names, and every later comparison has a single answer to make.
    """
    return body in (
        _unpublished_hold_body(generation),
        _published_hold_body(generation),
        _superseded_hold_body(generation),
    )


def _reconcile_hold(
    gh: GitHubClient,
    issue: Issue,
    state: PinnedState,
    generation: LateGeneration,
) -> _HeldPrHold:
    """Bring this generation's hold on any reusable pull request up to date.

    Answers three ways. Nothing to hold -- no pull request this generation can
    name, one it may not mark, or one that is no longer open -- leaves the
    generation exactly as it arrived and lets the caller spawn. A reconciled
    hold reports `held`. A pull request that could not be read, whose
    provenance could not be established, that already wears a hold nothing
    preserved a body for, or that refused the edit reports `failed`, and the
    caller parks without spawning.

    The pull request is fetched ONCE and everything is decided about that one
    snapshot -- what it may be, its state, the head it stands on, and the body
    preserved from it -- because a head is a mutable thing. Past the
    discussion handoff a plan is told from an implementation by the commit its
    head is on, so a tick that classified one read and then edited another
    could preserve and overwrite a description a human pushed in between.

    A hold left on a pull request this record has since moved off is settled
    BEFORE any of that, because the notice has to end up where the candidate
    is: a generation re-measured past its own push is adjudicating the change
    on the published pull request, and a "do not merge" standing on the plan
    one instead marks nothing while leaving the change a human could merge
    unmarked. The old hold is released first and the new one taken after --
    never both at once, since the record holds one identity and one preserved
    body, and taking the second before restoring the first would destroy the
    only copy of a description there is.
    """
    settled = _settled_stale_hold(gh, issue, generation)
    if settled is None:
        return _refused(generation)
    return _reconciled_target(gh, issue, state, settled)


def _refused(generation: LateGeneration) -> _HeldPrHold:
    """The answer every refusal here gives: nothing marked, caller parks.

    Spelled once because it is one decision read six ways -- a pull request
    nobody could read, a hold nobody could move, a body nobody could preserve,
    an edit GitHub declined. What follows any of them is an agent started
    against work a human might be looking at through a pull request this
    failed to mark, so all of them stop the tick in exactly the same place.
    """
    return _HeldPrHold(generation=generation, failed=True)


def _reconciled_target(
    gh: GitHubClient,
    issue: Issue,
    state: PinnedState,
    generation: LateGeneration,
) -> _HeldPrHold:
    """Reconcile the hold on whichever pull request this record now names.

    Reached with the hold's slot free of anything stale, so the pull request
    chosen here is the one the record means and there is no second one to
    settle first.
    """
    pr_number = _hold_subject(state, generation)
    if pr_number is None:
        return _HeldPrHold(generation=generation)
    held_pr = _readable_held_pr(gh, issue, pr_number)
    if held_pr is None:
        return _refused(generation)
    if not _may_be_held(gh, issue, state, generation, held_pr):
        return _HeldPrHold(generation=generation)
    if held_pr.pr_state != _OPEN_PR_STATE:
        log.info(
            "issue=#%d PR #%d is not open; leaving the frozen candidate and "
            "any recorded hold exactly as they are",
            issue.number, pr_number,
        )
        return _HeldPrHold(generation=generation)
    return _reconciled_hold(gh, issue, state, generation, held_pr)


def _stale_hold(generation: LateGeneration) -> bool:
    """Whether the recorded hold marks a pull request this record has left.

    One record says it: a publication entry naming a pull request the hold
    does not. That entry is the gate's own proof of which change the candidate
    is measured against, so a hold standing anywhere else is marking a change
    nothing is adjudicating -- and, worse, leaving the one that IS adjudicated
    open with nothing on it saying so.

    `pr_number` moving is deliberately NOT this answer. It names whichever
    pull request the issue currently records rather than the change under
    adjudication, and a hold that chased it would come off a pull request over
    a pointer somebody re-aimed.
    """
    if generation.plan_pr_number is None or generation.plan_pr_body is None:
        return False
    if not generation.has_publication_context:
        return False
    return generation.published_pr_number != generation.plan_pr_number


def _settled_stale_hold(
    gh: GitHubClient, issue: Issue, generation: LateGeneration,
) -> LateGeneration | None:
    """Release a hold this record has moved off, or refuse to move it.

    Returns the record with the hold's slot free where there was nothing to
    settle or the release landed, and None where it did not -- which parks the
    caller, since the alternative is a second hold taken over the only copy of
    the first one's description.

    The slot is cleared in memory and not written on its own. What persists it
    is the capture of the NEW hold, one write carrying all three fields, so no
    tick is ever left reading a record that has forgotten both. A crash before
    that write leaves the old identity standing over a description already put
    back, which the next tick releases again for nothing: the body is no
    longer this cycle's hold, so the release reports nothing and the migration
    runs on.
    """
    if not _stale_hold(generation):
        return generation
    log.info(
        "issue=#%d holds PR #%d while its publication entry names PR #%d; "
        "restoring the first before marking the second",
        issue.number,
        generation.plan_pr_number,
        generation.published_pr_number,
    )
    release = _release_hold(gh, issue, generation)
    if release.failed:
        return None
    return replace(
        release.generation,
        plan_pr_number=None,
        plan_pr_head="",
        plan_pr_body=None,
    )


def _hold_subject(
    state: PinnedState, generation: LateGeneration,
) -> int | None:
    """Which pull request this generation's hold is taken on, if any.

    Three sources, in the order each stops being answerable by the one after
    it. A hold already recorded names its own pull request and outranks the
    rest: the preserved body beside that identity is the only copy of a
    description there is, so a tick that went looking for a target instead
    could take a second hold and overwrite it -- which is exactly what an
    issue re-pointed at another change would otherwise arrange. It outranks
    them only because a hold the record has MOVED OFF has already been
    released by the time this is asked, and the slot it held is free. A
    publication entry names the pull request the work is already on, proved
    open by the gate and frozen there because nothing here could re-derive it.
    Failing both, the issue's own record is the only pull request there is,
    and it is the one whose provenance has to be established before a word of
    it is replaced.
    """
    if generation.plan_pr_number is not None and (
        generation.plan_pr_body is not None
    ):
        return generation.plan_pr_number
    if generation.has_publication_context:
        return generation.published_pr_number
    return _payloads.as_identity(state.get(_PR_NUMBER))


def _may_be_held(
    gh: GitHubClient,
    issue: Issue,
    state: PinnedState,
    generation: LateGeneration,
    held_pr: _HeldPr,
) -> bool:
    """Whether THIS snapshot is a pull request this generation may mark.

    One answer for each way a target is named, and each is settled by the
    record that named it rather than derived a second time. A hold already
    taken is one this generation is entitled to keep: whether the description
    could be replaced was decided on the snapshot that WAS replaced, and
    re-asking would strand a "do not merge" notice on a pull request no retry
    would ever re-apply to and no release could put a body back on. A pull
    request the publication entry names is the one the candidate was measured
    against, which the gate proved open and froze. Anything else is whatever
    the issue currently records, and that has to be shown to be its plan.
    """
    if generation.plan_pr_number == held_pr.number and (
        generation.plan_pr_body is not None
    ):
        return True
    if generation.published_pr_number == held_pr.number and (
        generation.has_publication_context
    ):
        return True
    return _plan_provenance(gh, issue, state, held_pr)


def _release_hold(
    gh: GitHubClient, issue: Issue, generation: LateGeneration,
) -> _HeldPrHold:
    """Take this generation's hold off the PR it marked, if it still is.

    Which pull request is asked is the generation's own record, not whichever
    one the issue currently points at: the hold was taken on exactly the
    pull request `plan_pr_number` names, the body beside it is the only copy
    of the description that hold displaced, and a `pr_number` the issue has
    since been re-pointed at is a different change nothing here marked.

    Neither provenance nor the recorded head is re-asked. Provenance decided
    whether the description could be replaced, and it was decided on the
    snapshot that was replaced; asking again means a human pushing onto the
    branch while the adjudication ran would leave the "do not merge" notice
    standing forever on a pull request nothing is adjudicating any more. The
    head is that argument one field over: it says which change wore the
    notice, never whose the words under it are. What proves the current text
    is this generation's to overwrite is the marker in it, which is a fact
    about the body rather than about the head above it.

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
        return _HeldPrHold(generation=generation)
    held_pr = _readable_held_pr(gh, issue, pr_number)
    if held_pr is None:
        return _refused(generation)
    if not _wears_our_hold(generation, held_pr.body):
        log.info(
            "issue=#%d PR #%d does not carry this cycle's hold "
            "verbatim; leaving its description alone",
            issue.number, pr_number,
        )
        return _HeldPrHold(generation=generation)
    return _restored_body(gh, issue, generation, held_pr)


def _restored_body(
    gh: GitHubClient,
    issue: Issue,
    generation: LateGeneration,
    held_pr: _HeldPr,
) -> _HeldPrHold:
    """Write the preserved description back, and say whether it had to land.

    The reusability of the pull request is what decides that, and it is read
    off the same snapshot the edit is made against. A refused edit on an open
    one is a hold still standing on a change somebody can merge, so the caller
    parks; a refused edit on one already merged or closed is untidy and
    nothing more, so the accepted candidate goes on publishing.
    """
    reusable = held_pr.pr_state == _OPEN_PR_STATE
    try:
        gh.edit_pr_body(held_pr.pull_request, generation.plan_pr_body)
    except Exception:
        log.exception(
            "issue=#%d could not restore the description of PR #%d "
            "(state=%s)",
            issue.number, held_pr.number, held_pr.pr_state,
        )
        return _HeldPrHold(generation=generation, failed=reusable)
    return _HeldPrHold(generation=generation)


def _plan_provenance(
    gh: GitHubClient, issue: Issue, state: PinnedState, held_pr: _HeldPr,
) -> bool:
    """Whether THIS snapshot of the recorded pull request is the plan.

    The question only a target taken off `pr_number` has to answer. Read
    through the implementing stage's own answer rather than re-derived, so
    what counts as a plan is decided in one place: while the discussion's
    plan path stands nothing has pushed, and past that handoff the recorded
    plan commit is compared against the pull request's head.

    Asked about the snapshot the hold is holding, which is what removes the
    window between deciding and acting. It also removes the third answer that
    question can have: "could not ask" belongs to a fetch, and the fetch has
    already happened and already failed closed if it was going to.
    """
    is_plan = _implementing._recorded_pr_is_the_plan(
        gh, issue, state, held_pr.head_sha,
    )
    if not is_plan:
        log.info(
            "issue=#%d PR #%d is not this issue's plan; leaving its "
            "description alone",
            issue.number, held_pr.number,
        )
    return bool(is_plan)


def _reconciled_hold(
    gh: GitHubClient,
    issue: Issue,
    state: PinnedState,
    generation: LateGeneration,
    held_pr: _HeldPr,
) -> _HeldPrHold:
    """Decide what an open pull request needs: a retry, refusal, or hold.

    The middle one is the crash window the persist-first order leaves no room
    for: a body already carrying a hold that this issue preserved no original
    for was held by something else -- an older cycle, another binary -- and
    capturing it would record the hold text as somebody's description,
    destroying the only copy of it. A human settles that; this refuses it.
    """
    if (
        generation.plan_pr_number == held_pr.number
        and generation.plan_pr_body is not None
    ):
        _report_moved_head(issue, generation, held_pr)
        return _applied_hold(gh, issue, generation, held_pr)
    if _HOLD_PREFIX in held_pr.body:
        log.error(
            "issue=#%d PR #%d already carries a late hold this issue "
            "preserved no body for; refusing to overwrite it",
            issue.number, held_pr.number,
        )
        return _refused(generation)
    return _taken_hold(gh, issue, state, generation, held_pr)


def _report_moved_head(
    issue: Issue, generation: LateGeneration, held_pr: _HeldPr,
) -> None:
    """Say when the change under this hold is not the one it was taken on.

    Said and nothing more. What the notice is for is stopping a human from
    merging while an adjudication is open, and that is as true of a branch
    somebody has pushed to as of the one the hold was written over -- so the
    hold stands, the retry re-applies the same body it would have anyway, and
    the recorded head is left as the reading it was rather than being restamped
    to whatever the pull request has become. What movement costs is settled
    where the evidence is: the gate refuses to re-enter a publication over it,
    and the settlement refuses to publish or supersede against one that moved.

    Nothing is said for a hold recorded without a head. That can only be a
    record an older binary wrote -- a head this one cannot name refuses the
    capture rather than being recorded absent -- and the pull request under
    such a record has moved or not moved against a reading nobody took.
    """
    if not generation.plan_pr_head:
        return
    if generation.plan_pr_head == held_pr.head_sha:
        return
    log.info(
        "issue=#%d PR #%d has moved from %s to %s under this cycle's hold; "
        "the hold stands and the recorded reading is kept",
        issue.number, held_pr.number, generation.plan_pr_head,
        held_pr.head_sha or "an unreadable head",
    )


def _readable_held_pr(
    gh: GitHubClient, issue: Issue, pr_number: int,
) -> _HeldPr | None:
    """Read the pull request to hold, or None if GitHub could not be asked.

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
        return _read_held_pr(gh, pr_number)
    except Exception:
        log.exception(
            "issue=#%d could not read PR #%d for the late hold",
            issue.number, pr_number,
        )
        return None


def _read_held_pr(gh: GitHubClient, pr_number: int) -> _HeldPr:
    """Fetch one pull request and read every field a decision is made on.

    Every read is here so every read is inside the caller's guard. The head
    defaults to empty rather than raising on a shape without one, and text
    that is not a whole object id reads as empty too: a head nobody can name
    is not the plan commit either way, and it is not one this domain would
    record, since the pinned write and both sinks take a commit or nothing.
    What must not happen is the read itself escaping, so the shape is answered
    here and the refusal is made where the head is needed -- by the capture,
    which will not take a hold it cannot record a head for, and not by the
    release, which asks the body and never the head above it.
    """
    held_pr = gh.get_pr(pr_number)
    return _HeldPr(
        pull_request=held_pr,
        number=held_pr.number,
        body=held_pr.body or "",
        head_sha=_payloads.as_hex(
            getattr(held_pr.head, "sha", ""), _formats.COMMIT_LENGTHS,
        ) or "",
        pr_state=gh.pr_state(held_pr),
    )


def _taken_hold(
    gh: GitHubClient,
    issue: Issue,
    state: PinnedState,
    generation: LateGeneration,
    held_pr: _HeldPr,
) -> _HeldPrHold:
    """Record the identity, the head, and the body, then apply the hold.

    All three go down in one write, and the head goes with them because it is
    the only thing that says which change wore the notice: the same pull
    request stands on a different commit the moment somebody pushes, and a
    later tick reading only the identity could not tell the two apart. What is
    NOT written is the published head one field over -- the gate froze that
    one and a settlement pushes against it, so a hold that re-stamped it from
    its own reading would move the evidence under the verdict.

    A head this reading could not name refuses the hold before anything is
    touched, rather than being recorded as absent. The write drops an empty
    one, so the record it would leave is an identity and a body with no head
    between them -- a notice on a change no later tick could show it was
    written over -- and the description would already have been replaced by
    the time anything noticed. Two of three is not this record.

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
    if not held_pr.head_sha:
        log.error(
            "issue=#%d PR #%d names no head this reading could use; "
            "refusing to hold a description it could record no head for",
            issue.number, held_pr.number,
        )
        return _refused(generation)
    holding = replace(
        generation,
        plan_pr_number=held_pr.number,
        plan_pr_head=held_pr.head_sha,
        plan_pr_body=held_pr.body,
    )
    prospective = PinnedState(data=dict(state.data))
    _late_state.write_late_generation(prospective, holding)
    if not _late_session._holdable(prospective.data, holding):
        log.error(
            "issue=#%d cannot preserve the body of PR #%d and still "
            "record the run; refusing to hold it",
            issue.number, held_pr.number,
        )
        return _refused(generation)
    _late_state.write_late_generation(state, holding)
    try:
        gh.write_pinned_state(issue, state)
    except Exception:
        log.exception(
            "issue=#%d could not preserve the body of PR #%d; refusing "
            "to hold it", issue.number, held_pr.number,
        )
        return _refused(generation)
    return _applied_hold(gh, issue, holding, held_pr)


def _applied_hold(
    gh: GitHubClient,
    issue: Issue,
    generation: LateGeneration,
    held_pr: _HeldPr,
) -> _HeldPrHold:
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
    if held_pr.body == _hold_body(generation):
        return _HeldPrHold(generation=generation, held=True)
    if not _wears_our_hold(generation, held_pr.body) and (
        held_pr.body != generation.plan_pr_body
    ):
        log.warning(
            "issue=#%d PR #%d carries a description this issue did not "
            "displace; leaving it alone and reporting the hold displaced",
            issue.number, held_pr.number,
        )
        return _HeldPrHold(
            generation=generation,
            displaced=held_pr.pr_state == _OPEN_PR_STATE,
        )
    try:
        gh.edit_pr_body(held_pr.pull_request, _hold_body(generation))
    except Exception:
        log.exception(
            "issue=#%d could not hold PR #%d",
            issue.number, held_pr.number,
        )
        return _refused(generation)
    return _HeldPrHold(generation=generation, held=True)
