# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The three parks the size gate takes, answered before anything is spawned.

None of them is a park a human can talk their way out of, which is what puts
them together and what puts them in one owner. One is owed another READING --
a base the remote would not name, an object this host does not hold, a diff
nothing could pin -- and a trusted bare `/orchestrator continue` is the reply
that asks for it again. One is owed another LOOK at the checkout, which no
reply can supply and no agent can produce: what it waits for is the worktree
back on the commit the gate approved, and it says nothing until the answer
changes. And one is owed a DECISION nothing but a named command can be: an
adjudicated candidate with no operator authorization behind it, ended by the
`/orchestrator authorize-oversized <commit>` the park's notice spells out.

On all three the work in question is committed already, which is why they are
answered ahead of the spawn rather than inside it: the road below would buy a
second developer run for an implementation the first one finished, over a
branch that already carries it.

What each of them hands the answer to is the same publication seam the
committed work came out of, so a recovery reaches exactly the outcomes a fresh
disposition does -- the branch published, the candidate held, or the park
taken again with the reason it fails for now. None of them spawns anything,
and none of them decides for itself what the gate would have decided.

A checkout the seam would REFUSE is what stops a recovery before it, and what
that costs differs by what the park was waiting for. A reading can be asked
for again, so the measurement park lets the seam park under a reason of its
own and the next continue retries it. A DECISION cannot: the seam's reason
would take the authorization park's own off, and its notice would move the
watermark past the command still standing on the thread, so an operator who
fixed the checkout would be asked to authorize the same change a second time.
That road asks the seam's questions for itself first -- the worktree on this
host, its tree provably carrying nothing loose -- and holds exactly as found,
writing nothing, wherever the answer is no.
"""
from __future__ import annotations

import logging

from github.Issue import Issue

from orchestrator import config
from orchestrator.agents import AgentResult
from orchestrator.git.verification import probes as _verification_probes
from orchestrator.git.worktrees import paths as _worktree_paths
from orchestrator.github.client import GitHubClient
from orchestrator.github.comments import authored_by_us
from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.stages.implementing import (
    checkout_recovery as _checkout_recovery,
    disposition as _disposition,
    late_command as _late_command,
    late_consent as _late_consent,
    late_evidence as _late_evidence,
    late_parks as _late_parks,
    models as _models,
    session_read as _session_read,
    state as _state,
)

log = logging.getLogger("orchestrator.workflow")

_AUTHORIZATION_PARK = _late_command.PARK_UNAUTHORIZED_EXEMPTION

# What says who is waiting on this issue and for what, plus how far the thread
# they are waiting on has been read. The three travel together because a park
# put back without its watermark is one whose command has been consumed.
_PARK_FIELDS = (
    _state._AWAITING_HUMAN,
    _state._PARK_REASON,
    _state._LAST_ACTION_COMMENT_ID,
)

_AUTHORIZED_RECOVERY = (
    "(orchestrator recovery: publishing the candidate an operator authorized)"
)


def _try_recover_late_measurement_park(
    gh: GitHubClient, spec: config.RepoSpec, issue: Issue, state: PinnedState
) -> bool:
    """Re-measure a candidate a human has told the orchestrator to retry.

    The recovery a measurement park earns, and it is deliberately not a
    session retry. What failed was a READING -- a base the remote would not
    name, an object this host does not hold, a diff nothing could pin -- and
    the developer that produced the commit finished long ago, so paying for
    another run would buy a second answer to a question nobody asked. The bare
    `/orchestrator continue` is the operator saying the reading should be
    taken again; everything else on the thread is guidance, which the ordinary
    resume feeds to the developer.

    Returns True when the command was answered and the caller must return, and
    it answers every one of them: a command this reconciliation recognized is
    never handed back to the generic parked-continue classifier, which would
    refuse it as carrying no guidance -- the wrong thing to tell an operator
    whose command is exactly the right one, and a refusal that consumes their
    reply against a question nobody asked.

    The committed work goes back through the same publication seam it came out
    of, so the retry reaches the same three outcomes a fresh disposition does:
    the branch is published, the candidate is routed to adjudication, or the
    park is taken again with the reason it fails for now. A checkout that is
    gone is the fourth, and it is the one outcome the seam cannot reach on its
    own: there is no commit to read there, the recorded SHA is evidence no
    fresh checkout may stand in for, and re-running the developer would answer
    with different work -- so it parks saying exactly that, and the next
    continue retries it once the worktree is back.

    The park flags are cleared ahead of the publish, because clearing them is
    what the answer means -- and the retry re-takes the park itself if the
    reading is still not there. The comments are consumed in the same breath,
    which is safe only because every one of them is a bare continue: nothing
    with words in it is dropped here.
    """
    replies = _late_parks._answers_the_measurement_park(gh, issue, state)
    if not replies:
        return False
    state.set(
        _state._LAST_ACTION_COMMENT_ID,
        max(reply.id for reply in replies),
    )
    wt = _worktree_paths._worktree_path(spec, issue.number)
    if not wt.exists():
        _late_evidence._holds_missing_candidate(gh, spec, issue, state, wt)
        gh.write_pinned_state(issue, state)
        return True
    if _late_evidence._holds_moved_candidate(gh, spec, issue, state, wt):
        gh.write_pinned_state(issue, state)
        return True
    state.set(_state._AWAITING_HUMAN, False)
    state.set(_state._PARK_REASON, None)
    _, _, _, dev_sid = _session_read._read_dev_session(state)
    agent_result = AgentResult(
        session_id=dev_sid,
        last_message=(
            "(orchestrator recovery: re-measuring the committed candidate)"
        ),
        exit_code=0,
        timed_out=False,
        stdout="",
        stderr="",
    )
    _disposition._publish_committed_work(
        gh, spec, issue, state, _models._RecoveredWork(agent_result, wt),
    )
    gh.write_pinned_state(issue, state)
    return True


def _recovers_a_late_park(
    gh: GitHubClient, spec: config.RepoSpec, issue: Issue, state: PinnedState
) -> bool:
    """Every park the size gate takes, answered before anything is spawned.

    None of them is a park a human can talk their way out of, which is what
    puts them together and what puts them here. One is owed another READING,
    one another LOOK at the checkout, and one a DECISION nothing but a named
    command can be, and on all three the work in question is committed
    already -- so what they must never reach is the spawn below, which would
    buy a second developer run for an implementation the first one finished.
    """
    if _try_recover_late_measurement_park(gh, spec, issue, state):
        return True
    if _try_recover_unauthorized_exemption_park(gh, spec, issue, state):
        return True
    return _try_recover_moved_candidate_park(gh, spec, issue, state)


def _try_recover_unauthorized_exemption_park(
    gh: GitHubClient, spec: config.RepoSpec, issue: Issue, state: PinnedState
) -> bool:
    """Republish an adjudicated candidate an operator has now authorized.

    The way out of the park the size gate takes when a commit is exempt on a
    record no human stands behind. What it was missing was a person rather
    than a reading, so what settles it is the command they wrote -- and the
    work is committed already, so this must never reach the spawn below.

    The command is recognized here and acted on where the READING is, because
    that is where the terms of an authorization come from: an operator
    authorizes a change of this size against this ceiling, and only the owner
    that counts one can say either. So this owes the routing and nothing else
    -- the committed work goes back through the same publication seam it came
    out of, and the gate answer decides what happens, including the sentence a
    command naming another commit earns.

    A reply whose last word is not the command is left alone, and it is the
    ordinary resume that feeds it to the developer. Only the seams that
    publish onto a pull request the remote already carries reach the gate
    without passing a stage handler at all, and their own debt reconciliation
    is what brings this park back there.

    The park flags are deliberately NOT cleared here. The write that records
    the authorization is the write that takes them off, so a tick that could
    not fingerprint the pair leaves the issue exactly as parked as it found
    it, rather than durably unparking an issue nothing published.

    A checkout that is GONE is the one road that publishes nothing and it
    writes nothing either, which is what separates this park from the
    measurement one beside it. There the answer was a bare continue, spent by
    the tick that read it, so re-parking under a reason of its own costs
    nobody anything. Here the answer is a decision a human made about one
    commit: a fresh park would take this park's reason off, and its notice
    would move the watermark past the command that is still standing -- so an
    operator who put the worktree back would be asked to authorize the same
    change a second time, on an issue now waiting for a different reply
    entirely. Held silently instead, the park, the command and the record are
    all still there, and the poll after the checkout comes back publishes on
    them. It still owns the tick, because the road below would pay for a
    developer over an implementation that is committed already.
    """
    if _late_command._read_the_park(gh, issue, state) is None:
        return _answered_and_lost(gh, issue, state)
    wt = _worktree_paths._worktree_path(spec, issue.number)
    unpublishable = _unpublishable_checkout(wt)
    if unpublishable:
        log.info(
            "issue=#%d was authorized to publish its adjudicated candidate "
            "and its checkout %s; holding the park and the command as they "
            "stand rather than asking for the same decision twice",
            issue.number, unpublishable,
        )
        return True
    _publishes_under_the_park(gh, spec, issue, state, wt)
    return True


def _answered_and_lost(gh: GitHubClient, issue: Issue, state: PinnedState) -> bool:
    """Own a tick whose own refusal is the last word on the thread.

    The sentence a refused command earns is posted before the write that
    records posting it, so a tick dying between the two leaves that sentence
    on the thread with nothing on the comment saying it is ours: the ledger
    entry went down in the very write that was lost. Every reader past it
    treats what it cannot attribute as somebody's word -- rightly, since
    attributing on a body anybody can paste is how a retraction gets deleted
    -- so the reading finds a last word that is not the command, hands the
    tick back, and the ordinary resume spawns a developer against the
    orchestrator's own refusal.

    So the receipt is read HERE instead, where being ours decides only who
    owns the tick and never who authorized anything. It is scoped to this
    issue, and what it buys is exactly the write that was lost: the thread is
    consumed up to our sentence and the park is left standing, so the poll
    after it reads whatever a human has written since.

    Forged, it costs its own author the reply they wrote under it and leaves
    the park standing -- which is why it may answer this question and not the
    other one.
    """
    marker = _late_consent._REFUSED_MARKER_PREFIX.format(issue=issue.number)
    stamped = [
        seen
        for seen in gh.comments_after(
            issue,
            state.get(_state._LAST_ACTION_COMMENT_ID),
            state_comment_id=state.comment_id,
        )
        if marker in (getattr(seen, "body", "") or "")
    ]
    said = max(
        (
            int(getattr(seen, "id", 0) or 0)
            for seen in stamped
            if authored_by_us(seen, bot_login=getattr(gh, "_bot_login", None))
        ),
        default=0,
    )
    if not said:
        return False
    log.info(
        "issue=#%d carries this stage's own refusal in comment %d with no "
        "watermark behind it; recording the reading that tick lost rather "
        "than handing our own words to a developer",
        issue.number, said,
    )
    state.set(_state._LAST_ACTION_COMMENT_ID, said)
    gh.write_pinned_state(issue, state)
    return True


def _publishes_under_the_park(
    gh: GitHubClient,
    spec: config.RepoSpec,
    issue: Issue,
    state: PinnedState,
    wt,
) -> None:
    """Hand the committed work to the seam, and keep this park whatever it does.

    The seam refuses for reasons of its own -- a tree that stopped being
    provably clean between the reading above and its own, a candidate it could
    not measure -- and each refusal parks under a reason of its own and posts
    a notice that moves the watermark past whatever it finds. On every other
    road that is exactly right. Here it takes this park's reason off and
    consumes the command still standing, so an operator who fixes the checkout
    is asked to authorize the same commit again on an issue now waiting for a
    different reply.

    The questions above cannot close that on their own, because the sharpest
    of them is a RACE: the tree is read once here and again inside the seam,
    and everything between is time something can write in. So the park is put
    back rather than merely guarded -- whatever the seam refused for, and
    however it refused.

    Put back only where the seam left somebody waiting under another reason.
    A seam that PUBLISHED has ended this park deliberately and its record is
    the one that stands; a seam that took the park off entirely has done the
    same. What is restored is the pair that says who is waiting and for what,
    and the watermark, since a command consumed is a decision thrown away --
    the notice the seam posted stays on the thread, which is what tells the
    operator what to fix.
    """
    held = {key: state.get(key) for key in _PARK_FIELDS}
    _disposition._publish_committed_work(
        gh, spec, issue, state, _models._RecoveredWork(
            AgentResult(
                session_id=_session_read._read_dev_session(state)[-1],
                last_message=_AUTHORIZED_RECOVERY,
                exit_code=0,
                timed_out=False,
                stdout="",
                stderr="",
            ),
            wt,
        ),
    )
    reason = state.get(_state._PARK_REASON)
    if state.get(_state._AWAITING_HUMAN) and reason != _AUTHORIZATION_PARK:
        log.info(
            "issue=#%d had its authorization park replaced by the "
            "publication seam's own refusal (%s); putting the park and the "
            "command back so a decision already made is not asked for twice",
            issue.number, reason or "no reason at all",
        )
        state.data.update(held)
    gh.write_pinned_state(issue, state)


def _unpublishable_checkout(worktree) -> str:
    """Why an authorized candidate may not reach the seam yet, or "".

    Everything that seam would refuse, asked HERE instead -- and asked only on
    this road, because of what its refusal costs on this one. The seam parks
    under reasons of its own and the notice it posts moves the watermark past
    whatever it finds. On every other road that is exactly right. Here it
    would take this park's reason off and consume the command still standing
    on the thread, so an operator who fixed the checkout would be asked to
    authorize the same commit a second time, on an issue now waiting for a
    different reply entirely.

    Three answers under one rule: the checkout has to be on this host, and its
    tree has to be PROVABLY carrying nothing loose. A reading that established
    nothing is refused beside a tree that is dirty, since it is not evidence
    of a clean one -- and neither is anybody's decision, so both leave the
    park, the command and the record exactly as found, and the poll after an
    operator fixes either publishes on the command they already wrote.

    Everything the seam refuses PAST this reading is answered by the park
    being put back rather than by a wider question here: the tree is read
    again inside the seam, so no reading taken before it can promise what that
    one finds.
    """
    if not worktree.exists():
        return "is not on this host"
    tree = _verification_probes._worktree_status(worktree)
    if not tree.is_clean:
        return (
            "carries work no push would publish" if tree.readable
            else "has a tree this host could not read"
        )
    return ""


def _try_recover_moved_candidate_park(
    gh: GitHubClient, spec: config.RepoSpec, issue: Issue, state: PinnedState
) -> bool:
    """Republish an approved commit whose checkout has been put back.

    The way out of the one park a human cannot answer with words. What that
    park refused was the HANDOFF -- the commit was measured and approved, and
    the checkout it would have handed to review was somewhere else -- so what
    settles it is the checkout coming back, not guidance and not another
    developer run over work that is already committed.

    Which makes it quiet: the approved commit is recorded beside the park, so
    every tick asks one local question of the checkout and says nothing until
    the answer changes. An operator who restores the worktree sees the branch
    publish on the next poll without having to ask for it, and one who leaves
    it where it is is not told the same thing once a tick.

    What it hands on is the ordinary reconciliation, and the approval travels
    with it rather than being spent on the way. The record is the gate's own
    verdict about that exact commit, so the reconciliation republishes it
    under it -- named against it and not measured again -- and the publication
    that lands is what drops it. Spending it here instead would leave the
    reconciliation asking the size question about a settled commit, against a
    base that has moved since, and a park in the window between the two with
    nothing on the issue naming what it is waiting for.
    """
    if state.get(_state._PARK_REASON) != _state._CANDIDATE_MOVED:
        return False
    wt = _worktree_paths._worktree_path(spec, issue.number)
    if not wt.exists():
        return False
    if not _checkout_recovery._restored_checkout(issue, state, wt):
        return False
    state.set(_state._AWAITING_HUMAN, False)
    state.set(_state._PARK_REASON, None)
    _, _, _, dev_sid = _session_read._read_dev_session(state)
    agent_result = AgentResult(
        session_id=dev_sid,
        last_message=(
            "(orchestrator recovery: the approved commit is back in the "
            "checkout)"
        ),
        exit_code=0,
        timed_out=False,
        stdout="",
        stderr="",
    )
    _disposition._publish_committed_work(
        gh, spec, issue, state, _models._RecoveredWork(agent_result, wt),
    )
    gh.write_pinned_state(issue, state)
    return True
