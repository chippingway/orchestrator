# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""One agent round of a discussion, opening or resumed, and what it records.

The round runs in the issue's own `issue-N` worktree on its own branch rather
than in a scratch checkout of its own, because the design being discussed is
the design that branch will carry: an operator inspecting a park, and every
later round of the same conversation, look at the tree the discussion actually
read. Nothing here tears it down for that reason, and a resumed round reuses
the tree its predecessor left rather than rebuilding one over it.

Reusing that tree is why every probe here exists. `_stranded_dirty_files` runs
BEFORE the checkout is prepared, because preparing it force-removes a dirty
tree that carries no commits and wiping it would destroy the only evidence an
operator has. Which restorer prepares it is decided by `pr_number`: once a PR
is open, the branch under discussion is the one it is open against, and a
pruned local ref has to come back from the PR head rather than from the base
branch. `_head_sha` is read after the checkout is settled and
before the spawn, because the branch may already carry commits from a stage the
issue passed through before an operator relabeled it here; a base-relative
probe would read those as this round's work and park the agent for something it
never did. And `_round_anchor_moved` asks that same question a tick late, for
the rounds that never got to ask it themselves.

That last one is why the SHA is written down rather than only held. A round can
end without any disposition at all -- a mid-run `paused` withholds every one of
them by contract, and a crash takes them with it -- and the next tick then
reuses the same checkout, so a commit the ended round made would become the new
round's own baseline and read as work the branch arrived carrying. Recording
the SHA before the spawn is what keeps that classifiable: on an issue this
stage does not have parked, a non-empty anchor means a round opened and never
finished, and comparing it to the tree says whether it left a commit behind.
On a parked one the same comparison says something narrower and just as
load-bearing -- whether the checkout is still the certified one -- which the
handler asks of both probes here before a reply may open a round on it.

