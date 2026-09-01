# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Why a conversation stage's park is checked before an implementing relabel is trusted.

The `question` and `discussion` stages both park with `awaiting_human=True` and
a stage-prefixed reason so their own next tick can pick the conversation back
up. Implementing's resume path cannot read those flags -- they mean nothing to
it -- so a relabel out of either stage has to clear them or refuse, and the two
are handled here together because the hazard is the same: what either agent may
write is narrow and neither stage ships it as dev work. The question agent may
write nothing at all. The discussion agent may commit one file, the plan its
humans confirmed, and only its own stage publishes that -- through a check of
what the branch carries, and onto a PR of the plan alone. Anything else either
of them leaves behind is for an operator to look at, never for this stage to
push.

Which one happens is decided by the worktree and the branch, never by the park
reason alone. A misbehaving run can park having committed or dirtied the
per-issue branch, and dropping the park would let the fresh-spawn path's
recovered-worktree shortcut push that work as a dev implementation. The branch
is checked even when the worktree is gone, because a safe teardown (or an
operator) can remove the directory while the local branch survives carrying
those commits -- `_ensure_worktree` would restore it and the shortcut would
ship them.

The checkout is read for its own HEAD for the mirror-image reason. A commit does
not have to be on a branch anybody here names: an agent that committed while
detached leaves every ref where it was and the plan sitting in the tree, which
is exactly what the creators keep and the shortcut pushes. So the branch reads
answer for the refs and the HEAD read answers for the checkout, and an
unreadable HEAD counts against it -- proving a tree carries nothing cannot rest
on a probe that did not run.

"Ahead of base" is the question for a question-stage park, whose own contract
already refuses to finish a round on a branch carrying anything. The discussion
stage tolerates the commits an issue arrives with, so the same question would
convict it of its dev's work and strand an issue no operator could unstick;
what is asked there instead is whether the branch still sits at the SHA the
last round recorded opening on. That anchor is written before the spawn and
survives every park the stage takes -- including the ones that found a commit,
which quote it as the tip to reset back to -- so it is the branch's position
against it, not the anchor's presence, that says whether the stage vouches for
what is there. A published plan passes for the same reason it should: that
stage moves the anchor onto the commit it put on a PR, so the tip and the
record agree and the relabel is the humans moving on from a design they have.

A refusal re-parks as `<stage>_unsafe_relabel` and is idempotent, so repeated
ticks stay silent until an operator resets the worktree or deletes the branch.
A clean pair means the relabel IS the unblock signal: the flags are dropped and
`last_action_comment_id` is ratcheted past what that agent posted, or
the later validating -> in_review seed would replay it as fresh PR feedback.
The anchor is retired here rather than discarded -- it becomes
`read_only_baseline_sha`, the floor the dev run that follows is measured
against, since the branch it inherits is already ahead of base.

A published plan asks the guard one more question, because between the
publication and the relabel the humans have had that design on a PR: they can
correct the Markdown on it, or merge the base into its branch to make it
mergeable, and either leaves the PR on a head this orchestrator never wrote. So
the PR is read before anything is ruled on, and what it carries now is used
twice. The checkout is brought forward onto it -- a developer handed the commit
we published would build on a design its reviewers have moved past, and push a
tip that does not contain the head they approved. And that head replaces
`discussion_plan_sha` in the very write that retires `discussion_plan_path`,
because the path record is what answered the merged-PR question until now: a
later tick with the path gone and the old commit still recorded would read the
humans' own edit as this stage's work and close the issue as `done` with no
developer having run. The baseline then names where the branch really ended up,
which is the anchor again whenever that head could not be fetched at all.

Reading GitHub before the guard rules is also what makes the move crash-safe.
The branch is anchored ahead of the write that records it, so a tick that dies
in between leaves a tip past the anchor -- and the next one, holding the same
reviewed head, recognizes that tip as certified rather than convicting the
branch of it. A read that fails ends the tick where it happened, writing
nothing, since every decision behind it is durable.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from github.Issue import Issue

from orchestrator import config
from orchestrator.git.verification import probes as _verification_probes
from orchestrator.git.worktrees import (
    creation as _worktree_creation,
    paths as _worktree_paths,
    recovery as _worktree_recovery,
)
from orchestrator.github.client import GitHubClient
from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.engine import guards as _guards
from orchestrator.workflow.stages.discussion.state import (
    _PLAN_PATH,
    _PLAN_SHA,
    _PR_NUMBER,
    _PUBLISHING_SHA,
    _ROUND_BRANCH,
    _ROUND_OPEN,
    _ROUND_SHA,
    _plan_published,
)
from orchestrator.workflow.stages.implementing import state as _state
from orchestrator.workflow.state import WorkflowLabel

log = logging.getLogger("orchestrator.workflow")

