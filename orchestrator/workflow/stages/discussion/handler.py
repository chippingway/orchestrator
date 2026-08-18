# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""One `discussion` tick, in the order its questions have to be asked.

Whether the conversation is over comes first, and `terminal` is what answers
it. Once the humans have confirmed a design and this stage has published the
plan they confirmed, the issue is with them on a pull request, and what that
pull request has become is the whole of what a tick may do next: no round is
opened over the top of it and no agent is spawned, whether the plan merged,
was turned down, or is still being read. That gate reads the publication's own
record rather than the bare `pr_number`, since an issue relabeled here from a
PR stage arrives carrying its dev's -- and it answers for a closed issue too,
which is why it runs ahead of the publication recovery below it rather than
beside the parks.

A publication that started and did not finish comes next, ahead of the
turn-taking below it, because the answer that would otherwise carry a tick this
far is already spent: the write that records a publication in flight persists
what the round staged, the consumed reply included. An issue whose publication
crashed after that point is parked with nothing unread, so waiting for a reply
would mean waiting for a human to say the same thing twice.

Whose turn it is comes next, and a park THIS stage wrote is what settles it:
the round already posted is on the thread waiting for the humans to answer it
by number, so the tick has nothing to OPEN. What it has instead is a reply to
look for, and only a trusted comment past the consumed watermark makes it this
stage's turn again -- an untrusted one may neither steer the agent nor be
recorded as read, and no comment at all leaves the durable state exactly as the
park left it. A park any other stage wrote is not this stage's turn to wait on
-- pinned state outlives a relabel, so an issue an operator moves here from a
parked stage arrives awaiting a reply nobody will send it here, and reading
`awaiting_human` alone would leave it inert for good.

What the last round left comes next, and on an issue this stage has not parked
it is asked in three parts. A commit found against the anchor a round opened
with is settled now because the alternative is the next round adopting it as
its own baseline -- but whose it is, the anchor cannot say, so the same
open-round record that decides it under this stage's own park decides it here.
A round of this stage that never reached a disposition -- withheld by a mid-run
pause, or cut short -- gets its commit settled rather than parked: a commit
that is the agreed plan and nothing else is published from here exactly as it
would have been by the round that made it, so a crash between the commit and
its disposition costs a tick rather than the artifact. A tip that moved with no
round in flight is somebody else's -- an issue arrives here under another
stage's park still carrying this one's anchor and session -- and it is reported
instead, since publishing it would put a commit that stage's agent made onto a
plan PR under a conversation that never saw it. Then uncommitted work,
because preparing the checkout is destructive: `_ensure_worktree` would
recreate the tree over changes that are the only record of what an unfinished
run was doing. A tree that could not be READ counts with them, and for the
sharper version of the same reason: nothing has been established about it, and
the recreation behind this question does not wait to be told twice. It is asked
FIRST of the three, because the commit question is a comparison and this read
supplies one of its ends -- an unresolvable `HEAD` comes back empty, compares
unequal to every anchor, and would have the commit already on the branch
published as this stage's own.

A parked issue with a reply asks both of those too, and answers them
differently: it holds silently instead of parking. The park that left the tree
in that state already carries the paths and the reset command, so a second copy
of that message on every reply would bury the one an operator has to act on --
and the reply stays unconsumed, so it is still waiting the tick after they
reset. What runs there FIRST is the publication attempt, ahead of both, and for
a sharper reason than convenience: the reply into a failed push is the only
thing that ever resumes one, and the marker is the sole record of it that
survives a host losing the checkout and the local ref. Read locally that state
is indistinguishable from nothing having happened, so an issue whose plan is
already on the remote would open another round -- and the write that opens one
retires the marker. The same order also keeps a tick that died between opening
the plan PR and recording it from being answered with instructions to reset the
published commit away.