The spec rides that same pre-spawn write, so a run that returns no session id
-- a CLI hiccup, an empty `-o` file -- still records which backend and args this
issue's discussion ran under. It is read back on every later round rather than
re-resolved, because every round after the first is the same conversation: a
`DECOMPOSE_AGENT` flip between two of them must not move it onto a backend that
never ran here, and must not hand a session id opened on one CLI to another.
The session id is staged when it arrives and reaches GitHub with the park it
belongs to, so a round nobody will ever see never leaves a conversation pointer
behind -- and the next round resumes the last one that was actually published.
"""
from __future__ import annotations

from pathlib import Path

from orchestrator.git.verification import probes as _verification_probes
from orchestrator.git.worktrees import (
    creation as _worktree_creation,
    paths as _worktree_paths,
    recovery as _worktree_recovery,
)
from orchestrator.workflow.engine import usage as _usage
from orchestrator.workflow.stages.discussion import models as _models
from orchestrator.workflow.stages.discussion import session as _session
from orchestrator.workflow.stages.discussion import state as _state


def _stranded_dirty_files(
    run: _models._DiscussionRun,
) -> tuple[str, ...]:
    """Uncommitted paths the checkout carried before this round opened.

    Every park this stage writes suppresses the next tick, so work waiting in
    the tree at the top of a discussion tick came either from a round that died
    before it could park on what it wrote, or from the stage the issue was
    relabeled out of. Reading it here -- ahead of the `_ensure_worktree` that
    would force-remove exactly that tree -- is what lets the caller preserve it
    instead of recreating over it.
    """
    worktree = _worktree_paths._worktree_path(run.spec, run.issue.number)
    if not worktree.exists():
        return ()
    return tuple(_verification_probes._worktree_dirty_files(worktree))


def _round_anchor_moved(run: _models._DiscussionRun) -> bool:
    """True when the checkout no longer sits where the last round opened it.

    The anchor is what makes this answerable: it is written before the spawn
    and outlives every park, so what a moved tip MEANS is decided by the
    caller. On an issue this stage does not have parked it is a round withheld
    by a mid-run pause or cut short by a crash, and the movement is the commit
    it left. On a parked one the round did reach a disposition, and the
    movement is somebody having written on the branch since -- the same
    violation, minus the question of who. HEAD is compared against the anchor
    rather than against the base, so a branch that already carried commits when
    the issue was relabeled here stays innocent either way.

    A missing checkout falls back to the branch tip, for the same reason the
    read-only relabel guard consults the branch at all: a directory can be
    removed while the local branch survives carrying the commits, and
    `_ensure_worktree` would restore it under the next round as that round's
    own baseline. It is the tip of the branch the round RECORDED that is read,
    and it is compared rather than measured against base -- an issue relabeled
    here from a PR stage has a branch ahead of base whatever this stage did, and
    an issue pinned to a legacy branch has a slug-namespaced ref beside it whose
    unchanged tip says nothing about where the round actually ran.
    """
    anchor = run.state.get(_state._ROUND_SHA)
    if not anchor:
        return False
    worktree = _worktree_paths._worktree_path(run.spec, run.issue.number)
    if not worktree.exists():
        return _recorded_branch_moved(run, str(anchor))
    return _verification_probes._head_sha(worktree) != str(anchor)


def _recorded_branch_moved(run: _models._DiscussionRun, anchor: str) -> bool:
    """True when the branch the round opened on no longer sits at `anchor`.

    A branch the anchor does not name is not this round's, and a branch that
    no longer exists carries nothing to attribute, so both read as "no commit".
    """
    branch = run.state.get(_state._ROUND_BRANCH)
    if not branch:
        return False
    branch_tip = _worktree_recovery._branch_tip_sha(run.spec, str(branch))
    return bool(branch_tip) and branch_tip != anchor


def _ensure_round_worktree(run: _models._DiscussionRun, branch: str) -> Path:
    """Prepare the checkout the round reads, restoring a pruned one in place.

    An issue arrives here from anywhere, and once it has a PR the branch it
    arrives on is the one that PR is open against. `_ensure_worktree` rebuilds
    a branch whose local ref has gone -- a host restart, a manual `git branch
    -D`, an operator's cleanup between ticks -- from `<remote>/<base>`, which
    would hand the round a tree with the PR's commits missing and have it
    discuss a design the issue is no longer on. Worse, the anchor written
    straight after would record that truncated tip as what the branch arrived
    carrying, so the relabel guard would later vouch for it.

    `_ensure_pr_worktree` anchors the same restore on `<remote>/<branch>`
    instead. That ref only exists once a PR has been pushed, so `pr_number` is
    what the choice is made on rather than the ref being probed for.
    """
    if run.state.get(_state._PR_NUMBER) is None:
        return _worktree_creation._ensure_worktree(
            run.spec, run.issue.number, branch=branch,
        )
    return _worktree_creation._ensure_pr_worktree(
        run.spec, run.issue.number, branch=branch,
    )


def _open_round_checkout(
    run: _models._DiscussionRun, *, resumed: bool,
) -> tuple[Path, str]:
    """Prepare the checkout the round reads, and record what it opened on.

    A resumed round takes the tree its predecessor read whenever it is still
    on disk. That is the tree the operator has been looking at while they
    composed the reply, and the handler's hold already established it is clean
    and still on the anchor -- which is exactly the tree `_ensure_worktree`
    force-removes and rebuilds, for no gain. Only a directory that has gone --
    a host restart, an operator's cleanup between ticks -- is restored, which
    is the same question an opening round asks of a branch it may not find.

    The anchor is staged here rather than by the caller because it is a
    statement about the checkout this just settled: the branch it resolved and
    the tip that branch was at once the tree was in hand. Both are read back
    by a later tick as one record, so neither is written without the other.
    """
    branch = _worktree_paths._resolve_branch_name(
        run.state, run.spec, run.issue.number,
    )
    retained = _worktree_paths._worktree_path(run.spec, run.issue.number)
    worktree = (
        retained
        if resumed and retained.exists()
        else _ensure_round_worktree(run, branch)
    )
    head_before = _verification_probes._head_sha(worktree)
    run.state.set(_state._ROUND_BRANCH, branch)
    run.state.set(_state._ROUND_SHA, head_before)
    return worktree, head_before


def _open_discussion_round(
    run: _models._DiscussionRun, replies: list | None = None,
) -> _models._DiscussionRound:
    """Run one discussion prompt, recording what it opened on.

    `replies` is the trusted batch a resumed round answers, and `None` on the
    conversation's opening round -- the two the caller can produce, since a
    batch with nothing in it never earns a round at all.

    The spec and the anchor are written before the spawn because they are what
    a round that never comes back is judged by. The consumed watermark is
    deliberately not in that write: a round that never comes back is replayed,
    and it has to be replayed against the same replies rather than against an
    answer already recorded as read. It is staged after it instead, beside the
    session id, so both reach GitHub only with the park that reports what the
    round made of them.

    Both round shapes stage one, and each over what its OWN prompt read: a
    resume over the batch it quotes, a full-context round over the thread it
    rebuilt -- which it HAS to, or the comments it just answered would read as
    unanswered replies on the next tick and earn a second round about them.
    The prompt hands its own back rather than being asked a second time, since
    a thread re-read here is a thread minutes older than the one the agent was
    shown.
    """
    session = _session._locked_discussion_session(run.state)
    worktree, head_before = _open_round_checkout(
        run, resumed=replies is not None,
    )
    run.state.set(_state._DISCUSSION_AGENT_KEY, session.agent_spec)
    run.gh.write_pinned_state(run.issue, run.state)
    round_prompt = _session._build_round_prompt(run, session, replies)
    _session._consume_replies(run, round_prompt.consumed)
    discussion_result = _usage._run_agent_tracked(
        run.gh,
        run.issue.number,
        agent_role=_state._DECOMPOSER_ROLE,
        stage=_state._DISCUSSION_STAGE,
        backend=session.backend,
        prompt=round_prompt.text,
        cwd=worktree,
        agent_spec=session.agent_spec,
        resume_session_id=session.session_id if replies else None,
        extra_args=session.extra_args,
    )
    _record_round_session(run, discussion_result, opened_fresh=replies is None)
    return _models._DiscussionRound(
        agent_result=discussion_result, head_before=head_before,
    )


def _record_round_session(
    run: _models._DiscussionRun, discussion_result, *, opened_fresh: bool,
) -> None:
    """Stage the conversation the NEXT round resumes, or the absence of one.

    A resumed round that hands back nothing keeps the pin it ran under: the
    session it continued is the one that answered, and a CLI that simply did
    not echo the id back must not cost the conversation its thread.

    A round opened fresh is the opposite case and overwrites it either way,
    absence included. Whatever it opened is a NEW conversation, and an issue
    can reach a fresh round still carrying a pin -- relabeled out of this stage
    and back, it arrives unparked with the session id its previous discussion
    left. Kept, that id would have the next reply resume a conversation about a
    design the thread has moved on from; cleared, that reply rebuilds the full
    context instead, which is the recovery the sessionless path already exists
    for.
    """
    if discussion_result.session_id:
        run.state.set(
            _state._DISCUSSION_SESSION_KEY, discussion_result.session_id,
        )
    elif opened_fresh:
        run.state.set(_state._DISCUSSION_SESSION_KEY, None)