# The stages whose parks this guard answers for, named by the prefix their
# reasons carry in pinned state. Both are operator-applied conversation
# labels neither of which produces dev work, so an issue can arrive at
# implementing from either one by a human relabel.
_READ_ONLY_PARK_STAGES: tuple[str, ...] = (
    str(WorkflowLabel.QUESTION), str(WorkflowLabel.DISCUSSION),
)

_UNSAFE_RELABEL_SUFFIX = "_unsafe_relabel"

# What `pr_state` calls a pull request whose head landed on the base branch.
_MERGED_PR_STATE = "merged"


def _parked_read_only_stage(state: PinnedState) -> str | None:
    """Return the conversation stage whose unfinished work this issue carries.

    A park is the ordinary form of it, and the flags are what say so. An
    unfinished ROUND is the other form, and it says so with no flags at all: an
    opening round leaves the issue unparked by design, and a publication's
    marker is written from the disposition of one. So a discussion tick that
    died mid-round -- after the agent committed, or after its plan PR was
    opened -- leaves an issue with `awaiting_human` false and a branch carrying
    the very commits this guard exists to keep out of a dev push.
    """
    if _discussion_in_flight(state):
        return str(WorkflowLabel.DISCUSSION)
    if not state.get(_state._AWAITING_HUMAN):
        return None
    park_reason = state.get(_state._PARK_REASON)
    if not isinstance(park_reason, str):
        return None
    for stage in _READ_ONLY_PARK_STAGES:
        if park_reason.startswith(f"{stage}_"):
            return stage
    return None


def _discussion_in_flight(state: PinnedState) -> bool:
    """True while a discussion round or publication is unfinished here.

    Both records are written BEFORE the thing they describe and retired by the
    disposition that reports it, so an issue still carrying one is an issue
    whose last discussion tick did not get that far. Neither depends on
    `awaiting_human`, which is why reading the park alone lets exactly the
    crashed rounds through -- the ones whose commit is sitting on the branch
    with nothing published, nothing reported, and no park to find it by.
    """
    return bool(state.get(_ROUND_OPEN)) or bool(state.get(_PUBLISHING_SHA))


def _handle_stale_read_only_park(
    gh: GitHubClient, spec: config.RepoSpec, issue: Issue, state: PinnedState
) -> bool:
    """Clear a stale conversation-stage park left by a relabel to
    `implementing`, or refuse the relabel when it would ship what that stage's
    agent wrote.

    `_handle_question` and `_handle_discussion` park with `awaiting_human=True`
    and `park_reason="<stage>_*"` so their own next tick can pick the
    conversation back up; those flags are opaque to implementing's resume path
    and would mis-fire it. When no such park is present this is a no-op
    returning False.

    The clear must check the actual worktree, NOT just the park reason. Both
    agents write nothing a human has not asked for, but a misbehaving run can
    park as `question_commits` / `discussion_plan_invalid` / `*_dirty` (or a
    `*_timeout` that committed before being killed) with unreviewed code state
    on the per-issue branch. Silently dropping the park would let the fresh-spawn
    branch's recovered-worktree shortcut (`_has_new_commits` -> push) publish
    those commits as if a dev session had authored them -- work no human
    confirmed and no check of the stage that produced it ever passed.

    Returns True when the caller must return this tick: the unsafe relabel was
    re-parked as `<stage>_unsafe_relabel` and pinned state written here. The
    branch check covers the case where the worktree was removed (a safe
    question teardown ran, or the operator deleted the dir) but the local
    `orchestrator/<slug>/issue-N` branch survived with the agent's commits:
    `_ensure_worktree` would otherwise silently restore it and the
    recovered-worktree shortcut would ship those commits as a dev PR. The
    re-park is idempotent -- once `park_reason` is already
    `<stage>_unsafe_relabel`, subsequent ticks stay silent until the state is
    cleaned or the operator relabels elsewhere.

    Returns False otherwise: either no conversation-stage park is present, or the
    worktree and branch are both clean so the relabel IS the unblock signal --
    the park flags are dropped and `last_action_comment_id` ratcheted past the
    agent's last comment (so the eventual validating->in_review watermark seed
    cannot replay it as fresh PR feedback) before the caller falls through to
    the fresh-spawn path.

    It also returns True, writing nothing at all, when the plan PR this issue
    records could not be read, or when what it carries could not be put on the
    branch. What that PR is on decides both what the developer inherits and what
    the write below records in place of the path record it retires, and guessing
    either is worse than waiting: the next tick asks again from the same durable
    state. Accepting the handoff on a checkout still sitting behind the reviewed
    head is the case that costs something -- the developer would build on a
    design its reviewers replaced, and the ordinary push that followed would
    read their head off the remote as its own lease and overwrite it.
    """
    stage = _parked_read_only_stage(state)
    if stage is None:
        return False
    reviewed = _reviewed_plan(gh, issue, state)
    if reviewed is None:
        return True
    hazard = _read_only_relabel_hazard(spec, issue, state, reviewed)
    if hazard is not None:
        unsafe_reason = f"{stage}{_UNSAFE_RELABEL_SUFFIX}"
        if state.get(_state._PARK_REASON) != unsafe_reason:
            _park_unsafe_read_only_relabel(
                gh, issue, state, stage, hazard,
            )
        gh.write_pinned_state(issue, state)
        return True
    inherited = _inherited_tip(spec, issue, state, reviewed)
    if inherited.pending:
        return True
    _clear_stale_read_only_park(gh, issue, state, reviewed.head, inherited.sha)
    # Written HERE, before the caller reaches the spawn, because accepting the
    # handoff is a durable fact and not a staged one. The tick after it can end
    # without writing pinned state at all -- a mid-run pause or a shutdown
    # interruption drops every staged mutation on purpose -- and if this went
    # with them the next tick would read the park and anchor back, find the
    # dev's commit sitting past that anchor, and convict the developer of a
    # violation it would then ask the operator to reset away.
    gh.write_pinned_state(issue, state)
    return False


