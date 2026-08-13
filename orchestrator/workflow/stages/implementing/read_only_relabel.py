# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Why a read-only stage's park is checked before an implementing relabel is trusted.

The `question` and `discussion` stages both park with `awaiting_human=True` and
a stage-prefixed reason so their own next tick can pick the conversation back
up. Implementing's resume path cannot read those flags -- they mean nothing to
it -- so a relabel out of either stage has to clear them or refuse, and the two
are handled here together because the hazard is identical: both agents are told
to write nothing, and neither stage ever pushes what one of them wrote anyway.

Which one happens is decided by the worktree and the branch, never by the park
reason alone. A misbehaving run can park having committed or dirtied the
per-issue branch, and dropping the park would let the fresh-spawn path's
recovered-worktree shortcut push that work as a dev implementation. The branch
is checked even when the worktree is gone, because a safe teardown (or an
operator) can remove the directory while the local branch survives carrying
those commits -- `_ensure_worktree` would restore it and the shortcut would
ship them.

"Ahead of base" is the question for a question-stage park, whose own contract
already refuses to finish a round on a branch carrying anything. The discussion
stage tolerates the commits an issue arrives with, so the same question would
convict it of its dev's work and strand an issue no operator could unstick;
what is asked there instead is whether the branch still sits at the SHA the
last round recorded opening on. That anchor is written before the spawn and
survives every park the stage takes -- including the two that found a commit,
which quote it as the tip to reset back to -- so it is the branch's position
against it, not the anchor's presence, that says whether the stage vouches for
what is there.

A refusal re-parks as `<stage>_unsafe_relabel` and is idempotent, so repeated
ticks stay silent until an operator resets the worktree or deletes the branch.
A clean pair means the relabel IS the unblock signal: the flags are dropped and
`last_action_comment_id` is ratcheted past what the read-only agent posted, or
the later validating -> in_review seed would replay it as fresh PR feedback.
The anchor is retired here rather than discarded -- it becomes
`read_only_baseline_sha`, the floor the dev run that follows is measured
against, since the branch it inherits is already ahead of base.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from github.Issue import Issue

from orchestrator import config
from orchestrator.git.verification import probes as _verification_probes
from orchestrator.git.worktrees import (
    paths as _worktree_paths,
    recovery as _worktree_recovery,
)
from orchestrator.github.client import GitHubClient
from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.engine import guards as _guards
from orchestrator.workflow.stages.discussion.state import (
    _ROUND_BRANCH,
    _ROUND_SHA,
)
from orchestrator.workflow.stages.implementing import state as _state
from orchestrator.workflow.state import WorkflowLabel

# The stages whose parks this guard answers for, named by the prefix their
# reasons carry in pinned state. Both are operator-applied read-only labels, so
# an issue can arrive at implementing from either one by a human relabel.
_READ_ONLY_PARK_STAGES: tuple[str, ...] = (
    str(WorkflowLabel.QUESTION), str(WorkflowLabel.DISCUSSION),
)

_UNSAFE_RELABEL_SUFFIX = "_unsafe_relabel"


def _parked_read_only_stage(state: PinnedState) -> Optional[str]:
    """Return the read-only stage whose park this issue still carries."""
    if not state.get(_state._AWAITING_HUMAN):
        return None
    park_reason = state.get(_state._PARK_REASON)
    if not isinstance(park_reason, str):
        return None
    for stage in _READ_ONLY_PARK_STAGES:
        if park_reason.startswith(f"{stage}_"):
            return stage
    return None


def _handle_stale_read_only_park(
    gh: GitHubClient, spec: config.RepoSpec, issue: Issue, state: PinnedState
) -> bool:
    """Clear a stale read-only park left by a relabel to `implementing`, or
    refuse the relabel when it would ship what that stage's agent wrote.

    `_handle_question` and `_handle_discussion` park with `awaiting_human=True`
    and `park_reason="<stage>_*"` so their own next tick can pick the
    conversation back up; those flags are opaque to implementing's resume path
    and would mis-fire it. When no such park is present this is a no-op
    returning False.

    The clear must check the actual worktree, NOT just the park reason. Both
    agents are supposed to be read-only, but a misbehaving run can park as
    `question_commits` / `discussion_commits` / `*_dirty` (or a `*_timeout`
    that committed before being killed) with unreviewed code state on the
    per-issue branch. Silently dropping the park would let the fresh-spawn
    branch's recovered-worktree shortcut (`_has_new_commits` -> push) publish
    those commits as if a dev session had authored them, violating the
    read-only contract.

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

    Returns False otherwise: either no read-only park is present, or the
    worktree and branch are both clean so the relabel IS the unblock signal --
    the park flags are dropped and `last_action_comment_id` ratcheted past the
    agent's last comment (so the eventual validating->in_review watermark seed
    cannot replay it as fresh PR feedback) before the caller falls through to
    the fresh-spawn path.
    """
    stage = _parked_read_only_stage(state)
    if stage is None:
        return False
    hazard = _read_only_relabel_hazard(spec, issue, state)
    if hazard is not None:
        unsafe_reason = f"{stage}{_UNSAFE_RELABEL_SUFFIX}"
        if state.get(_state._PARK_REASON) != unsafe_reason:
            _park_unsafe_read_only_relabel(
                gh, issue, state, stage, hazard,
            )
        gh.write_pinned_state(issue, state)
        return True
    _clear_stale_read_only_park(gh, issue, state)
    # Written HERE, before the caller reaches the spawn, because accepting the
    # handoff is a durable fact and not a staged one. The tick after it can end
    # without writing pinned state at all -- a mid-run pause or a shutdown
    # interruption drops every staged mutation on purpose -- and if this went
    # with them the next tick would read the park and anchor back, find the
    # dev's commit sitting past that anchor, and convict the developer of a
    # read-only violation it would then ask the operator to reset away.
    gh.write_pinned_state(issue, state)
    return False


