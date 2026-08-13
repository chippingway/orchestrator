# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The one agent round a discussion opens with, and what it records.

The round runs in the issue's own `issue-N` worktree on its own branch rather
than in a scratch checkout of its own, because the design being discussed is
the design that branch will carry: an operator inspecting a park, and every
later round of the same conversation, look at the tree the discussion actually
read. Nothing here tears it down for that reason.

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
never did. And `_unfinished_round_committed` asks that same question a tick
late, for the rounds that never got to ask it themselves.

That last one is why the SHA is written down rather than only held. A round can
end without any disposition at all -- a mid-run `paused` withholds every one of
them by contract, and a crash takes them with it -- and the next tick then
reuses the same checkout, so a commit the ended round made would become the new
round's own baseline and read as work the branch arrived carrying. Recording
the SHA before the spawn is what keeps that classifiable: a non-empty anchor on
entry means a round opened and never finished, and comparing it to the tree
says whether it left a commit behind.

The spec rides that same pre-spawn write, so a run that returns no session id
-- a CLI hiccup, an empty `-o` file -- still records which backend and args this
issue's discussion ran under. It is read back on every later round rather than
re-resolved, because a replayed round is the same conversation: a
`DECOMPOSE_AGENT` flip between the withheld round and its replay must not move
it onto a backend that never ran here. The session id is staged when it arrives
and reaches GitHub with the park it belongs to, so a round nobody will ever see
never leaves a conversation pointer behind.
"""
from __future__ import annotations

from pathlib import Path

from orchestrator import config
from orchestrator.git.verification import probes as _verification_probes
from orchestrator.git.worktrees import (
    creation as _worktree_creation,
    paths as _worktree_paths,
    recovery as _worktree_recovery,
)
from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.engine import comments as _comments
from orchestrator.workflow.engine import prompts as _prompts
from orchestrator.workflow.engine import usage as _usage
from orchestrator.workflow.stages.discussion import models as _models
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


def _unfinished_round_committed(run: _models._DiscussionRun) -> bool:
    """True when a round that never reached a disposition left a commit.

    The anchor is what makes this answerable: it is written before the spawn
    and outlives every park, so what dates it is not its presence but the
    handler's gate above -- only an issue this stage does NOT have parked
    reaches here, and on one of those an anchor belongs to a round withheld by
    a mid-run pause or cut short by a crash. HEAD is compared against it
    rather than against the base, so a branch that already carried commits
    when the issue was relabeled here stays innocent.

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


def _locked_discussion_session(
    state: PinnedState,
) -> _models._DiscussionSession:
    """Return the agent identity this issue's discussion is locked to.

    Mirrors `_read_question_session` / `_read_decomposer_session`: the spec
    pinned at the first spawn wins over the current config on every round
    after it. A round can be replayed -- a mid-run pause, an interruption, or
    a crash ends one with no disposition and the next tick opens it again --
    and re-reading `DECOMPOSE_AGENT` there would let an env flip between the
    two ticks move a conversation onto a backend and argument set that never
    ran on this issue, then overwrite the pin with them.

    Legacy bare-backend values (`"codex"` / `"claude"`) re-parse to
    `(backend, ())` and round-trip cleanly. Only an issue that has never
    spawned a discussion agent falls through to the configured decomposer.
    """
    stored = state.get(_state._DISCUSSION_AGENT_KEY)
    if stored:
        agent_spec = str(stored)
        backend, extra_args = config._parse_agent_spec(
            _state._DISCUSSION_AGENT_KEY, agent_spec,
        )
        return _models._DiscussionSession(
            agent_spec=agent_spec, backend=backend, extra_args=extra_args,
        )
    return _models._DiscussionSession(
        agent_spec=config.DECOMPOSE_AGENT_SPEC,
        backend=config.DECOMPOSE_AGENT,
        extra_args=config.DECOMPOSE_AGENT_ARGS,
    )


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


def _open_discussion_round(
    run: _models._DiscussionRun,
) -> _models._DiscussionRound:
    """Run the opening discussion prompt, recording what it opened on.

    The spec and the anchor are written before the spawn because they are what
    a round that never comes back is judged by; the session id is staged after
    it and rides the park's write, so it never outlives the analysis it
    belongs to.
    """
    branch = _worktree_paths._resolve_branch_name(
        run.state, run.spec, run.issue.number,
    )
    worktree = _ensure_round_worktree(run, branch)
    head_before = _verification_probes._head_sha(worktree)
    session = _locked_discussion_session(run.state)
    run.state.set(_state._DISCUSSION_AGENT_KEY, session.agent_spec)
    run.state.set(_state._ROUND_BRANCH, branch)
    run.state.set(_state._ROUND_SHA, head_before)
    run.gh.write_pinned_state(run.issue, run.state)
    discussion_result = _usage._run_agent_tracked(
        run.gh,
        run.issue.number,
        agent_role=_state._DECOMPOSER_ROLE,
        stage=_state._DISCUSSION_STAGE,
        backend=session.backend,
        prompt=_prompts._build_discussion_prompt(
            run.spec,
            run.issue,
            _comments._recent_comments_text(run.issue),
            config.default_repo_specs(),
        ),
        cwd=worktree,
        agent_spec=session.agent_spec,
        extra_args=session.extra_args,
    )
    if discussion_result.session_id:
        run.state.set(
            _state._DISCUSSION_SESSION_KEY, discussion_result.session_id,
        )
    return _models._DiscussionRound(
        agent_result=discussion_result, head_before=head_before,
    )