@dataclass(frozen=True)
class _ReviewedPlan:
    """What GitHub says this issue's plan PR is, right now.

    `head` is the commit it carries -- the design as its reviewers left it --
    and `merged` says that design landed. The second changes where the
    developer starts: a merged plan is in the base along with everything else
    that has landed since, and the branch it was open against may not even
    exist any more, so the base is the tip to build from rather than the commit
    that merged.

    An issue with no published plan carries neither, which is every
    question-stage park and every discussion that never got as far as an
    artifact.
    """

    head: str = ""
    merged: bool = False


def _reviewed_plan(
    gh: GitHubClient, issue: Issue, state: PinnedState,
) -> _ReviewedPlan | None:
    """Read the plan PR this issue records, or answer that it could not be.

    `None` is the read that failed, and it ends the tick rather than falling
    back. Everything downstream of this answer is a durable decision -- which
    tip the developer starts from, and which commit stands in for the path
    record about to be retired -- so a tick that cannot take the reading must
    not make those decisions on the strength of a stale one.

    A PR with no readable head is the same answer as a PR that could not be
    fetched. Both mean nothing was established, which is not what an issue with
    no plan PR at all reports.
    """
    if not _plan_published(state):
        return _ReviewedPlan()
    return _read_plan_pr(gh, issue, state.get(_PR_NUMBER))


def _read_plan_pr(
    gh: GitHubClient, issue: Issue, pr_number,
) -> _ReviewedPlan | None:
    """Ask GitHub what one recorded plan PR is on, and whether it landed.

    Split from the reading above because two callers decide differently that
    there IS a plan PR to ask about. The relabel guard has the path record; the
    reconcile below it does not, since retiring that record is the very thing
    the handoff did.
    """
    try:
        plan_pr = gh.get_pr(int(pr_number))
    except Exception:
        log.exception(
            "issue=#%s could not fetch plan PR #%s while accepting the "
            "relabel; deferring the tick", issue.number, pr_number,
        )
        return None
    head = getattr(plan_pr.head, "sha", None)
    if not head:
        return None
    return _ReviewedPlan(
        head=head, merged=gh.pr_state(plan_pr) == _MERGED_PR_STATE,
    )


def _reconcile_open_plan_handoff(
    gh: GitHubClient, spec: config.RepoSpec, issue: Issue, state: PinnedState,
) -> bool:
    """Keep an accepted plan handoff in step with its PR until a dev pushes.

    The handoff is written before the developer runs, and everything the tick
    stages after it is dropped by an interruption on purpose -- so the window
    between that write and the first dev commit is one a crash, a restart or a
    live pause can leave an issue sitting in for polls at a time. The humans
    still have the design on an open pull request through all of it, and what
    they do to it there is exactly what the handoff existed to take account of.

    Nothing was left watching. `discussion_plan_path` is retired by that write,
    so plan identity falls to the recorded commit against the PR's live head --
    and an amendment made in this window moves that head, which reads as this
    stage having pushed: merged, the issue is closed `done` with no developer
    having run, and unmerged the developer is spawned on the checkout the
    handoff left, whose push takes the amendment back out. A merge alone is
    enough to matter even with nothing amended, since the baseline freezes base
    sync and the developer would start behind a base the plan has just landed
    in.

    So the handoff's own record is read as the state it is: `read_only_baseline
    _sha` beside `discussion_plan_sha` says a relabel was accepted and this
    stage has published nothing since. While it stands, the reading the guard
    took once is taken again -- the same PR read, the same re-anchor onto what
    it carries, the same two records written -- and the tick then continues to
    a developer starting where its reviewers left off.

    What ends it is the branch, because the branch is the only durable record
    of a developer having committed: pinned state written after a push is lost
    by the same crash this exists for. A tip nothing could read is not that
    answer -- it is no answer -- and the tick holds rather than deciding the
    plan question on a reading nobody took.

    A tip past the baseline is not that answer on its own, though, because the
    re-anchor below moves the branch BEFORE it records where it put it. A tick
    that dies in between leaves the branch on the plan PR's live head with the
    older commit still recorded -- indistinguishable, by the branch alone, from
    a developer having committed. Read that way, the next tick hands the
    reviewers' own amendment to the recovered-work shortcut, which skips the
    agent and publishes their edit as the implementation. So the move writes a
    marker of its own before it makes it, and a marker still standing says the
    branch is where this stage put it and nothing has been published from here.
    """
    baseline = _accepted_handoff_baseline(state)
    if baseline is None:
        return False
    unspent = _handoff_unspent(spec, issue, state, baseline)
    if unspent is None:
        log.warning(
            "issue=#%s holding the accepted plan handoff: the branch tip "
            "could not be read, so nothing here can say whether a developer "
            "has committed on it", issue.number,
        )
        return True
    if unspent:
        return _readvance_plan_handoff(gh, spec, issue, state)
    return False