Everything else is the round and its disposition, in that order and nothing
after it. This stage never reaches a developer or a reviewer, and the one thing
it can publish is the plan the humans confirmed: the design is not settled until
they say so on the thread, so what a tick can produce is an analysis to reply
to, a park to reply into, or -- once -- the agreed plan on a PR. The worktree
the round ran in survives every one of those exits, because the tree the
discussion read is the tree the next round and the operator both look at. The
one thing that ever takes it down is the terminal above, and only once the
plan PR is gone: what the tree holds is what that pull request is open
against.
"""
from __future__ import annotations

from github.Issue import Issue

from orchestrator import config
from orchestrator.github.client import GitHubClient
from orchestrator.workflow.stages.discussion import models as _models
from orchestrator.workflow.stages.discussion import outcomes as _outcomes
from orchestrator.workflow.stages.discussion import parks as _parks
from orchestrator.workflow.stages.discussion import publication as _publication
from orchestrator.workflow.stages.discussion import run as _run
from orchestrator.workflow.stages.discussion import session as _session
from orchestrator.workflow.stages.discussion import state as _state
from orchestrator.workflow.stages.discussion import terminal as _terminal


def _run_discussion_round(
    run: _models._DiscussionRun, replies: list | None = None,
) -> None:
    """Open one round and publish whatever it turns out to have left."""
    round_result = _run._open_discussion_round(run, replies)
    outcome = _outcomes._assess_discussion_outcome(run, round_result)
    if outcome.park_reason is not None:
        _outcomes._route_discussion_outcome(run, round_result, outcome)


def _resume_parked_discussion(run: _models._DiscussionRun) -> None:
    """Answer the humans' reply to the parked round, or leave it parked.

    A tick nobody has answered is a no-op in the strict sense -- nothing
    spawned, nothing posted, no durable write -- so a parked discussion costs
    one comment read a tick and keeps waiting exactly as its park left it.
    """
    new_replies = _session._new_trusted_replies(run)
    if not new_replies:
        return
    if _hold_resume_for_repair(run, new_replies):
        return
    _run_discussion_round(run, new_replies)


def _hold_resume_for_repair(
    run: _models._DiscussionRun, replies: list,
) -> bool:
    """True when no round may open on this checkout as it stands.

    A publication this stage began is settled before anything local is read,
    because the marker is the only record of one that survives a host having
    lost the checkout AND the local ref. This is where a failed push is
    retried -- the recovery at the top of the tick steps around that park on
    purpose, so nothing else brings one here -- and "the push failed" is a claim
    about the request, not about the remote: the branch may well be published.
    Locally that state reads as nothing at all -- no tree, no branch, an anchor
    nothing has moved off -- so gating the settle on the anchor lets the reply
    open a round instead, and the write that opens one retires the marker. The
    plan is then on the remote with no PR, no record, and nothing left that
    knows to look for it.

    A commit is settled next: the branch may be carrying the agreed plan, in
    which case the reply publishes it rather than earning an answer. Everything
    else is said once and then held quietly. The park written here is itself a
    repair request, so the reply after it changes nothing on the thread -- and a
    park that ALREADY carried those instructions (this issue is sitting on the
    commit or dirty-tree park that reported the violation in the first place) is
    not repeated at all. Only a tree that went wrong under a clean park owes the
    humans an explanation, and without one they would answer the frontier and
    get silence.

    The reply survives every one of these paths but the push that takes it: no
    round opens, so nothing consumes it, and the park preserves the ceiling the
    last round read through. Repairing the tree -- or the push -- is the whole
    of what an operator has to do; the answer they already wrote is picked up on
    the next tick.
    """
    already_asked = _state._repair_already_requested(run.state)
    if _publication._settle_pending_publication(run, tuple(replies)):
        return True
    checkout = _checkout_reading(run)
    if checkout.moved:
        _settle_commit_under_park(run, already_asked=already_asked)
        return True
    if checkout.state.readable and not checkout.state.paths:
        return False
    if not already_asked:
        _parks._park_blocked_resume(run, checkout.state)
    return True


def _checkout_reading(run: _models._DiscussionRun) -> _models._CheckoutReading:
    """What the checkout is, and whether the round that opened on it moved it.

    One reading rather than two questions asked in either order, because the
    second is only answerable while the first says the checkout can be read at
    all -- and because both of its failures collapse to the same handling. A
    tree `git status` could not report on and a `HEAD` that would not resolve
    are each a checkout nothing has been established about, and what sits
    behind the moved question is a publication: empty compares unequal to every
    anchor there is, so an unread `HEAD` answers "a round committed here" and
    the commit the branch arrived carrying goes out under this stage's name.

    So the anchor is only asked of a readable tree, an unanswerable reading is
    reported as an unreadable checkout, and `moved` is never true on either.
    """
    state = _run._stranded_worktree_state(run)
    moved = _run._round_anchor_moved(run) if state.readable else None
    if moved is None:
        return _models._CheckoutReading(state=_run._UNREADABLE_TREE)
    return _models._CheckoutReading(state=state, moved=moved)


def _settle_commit_under_park(
    run: _models._DiscussionRun, *, already_asked: bool,
) -> None:
    """Settle a commit this stage owns, or report the one it merely found.

    A park normally means this stage's round is over, so what appeared on the
    branch afterwards was put there by something else -- and a design nobody
    argued out is not one to open a PR for on a human's next reply, least of
    all on a reply that rejects it. Two records say otherwise, and they are
    the two ways this stage can be mid-something under a park.

    A publication in flight is one of them, and by the time anything reaches
    here it has already answered for the branch either way: the caller asks it
    ahead of every local reading, since it is finished when the tip is still
    the commit it named -- one whose push failed and is being retried by this
    reply, or one whose PR was opened by a tick that died before recording it,
    where reporting a violation would tell an operator to reset away a plan a
    pull request may already be open against -- and refused when the tip is
    anything else, since a commit that turned up over an unfinished publication
    is no more this stage's than one that turned up over a park.

    An open round is the second record, and the one left to read here: a
    resumed round runs with the previous park still durable, so one that
    committed the agreed plan and was then paused or cut short is judged the
    same way `_settle_moved_checkout` judges the crash it recovers.
    """
    if _state._round_in_flight(run.state):
        _settle_recovered_commit(run)
        return
    if not already_asked:
        _parks._park_blocked_resume(run, _run._CLEAN_TREE)


def _settle_moved_checkout(run: _models._DiscussionRun) -> None:
    """Settle a checkout that has moved off the anchor, by who moved it.

    The anchor says only that the tip is not where this stage's last round
    opened it; it does not say whose commit is there. The open-round record is
    what says that, and it has to be read here as well as under a park, because
    "no discussion park" is not the same as "no park at all". Pinned state
    outlives a relabel: an issue can arrive here awaiting a human under
    ANOTHER stage's park, carrying this stage's anchor and session id from a
    conversation that finished, with that stage's own agent commit on the
    branch. Read as a round of this stage that never reported, a commit made
    there -- by a `question` agent that wrote the one path this stage
    publishes, say -- goes onto a plan PR under a session that never saw it.

    So the same ownership test applies to both: a commit is this stage's to
    publish when one of its rounds was in flight, and somebody else's
    otherwise. The flag is written durably before the spawn and cleared by
    every park, so it is true of exactly the rounds a crash or a mid-run pause
    left unreported -- which are the ones this recovery exists for.
    """
    if _state._round_in_flight(run.state):
        _settle_recovered_commit(run)
        return
    _parks._park_foreign_commit(run)


def _settle_recovered_commit(run: _models._DiscussionRun) -> None:
    """Publish or refuse the commit a round left with no disposition of its own.

    The round that made it was withheld mid-run or cut short before it could
    say what it had done, so this tick says it instead -- and it says the same
    thing that round would have: the agreed plan is published, and anything
    else parks with what the branch actually carries. Either way no new round
    opens over the top of the commit.
    """
    unpublishable = _publication._publish_plan_if_committed(run)
    if unpublishable is not None:
        _parks._park_recovered_commit(run, unpublishable)


def _handle_discussion(
    gh: GitHubClient, spec: config.RepoSpec, issue: Issue,
) -> None:
    """Open the discussion, answer the humans in it, or wait on them."""
    discussion_run = _models._DiscussionRun.start(gh, spec, issue)
    if _terminal._drain_discussion_terminals(discussion_run):
        return
    if _publication._finish_interrupted_publication(discussion_run):
        return
    if _state._parked_by_discussion(discussion_run.state):
        _resume_parked_discussion(discussion_run)
        return
    checkout = _checkout_reading(discussion_run)
    if checkout.moved:
        _settle_moved_checkout(discussion_run)
        return
    if not checkout.state.readable or checkout.state.paths:
        _parks._park_stranded_worktree(discussion_run, checkout.state)
        return
    _run_discussion_round(discussion_run)