@dataclass(frozen=True)
class _ReadOnlyRelabelHazard:
    branch: str
    trigger: str


def _uncertified_commits(
    spec: config.RepoSpec, issue: Issue, state: PinnedState,
) -> Optional[str]:
    """The per-issue branch carrying commits the read-only stage did not vouch for.

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
    """
    unpushed = _worktree_recovery._branch_has_unpushed_commits(spec, issue.number)
    round_branch = state.get(_ROUND_BRANCH)
    round_sha = state.get(_ROUND_SHA)
    if not round_sha or not round_branch:
        return unpushed
    anchored = str(round_branch)
    tip = _worktree_recovery._branch_tip_sha(spec, anchored)
    if tip and tip != str(round_sha):
        return anchored
    if unpushed is None or unpushed == anchored:
        return None
    return unpushed


def _read_only_relabel_hazard(
    spec: config.RepoSpec, issue: Issue, state: PinnedState,
) -> Optional[_ReadOnlyRelabelHazard]:
    worktree = _worktree_paths._worktree_path(spec, issue.number)
    dirty = worktree.exists() and bool(
        _verification_probes._worktree_dirty_files(worktree),
    )
    unpushed = _uncertified_commits(spec, issue, state)
    if not dirty and not unpushed:
        return None
    branch = unpushed or _worktree_paths._resolve_branch_name(
        state, spec, issue.number,
    )
    return _ReadOnlyRelabelHazard(
        branch=branch,
        trigger=_read_only_relabel_trigger(dirty, bool(unpushed), branch),
    )


def _read_only_relabel_trigger(dirty: bool, unpushed: bool, branch: str) -> str:
    if dirty and not unpushed:
        return "dirty edits in the per-issue worktree"
    if unpushed and not dirty:
        return f"unreviewed commits on the per-issue branch `{branch}`"
    return (
        f"unreviewed commits on the per-issue branch `{branch}` "
        "AND dirty edits in its worktree"
    )


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
    """
    round_sha = state.get(_ROUND_SHA)
    if round_sha and str(state.get(_ROUND_BRANCH)) == hazard.branch:
        return (
            f"Reset the worktree to `{round_sha}` -- the tip the last "
            "read-only round opened on, so any commits the branch already "
            "carried survive -- before re-relabeling: `git -C <worktree> "
            f"reset --hard {round_sha} && git -C <worktree> clean -fd`."
        )
    return (
        "Reset the worktree (e.g. `git -C <worktree> reset --hard "
        "origin/<base> && git -C <worktree> clean -fd`), or delete the "
        f"local branch (`git branch -D {hazard.branch}` in `target_root`), "
        "before re-relabeling so the dev agent starts from a clean base."
    )


def _park_unsafe_read_only_relabel(
    gh: GitHubClient,
    issue: Issue,
    state: PinnedState,
    stage: str,
    hazard: _ReadOnlyRelabelHazard,
) -> None:
    park_reason = str(state.get(_state._PARK_REASON))
    unsafe_reason = f"{stage}{_UNSAFE_RELABEL_SUFFIX}"
    _guards._park_awaiting_human(
        gh, issue, state,
        f"{config.HITL_MENTIONS} relabeled to `{WorkflowLabel.IMPLEMENTING}`, "
        f"but the prior {stage}-stage park (`{park_reason}`) left "
        f"{hazard.trigger}. The {stage} agent must be read-only, so the "
        "orchestrator refuses to push that work as a dev implementation. "
        f"{_relabel_remediation(state, hazard)}",
        reason=unsafe_reason,
    )
    state.set(_state._PARK_REASON, unsafe_reason)


def _clear_stale_read_only_park(
    gh: GitHubClient, issue: Issue, state: PinnedState,
) -> None:
    state.set(_state._AWAITING_HUMAN, False)
    state.set(_state._PARK_REASON, None)
    # The round anchor is retired here -- the branch is the dev's from now on,
    # so nothing is holding that tip still any more -- but it is handed over
    # rather than dropped. What it certified is exactly what the fresh-spawn
    # path must NOT read as a previous dev run: a discussion held on its PR's
    # branch leaves commits ahead of base, and the recovered-worktree shortcut
    # would skip the implementer and republish them as its work.
    state.set(_state._READ_ONLY_BASELINE_SHA, state.get(_ROUND_SHA))
    state.set(_ROUND_BRANCH, None)
    state.set(_ROUND_SHA, None)
    latest = gh.latest_comment_id(issue)
    if isinstance(latest, int):
        prior = state.get(_state._LAST_ACTION_COMMENT_ID)
        if not isinstance(prior, int) or latest > prior:
            state.set(_state._LAST_ACTION_COMMENT_ID, latest)