def _accepted_handoff_baseline(state: PinnedState) -> str | None:
    """The tip an accepted plan handoff recorded, while its records stand.

    All three are the one state: the baseline says a relabel was accepted and
    nothing here has published since, the plan commit says the pull request
    that relabel handed over is a design rather than a build, and the number
    says which one. An issue missing any of them is not in it.
    """
    baseline = str(state.get(_state._READ_ONLY_BASELINE_SHA) or "")
    if not baseline or not state.get(_PLAN_SHA):
        return None
    if state.get(_PR_NUMBER) is None:
        return None
    return baseline


def _handoff_unspent(
    spec: config.RepoSpec,
    issue: Issue,
    state: PinnedState,
    baseline: str,
) -> bool | None:
    """Whether no developer has committed on this branch yet, or None unread.

    A move still marked in flight answers before the branch is asked at all,
    and answers yes whatever the tip is: the marker is written before the ref
    is touched and retired by the write that records where it landed, so a tick
    finding one knows the branch is where this stage was putting it. Nothing is
    spawned between the two, so no developer can have committed under it.

    Otherwise the baseline answers. It names the tip the last completed write
    vouched for, and a branch that has moved off it since has moved for one
    reason -- the developer this handoff was accepted for committed on it.

    A tip nothing could read is neither, and the caller holds on it: proving no
    developer has published cannot rest on a probe that did not run.
    """
    if state.get(_state._HANDOFF_ANCHOR_SHA):
        return True
    tip = _worktree_recovery._branch_tip_sha(
        spec, _worktree_paths._resolve_branch_name(state, spec, issue.number),
    )
    if not tip:
        return None
    return tip == baseline


def _readvance_plan_handoff(
    gh: GitHubClient, spec: config.RepoSpec, issue: Issue, state: PinnedState,
) -> bool:
    """Move an unspent handoff onto whatever the plan PR carries now.

    The same three answers `_handle_stale_read_only_park` has. A PR that could
    not be read decides nothing and ends the tick; a head that could not be put
    on the branch holds the handoff where it is rather than spawning a
    developer behind the reviewers; and anything else records what the branch
    really ended up on.

    A MERGED plan is re-anchored even when its head has not moved, because what
    the developer starts from is the base by then and the base moves on its own
    -- the design landed in it, and so has everything else that landed since.
    Only a reading that changes neither record writes nothing, which is the
    ordinary poll of a handoff nobody has touched.

    The marker is what makes the move itself recoverable, and it is durable
    before the ref is touched for the same reason the publication's is:
    everything after that point can leave the world changed, and the branch it
    leaves behind is one the next tick has to be able to recognize as this
    stage's rather than as a developer's work to publish. It is retired by the
    write that says where the branch ended up, so the two are never both true
    and never both false.
    """
    reviewed = _read_plan_pr(gh, issue, state.get(_PR_NUMBER))
    if reviewed is None:
        return True
    recorded = str(state.get(_PLAN_SHA) or "")
    if reviewed.head == recorded and not reviewed.merged:
        return _spend_handoff_anchor(gh, issue, state)
    state.set(_state._HANDOFF_ANCHOR_SHA, reviewed.head)
    gh.write_pinned_state(issue, state)
    inherited = _inherited_tip(spec, issue, state, reviewed)
    if inherited.pending:
        return True
    state.set(_PLAN_SHA, reviewed.head)
    state.set(_state._READ_ONLY_BASELINE_SHA, inherited.sha)
    state.set(_state._HANDOFF_ANCHOR_SHA, None)
    gh.write_pinned_state(issue, state)
    return False


