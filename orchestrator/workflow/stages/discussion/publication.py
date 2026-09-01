# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Turning a confirmed design into a plan PR, and refusing everything else.

This is the one thing the stage publishes, and it is published from an
artifact rather than from a claim. The agent is told to write `plans/issue-N.md`
only after a human confirms on the thread that the two of them understand the
design the same way, and nothing here can check that a human said so -- what it
can check is what the branch now carries. So the check IS the contract: a tree
that could be read and is clean, a base-relative diff of exactly that one path,
and the plan itself present in HEAD. A missing plan, a deleted one, a second
one, a code or configuration change, anything left uncommitted beside it, or a
worktree that could not be inspected at all means the round did something other
than write down what was agreed -- or that nothing here can tell -- and none of
those is pushed.

`_plan_artifact` takes that reading once and hands it around whole, because the
same paths that decide are the paths the refusal quotes -- and because the tree
that was inspected has to be the tree that is pushed. It reads the checkout the
round ran in, restoring one only when the directory has gone: a dirty tree is
never recreated over, since it is the evidence the operator was parked to look
at.

The publication order is what makes the step re-runnable, and it opens with a
durable marker naming the tip about to be published. That write is what makes
the step ATTRIBUTABLE as well: everything after it can leave the world changed,
so a later tick finding this branch mid-publication knows the commit is one
this stage began publishing rather than one that merely looks like a plan.
Then the push, and a failed one parks without opening anything, so nothing
records a PR that does not exist. The PR is next and is reused if one is
already open on the branch, which is what a tick that died between `open_pr`
and the pinned write recovers through -- it re-derives the same artifact from
the same branch and finds its own PR rather than 422-ing on a duplicate. The
records are staged last and go down in one write, which is also what retires
the marker, so an issue never carries half a publication.

Which write that is depends on what the pull request is. An OPEN one is a
design still waiting on the humans, so the records ride the park that tells
them where to read it. One they have already DECIDED -- merged, or closed
without merging, which only the recovery ever adopts -- is not: telling
somebody to go and review what they have just settled would answer a verdict
with instructions, so there the records are persisted on their own and nothing
is said on the thread. `terminal` reads them on the next tick and finishes the
issue `done` or `rejected`, with the usage receipt and the teardown, which is
the whole of what is left to say.

Two of those records are not bookkeeping. `pr_number` and `branch` are what a
later checkout is restored from, and the round anchor is moved onto the
published tip because the implementing relabel guard measures the branch
against it: left at the tip the round opened on, the very commit this stage
just published would read as work nobody vouched for, and the operator moving
the issue on to be built would be told to reset it away.
"""
from __future__ import annotations

import logging
from pathlib import Path

from orchestrator.git import authentication as _authentication
from orchestrator.git.publication import (
    probes as _publication_probes,
    titles as _titles,
)
from orchestrator.git.verification import probes as _verification_probes
from orchestrator.git.worktrees import paths as _worktree_paths
from orchestrator.github import pull_requests as _pull_requests
from orchestrator.workflow.stages.discussion import models as _models
from orchestrator.workflow.stages.discussion import parks as _parks
from orchestrator.workflow.stages.discussion import run as _run
from orchestrator.workflow.stages.discussion import session as _session
from orchestrator.workflow.stages.discussion import state as _state

log = logging.getLogger("orchestrator.workflow")

_PR_OPENED_EVENT = "pr_opened"

# What `pr_state` calls a pull request still taking commits, and the state an
# already-carried publication is adopted rather than pushed to.
_OPEN_PR_STATE = "open"

# What `pr_state` calls a design the humans turned down. It is the one verdict
# a settle cannot act on the moment it sees it: an operator answering the stale
# park may close the stray pull request as part of the very reset that park
# asked for, so the close is only a verdict once the reset has been ruled out.
_CLOSED_PR_STATE = "closed"

# The states a lookup by commit narrows to: every verdict the humans can leave
# on a pull request, since to a publication a merge and a close are the same
# "nothing left to push here". Which of them the caller may act on, and when,
# is the caller's own -- see `_settled_plan_pr` and `_settle_moved_marker`.
_DECIDED_PR_STATES = frozenset((_CLOSED_PR_STATE, "merged"))


def _plan_artifact(run: _models._DiscussionRun) -> _models._PlanArtifact:
    """Read what the branch is carrying, in one pass, before anything moves.

    Every probe is taken, not just enough of them to reach a verdict, because
    the reading is also what the refusal quotes: an operator told only the
    first thing that was wrong would fix it and be refused again for the next.
    They are three different questions -- what is loose in the tree, what the
    commits change against base, and whether the plan is in the commit at all
    -- and a branch can pass any two of them and still not be a design anyone
    agreed to.