def _spend_handoff_anchor(
    gh: GitHubClient, issue: Issue, state: PinnedState,
) -> bool:
    """Retire a marker whose move has nothing left to make, and continue.

    The ordinary poll leaves it alone, since there is none. One IS standing
    when the move that wrote it landed and the tick died before recording it,
    and the humans then put the PR back where the records already say it is --
    at which point the branch is where it belongs and only the marker is left
    to spend.
    """
    if state.get(_state._HANDOFF_ANCHOR_SHA):
        state.set(_state._HANDOFF_ANCHOR_SHA, None)
        gh.write_pinned_state(issue, state)
    return False


@dataclass(frozen=True)
class _ReadOnlyRelabelHazard:
    branch: str
    trigger: str


def _uncertified_commits(
    spec: config.RepoSpec,
    issue: Issue,
    state: PinnedState,
    reviewed: _ReviewedPlan,
) -> str | None:
    """The per-issue branch carrying commits the conversation stage did not vouch for.

    Ahead-of-base is the question by default, because for most of these parks
    a branch ahead of base is exactly the violation. The discussion stage is
    the exception: it tolerates commits an issue arrived with, so it records
    the branch and SHA each round opened on and leaves that pair standing on
    every park where the round did not move it.

    Where an anchor exists it is asked FIRST and on its own terms, because
    ahead-of-base cannot stand in for it in either direction. A branch reset
    all the way to base is no longer ahead of base, yet on a PR-backed issue
    that reset threw away the commits the round was certified against -- so
    the cheap answer would clear a `discussion_commits` park whose violation
    nobody resolved. The recorded ref is therefore compared to the recorded
    SHA whatever its relation to base is, and only an exact match certifies.

    A recorded ref that no longer exists is not a mismatch: there is nothing
    local left to attribute, and a PR-backed checkout is rebuilt from the PR
    head, which never carried this stage's work. That is the same reading
    `_branch_tip_sha` gives its other caller. Commits on any OTHER candidate
    branch still convict, so a round that committed on the sibling ref of a
    legacy-pinned branch is not let through by its anchor.

    What certifies a tip is `_certified_tips`, and the anchor is not the only
    entry: the head the recorded plan PR is on certifies too. Two ticks want
    that. The branch may already have been brought forward onto that head by a
    previous attempt at this handoff that died before recording it, and the
    humans themselves may have pulled their own amendment down. Neither is a
    commit anybody here made -- it is the design as its reviewers left it on
    the PR.

    A MERGED plan takes the older question back, and it has to. The handoff for
    one moves the branch to the base rather than to any recorded head, and the
    move happens before the write that records it -- so a tick that dies in
    between leaves a branch at a tip no record names, which this reading would
    convict and then ask an operator to reset BACKWARDS off. A branch carrying
    nothing beyond base carries nothing of anybody's either, which is exactly
    what ahead-of-base answers, and it is the same reading this guard already
    trusts for the stage with no anchor at all. The move is idempotent, so the
    next tick simply makes it again against whatever the base is by then.
    """
    unpushed = _worktree_recovery._branch_has_unpushed_commits(spec, issue.number)
    round_branch = state.get(_ROUND_BRANCH)
    round_sha = state.get(_ROUND_SHA)
    if not round_sha or not round_branch:
        return unpushed
    anchored = str(round_branch)
    tip = _worktree_recovery._branch_tip_sha(spec, anchored)
    if tip and _tip_is_uncertified(state, reviewed, tip, unpushed == anchored):
        return anchored
    if unpushed is None or unpushed == anchored:
        return None
    return unpushed


def _tip_is_uncertified(
    state: PinnedState,
    reviewed: _ReviewedPlan,
    tip: str,
    ahead_of_base: bool,
) -> bool:
    """Whether a recorded branch's tip is one nothing here can vouch for.

    A recorded tip is matched exactly, which is what a discussion held on an
    inherited PR branch needs: that branch is legitimately ahead of base, so
    the older question would convict it of its dev's commits.

    A merged plan is the exception, and the reason is the handoff it is about
    to get. That handoff puts the branch on the BASE -- the design landed, so
    the base carries it -- and it moves the ref before the write that records
    where it put it. A crash in between leaves a tip no record names, and
    matching exactly would report the base itself as unreviewed work and offer
    the round anchor as the reset target: an operator told to move a branch
    backwards off the commit the merge produced. So once the plan has merged,
    a branch carrying nothing beyond base is certified by carrying nothing --
    the same ahead-of-base reading this guard applies where no tip was ever
    recorded.
    """
    if tip in _certified_tips(state, reviewed.head):
        return False
    return ahead_of_base or not reviewed.merged


def _certified_tips(state: PinnedState, reviewed_sha: str) -> frozenset:
    """Every commit this guard has grounds to vouch for a checkout sitting on.

    The tip the round opened on, because everything at or under it predates
    this stage, and the head the recorded plan PR is on, because that is the
    design as its reviewers left it. Nothing else, and deliberately not the tip
    a publication is in flight on: that commit is the plan this stage wrote,
    which is the one thing that may never leave here as a dev push.
    """
    anchor = str(state.get(_ROUND_SHA) or "")
    return frozenset(tip for tip in (anchor, reviewed_sha) if tip)


def _read_only_relabel_hazard(
    spec: config.RepoSpec,
    issue: Issue,
    state: PinnedState,
    reviewed: _ReviewedPlan,
) -> _ReadOnlyRelabelHazard | None:
    unpushed = _uncertified_commits(spec, issue, state, reviewed)
    triggers = _unfinished_publication_triggers(state) + _checkout_triggers(
        spec, issue.number, state, reviewed,
    )
    if unpushed:
        triggers += (
            f"unreviewed commits on the per-issue branch `{unpushed}`",
        )
    if not triggers:
        return None
    branch = unpushed or _worktree_paths._resolve_branch_name(
        state, spec, issue.number,
    )
    return _ReadOnlyRelabelHazard(
        branch=branch, trigger=" AND ".join(triggers),
    )


def _unfinished_publication_triggers(state: PinnedState) -> tuple[str, ...]:
    """The publication this stage began and never finished, if there is one.

    Refused on the record alone, because the record is the only thing that
    survives every way this can look locally. The marker is written before the
    push, so by the time a tick dies past it the branch may be on the remote
    with a pull request open against it -- and nothing here can say whether it
    is. A checkout that is gone reads as clean, a local ref that never existed
    reads as nothing to attribute, and a branch an operator reset reads as
    certified: on a fresh clone all three are true at once, and the guard would
    hand the whole thing over having proved nothing.

    What follows such a handover is the sharpest version of what this guard
    exists to stop. The developer builds from base, the publication that opens
    the PR is gone, and the push takes a lease read live off the remote -- so it
    force-pushes over the published plan, adopts the pull request already open
    on that branch, and rewrites its body to close the issue on merge.

    The way out is not a reset: it is the label that owns the unfinished half.
    The `discussion` stage's own recovery restores the checkout from the PR
    head, adopts the PR that is already open, and records it -- and only once
    that has happened (or the operator has reset the marker away there) is
    there anything here to hand over.
    """
    in_flight = state.get(_PUBLISHING_SHA)
    if not in_flight:
        return ()
    return (
        f"`{in_flight}` mid-publication -- possibly already pushed, with a "
        "pull request open against it",
    )


def _checkout_triggers(
    spec: config.RepoSpec,
    issue_number: int,
    state: PinnedState,
    reviewed: _ReviewedPlan,
) -> tuple[str, ...]:
    """What the retained checkout itself is carrying, if anything.

    The branch reads answer for named refs, and a checkout does not have to be
    on one. An agent that committed while detached -- or onto a ref nothing
    here looks at -- leaves `refs/heads/<branch>` sitting exactly where the
    round opened it while the tree in front of the developer is its commit. The
    creators keep such a checkout as it stands, and the recovered-work shortcut
    pushes whatever `HEAD` is, so the tip this guard has to prove is the
    checkout's own and not just its branch's.

    An unreadable HEAD is a finding of the same kind, and so is a tree `git
    status` could not report on -- the list form of that read maps its own
    failure to "no paths", which is the answer a clean tree gives. Neither is a
    clean checkout; both are probes that never answered, and a guard whose whole
    job is to PROVE the tree carries nothing this stage wrote may not rest on
    one. What follows an unproven clean reading is the destructive half: the
    creators force-remove a checkout with nothing unpushed on it, so the tree an
    operator was parked to look at would be gone before anyone read it.

    Both readings are reported, and so is a dirty tree beside them, because an
    operator fixing what the refusal names wants all of it the first time.
    """
    worktree = _worktree_paths._worktree_path(spec, issue_number)
    if not worktree.exists():
        return ()
    triggers: list[str] = []
    head = _verification_probes._head_sha(worktree)
    if not head:
        triggers.append("a per-issue worktree whose HEAD could not be read")
    elif not _checkout_certified(spec, worktree, head, state, reviewed):
        triggers.append(f"a per-issue worktree sitting on `{head}`")
    tree_status = _verification_probes._worktree_status(worktree)
    if not tree_status.readable:
        triggers.append(
            "a per-issue worktree whose state could not be read "
            "(`git status` failed)",
        )
    elif tree_status.paths:
        triggers.append("dirty edits in the per-issue worktree")
    return tuple(triggers)