Whether HEAD is the BRANCH is read beside it, because what the push sends
    is a SHA and where it sends it is `refs/heads/<branch>`. A commit an agent
    made on a detached HEAD is a real commit in a real tree, and every other
    check here would pass it -- but the branch would still be where it was, so
    the ref this stage records, the ref the relabel guard measures, and the ref
    a lost checkout is rebuilt from would all be behind what the pull request
    carries. The reading is what refuses that rather than moving somebody
    else's ref to make it true.

    The tip is read once and then NAMED to the two commit-level probes rather
    than each re-reading `HEAD`. It is the commit this reading decides about
    and the commit the push publishes, and every `git` invocation between them
    is a moment the branch could move under: asked of `HEAD`, the checks could
    answer for one commit while the push sent another.

    The other end of that diff comes from pinned state, not from a ref. The
    round recorded what the remote said the base was before it spawned, and
    reading `<remote>/<base>` here instead would ask a local ref the agent's
    own worktree can move -- which is how a branch carrying a code commit and a
    plan commit could be made to look like a branch carrying only the plan.
    """
    branch = _worktree_paths._resolve_branch_name(
        run.state, run.spec, run.issue.number,
    )
    return _probe_plan_branch(run, branch, _plan_worktree(run, branch))


def _probe_plan_branch(
    run: _models._DiscussionRun, branch: str, worktree: Path,
) -> _models._PlanArtifact:
    """Take every probe the verdict and the refusal are both built from."""
    plan_path = _state._plan_path(run.issue.number)
    head_sha = _verification_probes._head_sha(worktree)
    base_sha = str(run.state.get(_state._BASE_SHA) or "")
    tree_status = _verification_probes._worktree_status(worktree)
    return _models._PlanArtifact(
        branch=branch,
        worktree=worktree,
        plan_path=plan_path,
        head_sha=head_sha,
        head_attached=_verification_probes._head_on_branch(worktree, branch),
        base_sha=base_sha,
        tree_readable=tree_status.readable,
        plan_in_head=_verification_probes._revision_contains_path(
            worktree, head_sha, plan_path,
        ),
        dirty_files=tree_status.paths,
        changed_paths=tuple(
            _verification_probes._committed_paths_since(
                worktree, base_sha, head_sha,
            ),
        ),
    )


def _plan_worktree(run: _models._DiscussionRun, branch: str) -> Path:
    """The checkout the artifact is read and pushed from, restored if gone.

    A checkout still on disk is taken exactly as it stands -- it is what the
    round wrote into, and recreating it is how a dirty tree that carries no
    commits gets destroyed. Only a directory that has gone is rebuilt, which
    is the same case a round opening on a pruned branch handles and goes
    through the same restorer: a commit can outlive its worktree on the local
    branch -- and, once it is pushed, both of them on the remote -- so the
    crash that took the directory must not also take the plan.
    """
    worktree = _worktree_paths._worktree_path(run.spec, run.issue.number)
    if worktree.exists():
        return worktree
    return _run._ensure_round_worktree(run, branch)


def _publish_plan_if_committed(
    run: _models._DiscussionRun,
) -> _models._PlanArtifact | None:
    """Publish the plan a round of this stage just committed, or refuse it.

    `None` means the tick is finished here: the plan is on a PR, or the push
    that would have put it there failed and said so. Anything else comes back
    as the artifact that was refused, because what "a commit on this branch"
    means depends on where it was found -- mid-disposition, or left behind by
    a round that never reported -- and the caller is the one that can say
    which.

    Both callers reach this with the commit already attributable and with no
    publication in flight: one is the round that made it reporting on itself,
    the other a tick finding the anchor of a round that opened and never
    disposed of what it did. An issue with a marker on it never gets here --
    `_settle_pending_publication` answers first, and answers for the branch
    whatever it finds there.
    """
    artifact = _plan_artifact(run)
    if not artifact.publishable:
        return artifact
    _publish_plan(run, artifact)
    return None


def _finish_interrupted_publication(run: _models._DiscussionRun) -> bool:
    """Settle a publication a tick died in the middle of, before anything else.

    It runs ahead of the turn-taking gate because the reply that would
    otherwise carry the tick there is already spent: the marker's write
    persists whatever the round staged, the consumed watermark included, so an
    issue whose publication crashed after that point is parked with no unread
    answer and would wait for a human to say something twice.

    A failed push is deliberately not resumed here. That park is a request to
    an operator, and retrying every tick would push at a remote already
    refusing us and comment each time it did; the reply to that park is what
    retries it, which is also the operator saying they fixed the reason.

    A retry already under way is a different state and resumes like any other:
    the write that begins one replaces that reason, precisely because it also
    spends the reply -- so what reaches here still carrying the failure is a
    publication nobody has taken up yet, and nothing else.
    """
    if run.state.get(_state._PARK_REASON) == _state._DISCUSSION_PUSH_FAILED:
        return False
    return _settle_pending_publication(run)


def _settle_pending_publication(
    run: _models._DiscussionRun, replies: tuple = (),
) -> bool:
    """Carry a publication THIS stage began to an ending, or answer False.

    False means there is no publication in flight and the caller's own reading
    of the branch is what applies. A marker, once set, answers for the branch
    itself -- it is finished when the tip is still the commit it named and that
    commit still validates, and refused otherwise.

    That tip is the whole of what this decides. Everything a MOVED one can mean
    -- a publication that merged elsewhere, a branch an operator reset, a
    second plan-shaped commit nobody here began -- is settled in
    `_settle_moved_marker` beside it.

    `replies` is the batch that drove this tick, and it is consumed by a push --
    only by a push. A retry that fails parks and would otherwise be asked for
    again by the same comment on the very next poll; a refusal leaves the answer
    where it is, since the reply is still waiting on a checkout the humans have
    to put back.
    """
    in_flight = run.state.get(_state._PUBLISHING_SHA)
    if not in_flight:
        return False
    artifact = _plan_artifact(run)
    if artifact.head_sha == str(in_flight) and artifact.publishable:
        _session._consume_replies(run, list(replies))
        _publish_plan(run, artifact)
        return True
    return _settle_moved_marker(run, artifact, str(in_flight))


def _settle_moved_marker(
    run: _models._DiscussionRun,
    artifact: _models._PlanArtifact,
    in_flight: str,
) -> bool:
    """Decide a marker whose tip is no longer the commit it names.

    Refused rather than declined, because the alternatives all publish
    something nobody proved: a tip that has moved is a second plan-shaped
    commit this stage never began publishing, and letting the readings below
    take it for a round's own work would credit a design to a conversation that
    never agreed to one.

    That refusal is written once. Its own reason is what the repeat reads, so
    an operator who restores the commit the marker names finds it published on
    the next tick, and one who does not is not told again every poll. A branch
    reset back to the round's anchor is the second answer: it carries nothing
    to publish, so the marker is spent rather than enforced, and the
    conversation is free to continue from the reply that has been waiting on it.

    A publication that MERGED is settled before either of those, and settled by
    recording rather than by publishing. The checkout it is read from can be
    one rebuilt at base -- the merge deletes the branch, so a host that lost the
    worktree and the local ref has nowhere else to rebuild from -- and that tip
    is neither the commit the marker names nor the round's anchor. Left to the
    readings below it is a branch somebody moved, and the issue parks on that
    forever with no `pr_number` and no plan path ever written, while the plan
    it is parked about is in the base branch. So the pull request itself is
    asked for by commit, and finding it finishes the publication the crash
    interrupted. An OPEN one the humans have pushed past is the same answer for
    the same reason, and is settled in the same place.

    That question is the one this cannot proceed without an answer to. Both
    readings under it act on the marker -- one spends it, the other refuses on
    it for good -- and each is a claim about whether the plan was published
    that a failed commit-list read cannot support.

    The reset reading is a claim about the REMOTE, though, and only the remote
    can make it. The push names the commit it sends rather than `HEAD`, so a
    plan committed on a detached head goes out while the local ref never moves,
    and a restore later prefers that local ref over the head it just fetched --
    so a publication that landed and a publication that was reset away look the
    same from here. Spent on that reading, the plan stays open on a pull
    request nobody recorded and the conversation opens another round over the
    top of it. So the marker is only spent once the branch the remote holds can
    be shown not to carry the commit it names.

    A pull request the humans CLOSED without merging is the one answer that
    waits for that reading rather than preceding it, because it is the only one
    the reset can also explain. An operator answering the stale park may well
    close the stray pull request while they are resetting the branch, and a
    close read as a verdict there would finish the issue on debris they were
    tidying. So it is taken up only once the reset has been ruled out -- the
    branch is not back at the anchor, or the remote still carries the commit --
    and then it IS the verdict: the plan is out there, the humans turned it
    down, and `terminal` finishes the issue `rejected` from the record this
    writes. Refused instead, the issue parks on a stale publication forever
    with no number, no label, no event, and no branch anything will reap, which
    is exactly what a reviewer who amends the plan and then closes it leaves
    behind.
    """
    landed = _settled_plan_pr(run, artifact, in_flight)
    if landed is _pull_requests.PR_LOOKUP_UNREADABLE:
        log.warning(
            "issue=#%s holding a publication in flight on %s: GitHub could "
            "not say whether it is already on a pull request",
            run.issue.number, in_flight,
        )
        return True
    if landed is not None and run.gh.pr_state(landed) != _CLOSED_PR_STATE:
        _record_landed_plan(run, artifact, landed)
        return True
    published = _publication_on_the_branch(run, artifact, in_flight)
    if not published and artifact.head_sha == str(
        run.state.get(_state._ROUND_SHA) or "",
    ):
        # The operator took the remedy and nothing of ours is on the remote to
        # outlive it: the branch is back at the tip the round opened on, so
        # there is no longer a commit to publish and the marker is spent.
        # Cleared rather than refused on, or the refusal would hold the
        # conversation shut against the reset it asked for -- and staged, so
        # whatever this tick writes next carries it.
        run.state.set(_state._PUBLISHING_SHA, None)
        return False
    if landed is not None:
        _record_landed_plan(run, artifact, landed)
        return True
    _refuse_stale_publication(run, artifact, in_flight, published)
    return True


def _publication_on_the_branch(
    run: _models._DiscussionRun,
    artifact: _models._PlanArtifact,
    in_flight: str,
) -> bool:
    """Whether the remote branch still carries the commit the marker names.

    Asked because a local reading cannot answer it. The commit may have been
    pushed from a checkout whose branch ref never moved -- the push sends the
    SHA it validated, not `HEAD` -- and it survives every local reset, every
    lost worktree, and every restore that comes back on the local ref instead
    of the fetched one. What is out there is what decides whether this stage
    may drop its record of a publication.

    True unless the remote can be SHOWN not to carry it, which is three
    different absences and one presence. A branch the remote does not have is
    the real absence: nothing of this stage's is published, and the marker is
    the caller's to spend -- the one way a deleted branch still means a
    published plan is a merge, and the caller has already recorded that pull
    request before anything reaches here. A tip equal to the commit itself needs nothing else
    asked. Any other tip is a branch that may have been moved past the plan --
    a human amending their own design on its pull request does exactly that --
    so what settles it is whether the commit is still in that branch's history,
    which is a local question about an id that came off the remote. A remote
    that could not be asked, or a tip nothing could bring into this store,
    establishes nothing and answers True: a record dropped on a reading nobody
    could take is a plan nothing goes looking for again.
    """
    remote_tip = _authentication._remote_branch_tip(
        run.spec, artifact.worktree, artifact.branch,
    )
    if remote_tip is None:
        return True
    if not remote_tip:
        # A branch that is gone with a merge behind it has already been
        # answered by the caller, which records that pull request rather than
        # asking this. What is left is a branch nothing merged took: a push
        # that never landed, or a pull request somebody closed and cleaned up
        # after. Neither leaves anything on the remote, which is the reset
        # standing.
        return False
    if remote_tip == in_flight:
        return True
    if not _readable_remote_tip(run, artifact, remote_tip):
        return True
    return _verification_probes._commit_contains(
        artifact.worktree, in_flight, remote_tip,
    )


def _readable_remote_tip(
    run: _models._DiscussionRun,
    artifact: _models._PlanArtifact,
    remote_tip: str,
) -> bool:
    """Make the remote's tip an object this checkout can be asked about.

    Every reading that judges a tip runs `_commit_contains`, which is a local
    command over local objects -- and the id it is handed is the remote's own
    answer about a branch this host may not have fetched since. A commit
    somebody pushed after this checkout was made is one git here cannot
    resolve, and an unresolvable id answers the same "no" a branch that really
    diverged does. That is the right answer for the caller about to overwrite a
    ref and the wrong one for the caller asking whether its own work is already
    out there: a publication whose pull request a human wrote on top of would
    be read as a divergence, refused for a commit nothing ever went to get, and
    parked again on every retry with the PR number still unrecorded.

    The fetch's exit status is deliberately not the answer, for the same reason
    the round's base read does not take it: a fetch that reported success
    without bringing this commit -- the branch moved again between the two
    commands, or was rewritten under them -- leaves the caller exactly where a
    failed one does, so the store is asked again either way. False means
    nothing about that tip can be established here, and each caller says what
    it does with that.
    """
    if _verification_probes._commit_present(artifact.worktree, remote_tip):
        return True
    _authentication._authed_target_fetch(run.spec, artifact.branch)
    return _verification_probes._commit_present(artifact.worktree, remote_tip)


def _plan_pr_by_commit(
    run: _models._DiscussionRun,
    artifact: _models._PlanArtifact,
    commit: str,
    wanted_states: frozenset,
):
    """The pull request carrying this commit, when it is in one of these states.

    Searched by commit and across every state, which is the pair of things
    `find_open_pr` cannot do. A tick that opened the plan PR and died before
    persisting its number leaves nothing pinned pointing at it, and by the time
    anything comes back a human may have merged it -- which closes the PR and,
    with auto-delete on, takes the head branch with it. Read as "no PR and no
    branch", the recovery pushes the branch back into existence and asks for a
    second pull request GitHub refuses for having no commits between the two
    refs; read as "nothing was published", it drops the marker and opens
    another round over a design that already merged.

    The commit is what makes an answer of any state safe to look at: a branch
    name outlives every pull request opened on it, so widening the search is
    only sound because the SHA narrows it back to the one this publication put
    there. Which states count is the CALLER's, and so is WHEN each of them may
    be acted on: `_settled_plan_pr` composes this into the one answer a
    publication has, and `_settle_moved_marker` holds one of that answer's
    verdicts back until it has ruled out an operator's reset.

    A lookup nobody could take is handed straight back rather than narrowed,
    because the narrowing is what would turn it into a "no": the pull request
    this exists to find has a moved head and possibly a deleted branch, so its
    commit list is the only place it is still visible, and one failed read of
    that list is enough to have the recovery republish over a design the humans
    already settled.
    """
    plan_pr = run.gh.find_pr_for_commit(
        branch=artifact.branch,
        base=run.spec.base_branch,
        head_sha=commit,
    )
    if plan_pr is _pull_requests.PR_LOOKUP_UNREADABLE:
        return plan_pr
    if plan_pr is None or run.gh.pr_state(plan_pr) not in wanted_states:
        return None
    return plan_pr


def _plan_pr_overtaken(
    run: _models._DiscussionRun, artifact: _models._PlanArtifact, commit: str,
):
    """An open pull request carrying this commit with newer work on top of it.

    The other way a publication is already finished. A tick that opened the PR
    and died before recording its number leaves a window a human can push into
    -- their own correction to the design, or the base merged in to make the PR
    mergeable -- and what they leave is a branch head that DESCENDS from the
    commit this publication put there. Nothing is left to push: the commit is
    on the branch, the pull request carries it, and the only thing a push could
    do is send the older SHA over their work.

    Which is exactly what the lease refuses, and refusing was never the
    problem: the problem is what a refusal leaves behind. Parked
    `discussion_push_failed` with no `pr_number` written, the issue sits on a
    pull request nothing recorded, and the reply that retries the publication
    finds the same newer head and refuses again -- a plan published, reviewable,
    and unreachable from the issue that produced it.

    Both readings are needed to say it, and neither alone: the remote head has
    to CONTAIN this commit (a tip that merely differs is somebody else's branch,
    and the divergence park is right about it), and a pull request has to carry
    it (a branch pushed past with no PR is a publication that never opened one).

    The containment half is only askable once that head is in this store. It is
    a commit made after this checkout was, so a retained worktree has never
    seen it, and git refuses an id it cannot resolve -- which would read their
    fast-forward as the divergence this is here to tell apart. A tip nothing
    can bring in is left to the lease below, which refuses the push and says
    what is there rather than adopting a pull request on a reading never taken.

    A pull-request lookup nobody could take is handed back as itself, for the
    same reason the merged one is: read as "no PR carries this", the branch is
    pushed and the reviewer's own commit goes under the older SHA.

    `commit` is named rather than taken off the artifact because the two
    callers hold it in different places. A checkout still on the published
    commit is asked about its own tip; a checkout REBUILT after the host lost
    it comes back on whatever the remote branch is at -- the reviewer's head,
    not ours -- and there the marker is the only record of what was published.
    Read off the artifact in that case, this asks whether their head descends
    from itself, answers no, and the plan the humans are looking at is refused
    for good.
    """
    remote_tip = _authentication._remote_branch_tip(
        run.spec, artifact.worktree, artifact.branch,
    )
    moved_past = (
        remote_tip
        and remote_tip != commit
        and _readable_remote_tip(run, artifact, remote_tip)
        and _verification_probes._commit_contains(
            artifact.worktree, commit, remote_tip,
        )
    )
    if not moved_past:
        return None
    plan_pr = run.gh.find_pr_for_commit(
        branch=artifact.branch,
        base=run.spec.base_branch,
        head_sha=commit,
    )
    if plan_pr is _pull_requests.PR_LOOKUP_UNREADABLE:
        return plan_pr
    if plan_pr is None or run.gh.pr_state(plan_pr) != _OPEN_PR_STATE:
        return None
    return plan_pr


def _settled_plan_pr(
    run: _models._DiscussionRun, artifact: _models._PlanArtifact, commit: str,
):
    """The pull request that leaves this commit nothing to publish, if any.

    Three ways one does, and all three are the humans having settled it
    somewhere this host cannot see. A MERGE took the branch with it and put the
    design in the base, so pushing would recreate a ref GitHub deleted and ask
    for a pull request with no commits between its two refs. A CLOSE without
    merging is the design turned down, so pushing would open a REPLACEMENT
    proposing it all over again -- with the issue then held on that replacement
    and their rejection left with nothing pointing at it. An OPEN one whose
    head they moved past this commit carries it already, so the only thing a
    push could send is the older SHA over their own work.

    Asked in that order because the first two are one lookup between them,
    while the open reading has to establish the remote tip and its ancestry
    first. `PR_LOOKUP_UNREADABLE` from either short-circuits the rest, since it
    is truthy and says the question could not be put at all.

    What a caller may DO with a close is not decided here, because it depends
    on where the branch is: `_settle_moved_marker` holds that one answer back
    until it has ruled out an operator's reset, since answering the stale park
    can mean closing the stray pull request as well as resetting the branch.
    """
    return _plan_pr_by_commit(
        run, artifact, commit, _DECIDED_PR_STATES,
    ) or _plan_pr_overtaken(run, artifact, commit)


def _refuse_stale_publication(
    run: _models._DiscussionRun,
    artifact: _models._PlanArtifact,
    in_flight: str,
    published: bool,
) -> None:
    """Say once that the publication in flight can no longer be finished."""
    if run.state.get(_state._PARK_REASON) == _state._DISCUSSION_STALE_PUBLISH:
        return
    _parks._park_stale_publication(run, artifact, in_flight, published)


def _publish_plan(
    run: _models._DiscussionRun, artifact: _models._PlanArtifact,
) -> None:
    """Record the attempt, push, open or reuse the PR, and record the result.

    The marker is written durably first because everything after it can leave
    the world changed: a tick that dies past this point has a tip a later one
    can recognize as its own. It costs one write per publication, which is
    once per issue, and it carries whatever the round staged beside it -- the
    records those staged values describe are the ones this call is about to
    make, so persisting them here rather than at the park is no loss.

    The rest is the re-runnable order: a failed push parks with nothing opened,
    and the PR is found before it is opened, so the window between the two
    writes leaves a PR the next tick adopts. What the humans do inside that
    window is asked FIRST, ahead of the marker: a pull request already carrying
    this commit -- merged, or open with their own work on top of it -- is a
    publication with nothing left to push, and pushing anyway would either
    recreate a branch a merge deleted or send the older SHA over what they
    wrote.

    What is pushed is the SHA the artifact was read at, never `HEAD`. The
    reading and the push are separate git invocations, and anything that moves
    the branch between them -- another tick, an operator, a stray agent --
    would otherwise publish a commit no check ever saw while the records named
    the one that passed.

    Nothing is pushed at all without a session to attribute it to. The body's
    whole job is to say which conversation produced this plan, and a recorded
    id is what makes that answerable: a round resuming one is pinned to it
    before it spawns, and a round opening one records what it opened. Neither
    holds when a backend hands no id back, or when a fresh round is cut short
    before it can say -- and a plan published under an unknown session is one
    a reviewer cannot trace to the discussion that agreed it.

    And nothing is pushed over a remote branch this publication cannot account
    for. The lease is pinned to the tip the remote was observed at rather than
    left to the push's own read, because the push's read would adopt whatever
    it found as the value it may overwrite -- so a retry of a publication that
    crashed would send its older validated commit straight over an update
    somebody made to the branch in between, and the reviewer's own commit would
    be gone with no record that it existed.

    That reading comes AFTER the marker, not before it, because its refusal is
    one an operator is expected to answer. The reply that answers it retries the
    publication, and the only thing that carries a reply there is the marker: an
    issue parked on this refusal without one has no publication in flight and no
    round open, and the park's own reason suppresses the repair request too --
    so the thread would go quiet and neither a push nor an agent would run
    again.

    A window nobody could see INTO is the third answer that question has, and
    it stops the publication where it stands. Read as "no pull request carries
    this", a failed commit-list read has the push recreate a branch a merge
    deleted and ask for a second pull request against a design already in the
    base -- and where the humans amended the plan before merging it, that
    second one proposes taking their amendment back out. So the marker is
    written and nothing else is: the tick that asks again is one poll away, and
    the write is what carries the round's own records there, since a round
    holding its session id only in memory would come back unattributable.
    """
    landed = _settled_plan_pr(run, artifact, artifact.head_sha)
    if landed is _pull_requests.PR_LOOKUP_UNREADABLE:
        _hold_unreadable_plan_pr(run, artifact)
        return
    if landed is not None:
        _record_landed_plan(run, artifact, landed)
        return
    if not _marked_publication(run, artifact):
        return
    lease = _permitted_lease(run, artifact)
    if lease is None:
        return
    pushed = _authentication._push_branch(
        run.spec,
        artifact.worktree,
        artifact.branch,
        force_with_lease=lease,
        revision=artifact.head_sha,
    )
    if not pushed:
        _parks._park_failed_plan_push(run, artifact)
        return
    plan_pr = _reuse_or_open_plan_pr(run, artifact)
    _record_published_plan(run, artifact, plan_pr.number)
    _parks._park_published_plan(run, artifact, plan_pr.number)


def _record_landed_plan(
    run: _models._DiscussionRun, artifact: _models._PlanArtifact, plan_pr,
) -> None:
    """Finish a publication whose pull request already carries the commit.

    Nothing is pushed and nothing is opened, because both would be wrong: what
    the push would send is on the branch already, and what the open would ask
    for exists. What is left to do is what the crash skipped -- writing down
    which PR the plan is on -- and the records that do it are the same ones a
    live publication ends with, so the issue comes out of this holding exactly
    what it would have held had the tick not died.

    A merge is one way in, and pushing there would recreate a ref GitHub
    deleted on purpose and ask for a pull request with no commits between its
    two refs. A close without merging is the second, and pushing there would
    ask the humans for a design they have just turned down -- on a REPLACEMENT
    pull request, leaving their rejection with nothing pointing at it. The
    third is an open pull request whose head a human moved past this commit
    while still carrying it, and pushing there would send the older SHA over
    their work.

    What the park says depends on which of them it was, because the park is
    what the humans read. An OPEN one is a design still waiting on them, and
    the message says where to review it and how to have it built. A DECIDED one
    is not: they merged or closed it already, and telling them to go and review
    it would be answering a verdict they have given with instructions they have
    no use for. So the records are written on their own there, and what speaks
    instead is `terminal` on the very next tick, which reads them and finishes
    the issue `done` or `rejected` with the usage receipt and the teardown.
    The open-round flag is retired by hand on that path, because the park
    funnel is what retires it everywhere else: a round whose plan is on a pull
    request has reported, and a flag left standing would have a later tick
    treat somebody else's commit as this round's.

    Nothing happens at all without a session to name, which is asked before
    the pull request is touched rather than after: this path reaches one
    ahead of the push's own refusal, so a plan nothing can attribute would
    otherwise be recorded as published here and never reach it.

    The body is then made to name that session, through the same check the
    ordinary reuse runs. What the lookup that found this pull request proves is
    only that it is on this branch, against this base, and carries this commit
    -- never that anything here opened it. A human can open one by hand on the
    branch the plan was pushed to, and merging it or writing on top of it puts
    it on exactly this path; recorded as the artifact, the plan would be
    reachable from the issue and described by a body about something else, or
    by no body at all. Naming the session is the whole reason the body exists,
    so an adoption is not finished until it does.

    One that already names it is left exactly as it stands, merged or not: it
    is this stage's own pull request, opened by the publication that crashed,
    and a design the humans have merged or written their own commit on top of
    is not one to rewrite back at them -- annotations and all.
    """
    if not _attributable_plan(run, artifact):
        return
    log.info(
        "issue=#%s plan %s is already on PR #%d (%s); recording it rather "
        "than publishing again", run.issue.number, artifact.plan_path,
        plan_pr.number, run.gh.pr_state(plan_pr),
    )
    _attribute_reused_pr(run, artifact, plan_pr)
    _record_published_plan(run, artifact, plan_pr.number)
    if run.gh.pr_state(plan_pr) == _OPEN_PR_STATE:
        _parks._park_published_plan(run, artifact, plan_pr.number)
        return
    run.state.set(_state._ROUND_OPEN, None)
    run.gh.write_pinned_state(run.issue, run.state)


def _marked_publication(
    run: _models._DiscussionRun, artifact: _models._PlanArtifact,
) -> bool:
    """Record the attempt durably, or refuse a plan with no session to name.

    The refusal comes first because it is the one an operator answers with a
    reset rather than a retry: the remedy is a fresh round under a session a
    reviewer can follow, so a marker left standing would have every reply
    republish the same unattributable commit and say so again.

    Everything past the write can leave the world changed -- the remote is
    asked, the branch is pushed, the PR is opened -- and the marker is what
    lets a later tick tell a commit this stage began publishing from one it
    merely found on the branch.

    The park reason goes with it, because a retry arrives here under
    `discussion_push_failed` and this write has already consumed the reply that
    asked for the retry. That reason is a request to an operator, so the
    recovery path refuses to resume a publication carrying it -- and with the
    reply spent, nothing else would either: a crash straight after this write
    would leave the plan waiting for a human to say the same thing twice. So the
    reason becomes what is actually true for the length of the attempt, and
    whichever way the attempt ends writes its own over it.

    A marker already standing on this exact tip, under that same reason, is
    this record and not a stale one, so the write is skipped. What that costs
    is nothing -- every ending of the attempt writes its own state anyway -- and
    what it saves is an edit of the pinned comment on every poll of a
    publication that is holding for a read GitHub keeps refusing. The reason is
    part of the test rather than decoration: a marker sitting under
    `discussion_push_failed` is a park an operator answered, and that write has
    to happen so the reply is spent.
    """
    if not _attributable_plan(run, artifact):
        return False
    marked = run.state.get(_state._PUBLISHING_SHA) == artifact.head_sha
    if marked and run.state.get(
        _state._PARK_REASON,
    ) == _state._DISCUSSION_PUBLISHING:
        return True
    run.state.set(_state._PUBLISHING_SHA, artifact.head_sha)
    run.state.set(_state._PARK_REASON, _state._DISCUSSION_PUBLISHING)
    run.gh.write_pinned_state(run.issue, run.state)
    return True


def _attributable_plan(
    run: _models._DiscussionRun, artifact: _models._PlanArtifact,
) -> bool:
    """True when there is a conversation to publish this plan under.

    The one question every path that touches a pull request has to answer
    first, because the answer is what the body says and what a reviewer
    follows back to the design being agreed. A round that opened a NEW
    conversation drops the previous pin before it spawns and records the id it
    opened only when it reports, so one cut short in between leaves a valid
    plan commit nothing here can name -- and every ending is wrong for it. The
    push would open a pull request under a placeholder; the ADOPTION of one
    already carrying the commit is worse, since that pull request need not be
    ours at all (the lookup proves branch, base and commit and nothing else),
    and it would be recorded as the published plan and rewritten to say
    `session None`.

    The refusal asks for the reset that makes a re-run possible, and it is
    written once. Its own reason is what the repeat reads, so an operator who
    has not answered yet is not told again on every poll -- which matters for
    the adoption in particular: that path is reached ahead of the turn-taking
    gate, by a marker the reply has not spent.
    """
    if _session._recorded_session_id(run.state) is not None:
        return True
    if run.state.get(
        _state._PARK_REASON,
    ) != _state._DISCUSSION_PLAN_UNATTRIBUTED:
        _parks._park_unattributed_plan(run, artifact)
    return False


def _hold_unreadable_plan_pr(
    run: _models._DiscussionRun, artifact: _models._PlanArtifact,
) -> None:
    """Stop a publication that cannot be told from one already finished.

    Nothing is pushed, nothing is opened, and nothing is said on the thread:
    a commit list GitHub declined to serve is a transient failure, and a park
    would put a request to a human on an issue whose only problem is that one
    read has to be taken again. The tick after this one takes it.

    The marker is written all the same, and it is the whole point of stopping
    here rather than simply returning. It is what a later tick recognizes this
    tip by, and its write is what persists whatever the round staged -- the
    session id above all, which a fresh round holds only in memory until
    something writes: lost, the retry finds a valid plan it cannot attribute
    and refuses it as unpublishable.
    """
    log.warning(
        "issue=#%s holding the publication of %s: GitHub could not say "
        "whether %s is already on a pull request for %s",
        run.issue.number, artifact.plan_path, artifact.head_sha,
        artifact.branch,
    )
    _marked_publication(run, artifact)


def _permitted_lease(
    run: _models._DiscussionRun, artifact: _models._PlanArtifact,
) -> str | None:
    """What this push may overwrite on the remote, or None having said why not.

    The tip it returns becomes the push's lease, which is what makes the answer
    hold: the check and the push are two commands, and a lease pinned to the
    tip that was checked refuses if anything moves the branch between them.
    Left to the push's own read, the lease would be whatever the remote had
    become -- the exact value that lets a retry overwrite it.

    What makes a tip publishable is not which record names it but whether this
    commit CONTAINS it. A branch the remote does not have yet is the ordinary
    first publication and there is nothing to contain. Otherwise the commit
    being published has to descend from what is there, which is true of a
    publication being replayed after a crash (the tip is the commit itself) and
    of an inherited PR branch a discussion was held on top of (the plan sits on
    that tip). A lease cannot stand in for that: it proves only that the ref has
    not moved since it was read, not that what is on it survives the push -- so
    an agent that reset an inherited branch to base and committed the plan there
    would pass every other check and delete the PR's history.

    Answering that takes the tip itself and not merely its id, so the fetch is
    part of the question here as well as above it. An id git cannot resolve is
    refused as a divergence, and a tip that is only unfetched is the ordinary
    state of a branch somebody else has pushed to -- so a branch this commit
    really does descend from would otherwise park on a reading never taken.

    Anything else parks and says what is there: a human amending the plan on its
    PR, a stray push, a rewritten remote, or a tip nothing could bring here.
    """
    remote_tip = _authentication._remote_branch_tip(
        run.spec, artifact.worktree, artifact.branch,
    )
    if remote_tip is None:
        _parks._park_diverged_plan_branch(run, artifact, remote_tip)
        return None
    if not remote_tip:
        return remote_tip
    if _readable_remote_tip(
        run, artifact, remote_tip,
    ) and _verification_probes._commit_contains(
        artifact.worktree, remote_tip, artifact.head_sha,
    ):
        return remote_tip
    _parks._park_diverged_plan_branch(run, artifact, remote_tip)
    return None


def _reuse_or_open_plan_pr(
    run: _models._DiscussionRun, artifact: _models._PlanArtifact,
):
    """Return the plan's PR, reusing the open one a prior tick left behind.

    A tick that died between opening the PR and writing its records left the
    PR up and nothing pointing at it, and the next tick re-derives the same
    publishable artifact from the same branch. Asking for the open PR first is
    what turns that replay into a reuse instead of a duplicate -- and why the
    `pr_opened` event is emitted only on the branch that really opened one, so
    a recovered publication is not counted twice.

    What comes back is only guaranteed to be open on this branch, not to be
    the one a previous tick of this stage opened, so the reuse fixes up the
    body rather than trusting it.
    """
    plan_pr = run.gh.find_open_pr(
        branch=artifact.branch, base=run.spec.base_branch,
    )
    if plan_pr is not None:
        log.info(
            "issue=#%s reusing existing plan PR #%d for %s",
            run.issue.number, plan_pr.number, artifact.branch,
        )
        _attribute_reused_pr(run, artifact, plan_pr)
        return plan_pr
    plan_pr = run.gh.open_pr(
        branch=artifact.branch,
        base=run.spec.base_branch,
        title=_plan_pr_title(run, artifact),
        body=_plan_pr_body(run, artifact),
    )
    run.gh.emit_event(
        _PR_OPENED_EVENT,
        issue_number=run.issue.number,
        stage=_state._DISCUSSION_STAGE,
        pr_number=plan_pr.number,
        branch=artifact.branch,
        sha=artifact.head_sha or None,
    )
    return plan_pr


def _attribute_reused_pr(
    run: _models._DiscussionRun, artifact: _models._PlanArtifact, plan_pr,
) -> None:
    """Make a reused PR say which session's plan it is now carrying.

    A PR open on this branch is not necessarily one of ours: it can be a PR an
    issue arrived here with, or one an operator opened by hand, and adopting
    it silently would leave the published plan described by a body about
    something else. The named session is the whole point of the body -- it is
    what lets a reviewer find the conversation the plan came out of -- so its
    absence is what triggers the rewrite, and its presence leaves whatever
    else the body says alone, including a human's own additions to ours.
    """
    if _plan_pr_attribution(run) in (plan_pr.body or ""):
        return
    log.info(
        "issue=#%s rewriting reused plan PR #%d body to name this stage",
        run.issue.number, plan_pr.number,
    )
    run.gh.edit_pr_body(plan_pr, _plan_pr_body(run, artifact))


def _plan_pr_title(
    run: _models._DiscussionRun, artifact: _models._PlanArtifact,
) -> str:
    """Title the plan PR the way a dev PR is titled: from its own commit.

    The agent wrote the plan and its subject in the repository's own style, so
    reusing that subject makes the PR read like the repository it lands in.
    The issue title and the prefix inferred from recent base history are the
    same two fallbacks every other PR here falls to.
    """
    first_subject = _publication_probes._first_commit_subject(
        run.spec, artifact.worktree,
    )
    fallback_prefix = _titles._infer_subject_prefix(
        run.spec, artifact.worktree, run.issue,
    )
    return _titles._pr_title_from_commit_or_issue(
        run.issue, first_subject, fallback_prefix,
    )


def _plan_pr_attribution(run: _models._DiscussionRun) -> str:
    """Name the session whose plan a PR carries.

    Read from the identity the conversation is pinned to rather than from the
    current config, for the same reason every round is: a `DECOMPOSE_AGENT`
    flip must not re-attribute what already ran. It is its own line because
    two owners need it -- the body that states it, and the reuse that checks
    a PR of unknown provenance for it before adopting that PR as the plan's.

    The id is always there to name: a publication with none is refused before
    it reaches here, rather than published under a placeholder no reviewer
    could follow.
    """
    session = _session._locked_discussion_session(run.state)
    return (
        f"Generated by orchestrator ({session.backend} session "
        f"`{session.session_id}`) in the `discussion` stage."
    )


def _plan_pr_body(
    run: _models._DiscussionRun, artifact: _models._PlanArtifact,
) -> str:
    """Say what the PR is, which session wrote it, and what deciding it does.

    What a decision on it MEANS is the part a reviewer cannot infer from the
    diff: this pull request is the design being agreed, so taking it finishes
    the issue rather than starting anything, and having the plan built is a
    relabel made BEFORE either button is pressed. This body is the only thing
    that reaches the person about to press one.

    No closing keyword appears anywhere in it all the same, and that is not a
    contradiction. What a merge meant is this stage's to record -- the stamp,
    the usage receipt, the event, and the teardown all ride the terminal it
    drains -- and `Resolves #N` would have GitHub close the issue with none of
    it written. The keyword also outlives the label it was written under: a
    relabel to `workflow:implementing` hands the developer this very pull
    request, and a closing keyword there would let a merge of the plan alone
    close the issue as finished work -- the exact reading `discussion_plan_path`
    exists to refuse.
    """
    issue_number = run.issue.number
    plan_summary = (
        "The resolved decisions, the evidence behind them, the alternatives "
        "considered, the risks, and the implementation plan are in "
        f"`{artifact.plan_path}`; this branch changes nothing else, and no "
        "implementation starts from here. Merging it is agreeing to the "
        f"design: the orchestrator finishes #{issue_number} as `done`, closes "
        "it, and removes the branch this pull request was opened from. "
        "Closing this pull request unmerged finishes the issue as `rejected` "
        f"the same way. To have the plan BUILT instead, relabel #{issue_number} "
        "`workflow:implementing` before doing either."
    )
    return "\n".join((
        f"Plan for #{issue_number}, as agreed on the issue thread.",
        "",
        _plan_pr_attribution(run),
        "",
        plan_summary,
    ))


def _record_published_plan(
    run: _models._DiscussionRun,
    artifact: _models._PlanArtifact,
    pr_number: int,
) -> None:
    """Stage what was published, where it lives, and what certifies it.

    All four land in one durable write -- the park's where the pull request is
    still open, and the caller's own where it has already been decided and
    there is nothing to say on the thread -- so an issue is never left carrying
    a PR number without the branch it is open against or a plan path without
    the PR that reviews it.

    The anchor is the load-bearing one. It records the branch and the tip this
    stage vouches for, and moving it onto the published commit is what lets
    the operator relabel the issue to be built: the implementing guard reads
    the branch against that SHA, and an anchor still pointing at the tip the
    round opened on would convict the branch of the very commit this
    publication just put on a PR -- and offer, as the remedy, resetting it
    away.

    The commit that PR carries is recorded beside its number, because the
    number alone does not say what is on it. The implementing stage reads that
    SHA against the PR's head to know whether a merge there is a human agreeing
    to a design or work finishing, and asking GitHub is what makes the answer
    right even when a tick pushed onto this PR and died before recording it.
    Until that stage retires the path record above, the path is what answers:
    the humans may amend their own plan on its PR, and a head they moved is not
    an implementation to close the issue on.

    The in-flight marker is retired in the same write, because what it was
    there to say -- somebody has to finish this -- is exactly what these
    records now answer.
    """
    run.state.set(_state._PLAN_PATH, artifact.plan_path)
    run.state.set(_state._BRANCH, artifact.branch)
    run.state.set(_state._PR_NUMBER, pr_number)
    run.state.set(_state._PLAN_SHA, artifact.head_sha)
    run.state.set(_state._ROUND_BRANCH, artifact.branch)
    run.state.set(_state._ROUND_SHA, artifact.head_sha)
    run.state.set(_state._PUBLISHING_SHA, None)
    log.info(
        "issue=#%s published plan %s as PR #%d on %s",
        run.issue.number, artifact.plan_path, pr_number, artifact.branch,
    )