def _checkout_certified(
    spec: config.RepoSpec,
    worktree: Path,
    head: str,
    state: PinnedState,
    reviewed: _ReviewedPlan,
) -> bool:
    """Whether this checkout is sitting somewhere the guard can vouch for.

    A recorded tip is the sharper question and the one a discussion needs: its
    branch may legitimately be ahead of base, carrying a PR's commits the round
    opened on top of, so only an exact match with what was recorded certifies.

    With nothing recorded there is nothing to match against, and the question
    stage is the caller that has nothing: its checkout is recreated from base
    every spawn and its contract forbids finishing on a branch carrying
    anything. So the older question is asked instead, and asked of the CHECKOUT
    -- `_has_new_commits` reads `HEAD` against `<remote>/<base>`, which is what
    makes it answer for a commit made while detached as readily as for one on
    the branch.

    A merged plan is asked the older question too, and for the reason the
    branch reading beside this one gives: its handoff resets the checkout to
    the base, and the write recording where it landed comes after the reset --
    so the tick that dies in between leaves a tree on a commit no record names,
    which an exact match would convict of the base branch itself.
    """
    certified = _certified_tips(state, reviewed.head)
    if head in certified:
        return True
    if certified and not reviewed.merged:
        return False
    return not _worktree_creation._has_new_commits(spec, worktree)


def _relabel_remediation(
    state: PinnedState, hazard: _ReadOnlyRelabelHazard,
) -> str:
    """Say how to clear the hazard without destroying work worth keeping.

    Resetting to base and deleting the branch are both right for a stage whose
    branch should carry nothing, which is the question stage's case. A
    discussion can be held on a branch that arrived with a PR's commits on it,
    and both of those would discard the PR; the round anchor names the tip that
    branch was at before the agent touched it, so when one is recorded for this
    same branch it is the reset target that leaves the inherited work in place
    -- and it is what this guard re-measures the branch against next tick.

    A publication in flight is told the other way round. The commit under it is
    the agreed plan, and it may already be pushed with a pull request open
    against it, so the first thing to offer is the label that finishes what was
    started: the `discussion` stage picks its own marker up and publishes.
    Resetting is still there, but it is the answer for somebody who has decided
    to drop the plan, not the first thing an operator should read.
    """
    if state.get(_PUBLISHING_SHA):
        return (
            f"Relabel back to `{WorkflowLabel.DISCUSSION}` and that stage "
            "finishes the publication it began -- the commit may already be "
            "pushed with a pull request open against it. To drop the plan "
            f"instead: {_reset_instruction(state, hazard)}"
        )
    return _reset_instruction(state, hazard)


def _reset_instruction(
    state: PinnedState, hazard: _ReadOnlyRelabelHazard,
) -> str:
    """The reset that clears the branch, aimed at the tip worth keeping."""
    round_sha = state.get(_ROUND_SHA)
    if round_sha and str(state.get(_ROUND_BRANCH)) == hazard.branch:
        return (
            f"Reset the worktree to `{round_sha}` -- the tip the last "
            "conversation round opened on, so any commits the branch already "
            "carried survive -- before re-relabeling: `git -C <worktree> "
            f"reset --hard {round_sha} && git -C <worktree> clean -fd`."
        )
    return (
        "Reset the worktree (e.g. `git -C <worktree> reset --hard "
        "origin/<base> && git -C <worktree> clean -fd`), or delete the "
        f"local branch (`git branch -D {hazard.branch}` in `target_root`), "
        "before re-relabeling so the dev agent starts from a clean base."
    )


def _unsafe_relabel_finding(state: PinnedState, stage: str) -> str:
    """What this issue was carrying when the relabel arrived.

    The unfinished publication is named first, because the reason standing
    beside one is `discussion_publishing` -- a state, not a park anybody was
    ever shown a comment for. Every other park names itself, and its reason is
    what an operator matches against the comment that wrote it. An issue with
    neither is one whose round never reached a disposition at all.
    """
    if state.get(_PUBLISHING_SHA):
        return f"a {stage}-stage publication that never finished"
    park_reason = state.get(_state._PARK_REASON)
    if isinstance(park_reason, str) and park_reason:
        return f"the prior {stage}-stage park (`{park_reason}`)"
    return f"a {stage}-stage round that never reported"


def _park_unsafe_read_only_relabel(
    gh: GitHubClient,
    issue: Issue,
    state: PinnedState,
    stage: str,
    hazard: _ReadOnlyRelabelHazard,
) -> None:
    unsafe_reason = f"{stage}{_UNSAFE_RELABEL_SUFFIX}"
    _guards._park_awaiting_human(
        gh, issue, state,
        f"{config.HITL_MENTIONS} relabeled to `{WorkflowLabel.IMPLEMENTING}`, "
        f"but {_unsafe_relabel_finding(state, stage)} left "
        f"{hazard.trigger}. Nothing the {stage} stage leaves in the worktree "
        "is shipped as a dev implementation -- a discussion publishes the one "
        "plan it confirmed, itself and through its own check, and this is not "
        f"that -- so the orchestrator refuses to push it. "
        f"{_relabel_remediation(state, hazard)}",
        reason=unsafe_reason,
    )
    state.set(_state._PARK_REASON, unsafe_reason)


def _clear_stale_read_only_park(
    gh: GitHubClient,
    issue: Issue,
    state: PinnedState,
    reviewed_sha: str,
    inherited_sha: str | None,
) -> None:
    state.set(_state._AWAITING_HUMAN, False)
    state.set(_state._PARK_REASON, None)
    # The round anchor is retired here -- the branch is the dev's from now on,
    # so nothing is holding that tip still any more -- but it is handed over
    # rather than dropped. What it certified is exactly what the fresh-spawn
    # path must NOT read as a previous dev run: a discussion held on its PR's
    # branch leaves commits ahead of base, and the recovered-worktree shortcut
    # would skip the implementer and republish them as its work.
    state.set(_state._READ_ONLY_BASELINE_SHA, inherited_sha)
    state.set(_ROUND_BRANCH, None)
    state.set(_ROUND_SHA, None)
    _retire_plan_records(state, reviewed_sha)
    latest = gh.latest_comment_id(issue)
    if isinstance(latest, int):
        prior = state.get(_state._LAST_ACTION_COMMENT_ID)
        if not isinstance(prior, int) or latest > prior:
            state.set(_state._LAST_ACTION_COMMENT_ID, latest)


def _retire_plan_records(state: PinnedState, reviewed_sha: str) -> None:
    """Spend the `discussion` stage's records, and leave the plan's head behind.

    The path record exists to stop that stage acting while the design is with
    the humans on its PR, and the relabel IS them deciding -- left standing, it
    would hold the stage inert for good if an operator ever moved the issue
    back.

    Retiring it is what hands the plan question over to the recorded commit, so
    the head that PR is on NOW is what goes in its place. The humans may have
    amended their own plan on it, and the commit publication recorded would
    then read as somebody's implementation from the next tick on -- closing the
    issue as `done` on their edit, with no developer having run. Both go in the
    one write, or an interruption between them would leave exactly that gap.

    The two mid-flight records go with them: a round or a publication nobody
    finished is one the relabel has just answered another way, and a flag
    outliving it would have that stage claim a commit the dev made.
    """
    if reviewed_sha:
        state.set(_PLAN_SHA, reviewed_sha)
    state.set(_PLAN_PATH, None)
    state.set(_PUBLISHING_SHA, None)
    state.set(_ROUND_OPEN, None)


@dataclass(frozen=True)
class _HandoffTip:
    """The tip a relabel hands over, or that it cannot be handed over yet.

    `pending` is the second one, and it is not a tip at all: the reviewed head
    could not be put on the branch, so there is nothing this stage may record
    and nothing it may run. Accepting the relabel anyway would spawn the
    developer on a commit the reviewers moved past and let the ordinary push
    that follows read their head off the remote as its own lease.
    """

    sha: str | None = None
    pending: bool = False


def _inherited_tip(
    spec: config.RepoSpec,
    issue: Issue,
    state: PinnedState,
    reviewed: _ReviewedPlan,
) -> _HandoffTip:
    """The tip the developer starts from, once the branch is where it belongs.

    The anchor is the answer on every issue without a plan PR, and on one whose
    PR is still on the commit this stage published: it is the tip the guard
    above certified, and the spawn path reads it back to keep the commits an
    issue arrived with from passing as a dev run to finish.

    A plan PR the humans moved is the other case, and the branch is brought
    forward onto that head before anything is written or spawned. The developer
    has to build on the design its reviewers actually approved, and a push from
    a tip that does not contain their amendment is what would overwrite it.

    A plan PR that MERGED is the third case, and the anchor is wrong for it
    even when it matches: the design landed, so the base carries it along with
    everything else that has landed since, and the branch it was open against
    may be deleted. Left on the commit that merged, the developer starts behind
    the branch they are building for and their PR opens against a base they
    never saw. So the move is asked for with no head at all, which is how the
    anchor is told to put the checkout on the base.

    What comes back is where the branch REALLY ends up, never where the move
    intended to put it: the reviewed head, or the base. A move that established
    neither leaves the handoff pending rather than recording the
    anchor -- the checkout would still be behind the reviewers, and a baseline
    naming any other commit would have the spawn path read the difference as an
    interrupted dev run and push it with no agent having run at all.
    """
    anchor = state.get(_ROUND_SHA)
    if not reviewed.head:
        return _HandoffTip(sha=anchor)
    onto = "" if reviewed.merged else reviewed.head
    if onto and onto == str(anchor or ""):
        return _HandoffTip(sha=anchor)
    anchored = _worktree_creation._anchor_pr_worktree(
        spec,
        issue.number,
        branch=_worktree_paths._resolve_branch_name(state, spec, issue.number),
        head_sha=onto,
    )
    if anchored is None:
        log.warning(
            "issue=#%s holding the plan handoff: the checkout could not be "
            "put on %s", issue.number, onto or "the base branch",
        )
        return _HandoffTip(pending=True)
    return _HandoffTip(sha=anchored)
