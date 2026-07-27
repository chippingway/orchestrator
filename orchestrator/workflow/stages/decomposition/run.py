# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""One `decomposing` tick: what runs before the agent, and what the agent earns.

The order in `_prepare_decomposer_run` is the contract. Drift goes first, so a
body edited during a crash window clears the manifest markers before recovery
can read them and finalize a split the human no longer wants. Recovery goes
next, and deliberately ahead of the `DECOMPOSE` kill switch: children already
open on GitHub have to be resolved whether or not new decompositions are still
enabled -- a kill switch that stranded existing work would be the wrong kind of
off. Only past both does the tick pick between resuming a parked session and
spawning a fresh one.

Everything after the run is about what that run is allowed to publish. A
`paused` label applied mid-run wins over the whole disposition, an agent that
left commits or edits in a read-only worktree parks with the worktree kept for
inspection, and an interrupted run is dropped entirely -- checked in that order
so a killed run's changes stay inspectable rather than being discarded as
untrustworthy.

The worktree is torn down by an `ExitStack` callback rather than at each exit,
because `keep_worktree` is decided in the middle of that sequence and every
path after it -- including one that raises -- has to honor the decision.
"""
from __future__ import annotations

from contextlib import ExitStack

from github.Issue import Issue

from orchestrator import config
from orchestrator.agents import AgentResult
from orchestrator.github.client import GitHubClient
from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.engine import comments as _comments
from orchestrator.workflow.engine import guards as _guards
from orchestrator.workflow.engine import usage as _usage
from orchestrator.workflow.stages.decomposition import outcomes as _outcomes
from orchestrator.workflow.stages.decomposition import recovery as _recovery
from orchestrator.workflow.stages.decomposition import session as _session
from orchestrator.workflow.stages.decomposition import state as _state
from orchestrator.workflow.stages.decomposition.models import (
    _DecomposerCleanup,
    _DecomposerRunPlan,
)
from orchestrator.workflow.state import WorkflowLabel


def _route_disabled_to_implementing(
    gh: GitHubClient, spec: config.RepoSpec, issue: Issue, state: PinnedState
) -> bool:
    """DECOMPOSE kill-switch bailout.

    Returns True when decomposition is disabled and the issue was routed
    to implementation (caller must return); False when decomposition is
    enabled and the caller should proceed to spawn the decomposer.

    Every path after this point spawns the decomposer (fresh or via the
    awaiting_human resume), so an operator who restarts with DECOMPOSE=off
    after `_handle_pickup` already labeled the issue `decomposing` -- or
    while it is parked there awaiting a human -- would still see the
    disabled rollout create manifests and child issues. Drop into the
    legacy implementing flow exactly as `_handle_pickup` does on a freshly
    unlabeled issue. The half-finished recovery above must keep running
    regardless of the flag: abandoning orphan children (already on GitHub)
    because new decompositions are now disabled would strand work, which
    is not what a kill switch should do.
    """
    from orchestrator import workflow as _wf

    if config.DECOMPOSE:
        return False
    _comments._post_issue_comment(
        gh, issue, state,
        ":robot: decomposition is disabled; routing this issue "
        "to implementation.",
    )
    # Clear decomposer-side park state. Without this,
    # `_handle_implementing` reads `awaiting_human=True` and
    # tries to resume a dev session that was never spawned --
    # at best it stalls on `comments_after`, at worst the
    # follow-up text becomes the sole prompt instead of the
    # real implement prompt.
    state.set(_state._AWAITING_HUMAN, False)
    state.set(_state._PARK_REASON, None)
    # Mark every comment visible at this transition as
    # "already consumed", mirroring `_handle_ready`'s ratchet.
    # `_handle_implementing` will read the full issue thread
    # via `_recent_comments_text` when it builds the implement
    # prompt, so the dev sees any decomposing-era human
    # feedback at spawn. Without this bump, the
    # validating->in_review watermark seed later sees those
    # same comments as fresh PR feedback (because they sit
    # AFTER the now-stale `last_action_comment_id` from the
    # decomposer-era park) and bounces the dev unnecessarily.
    # One-way ratchet so we never lower a higher prior value.
    latest = gh.latest_comment_id(issue)
    if isinstance(latest, int):
        prior = state.get(_state._LAST_ACTION_COMMENT_ID)
        if not isinstance(prior, int) or latest > prior:
            state.set(_state._LAST_ACTION_COMMENT_ID, latest)
    gh.set_workflow_label(issue, WorkflowLabel.IMPLEMENTING)
    gh.write_pinned_state(issue, state)
    _wf._handle_implementing(gh, spec, issue)
    return True


def _settle_decomposer_run(
    gh: GitHubClient,
    issue: Issue,
    state: PinnedState,
    decomposer_result: AgentResult,
) -> bool:
    """Fold this run's usage and park on a live pause or timeout.

    Returns True when the caller must return (paused or timed out), False
    to continue to the dirty-worktree check and manifest dispatch. None of
    these paths preserve the decompose worktree: the caller's `finally`
    tears it down on return. The read-only dirty/commits park (which DOES
    preserve the worktree) stays inline in `_handle_decomposing` so
    `keep_worktree` is set BEFORE the park's side effects run.
    """
    # Live pause: an operator applied `paused` / `backlog` while the
    # decomposer ran (fresh spawn or awaiting-human resume). Dispatch only
    # saw the pre-run labels, so re-check a freshly fetched issue and return
    # WITHOUT folding usage, parking on timeout, creating child issues,
    # relabeling, or writing pinned state -- durable GitHub state stays
    # exactly as the prior tick left it and the next tick re-runs the
    # decomposer once the label is removed. The read-only decompose worktree
    # is torn down by the caller's `finally` as on any normal exit and
    # recreated on the re-run.
    if _guards._paused_during_agent_run(gh, issue):
        return True

    state.set("last_agent_action_at", _usage._now_iso())
    # Fold this run's usage into the per-issue counters at the convergence
    # of the fresh-spawn and awaiting-human resume branches, so a real
    # resume exit is counted exactly once and the no-new-comment resume
    # (which returned above without running the agent) never touches the
    # counters. Interrupted runs are excluded entirely: the read-only
    # dirty/commits park below still writes pinned state (to preserve the
    # inspection worktree), so folding a killed run's usage first would
    # persist a counter the interrupted contract says must not accrue. The
    # clean-interrupted case is additionally short-circuited by the
    # `_ignore_if_interrupted` guard in `_handle_decomposing`.
    if not decomposer_result.interrupted:
        _usage._accumulate_issue_usage(state, decomposer_result.usage)

    if decomposer_result.timed_out:
        _guards._park_awaiting_human(
            gh, issue, state,
            f"{config.HITL_MENTIONS} decomposer timed out after "
            f"{config.AGENT_TIMEOUT}s, manual intervention needed.",
            reason="decomposer_timeout",
        )
        gh.write_pinned_state(issue, state)
        return True
    return False


def _prepare_decomposer_run(
    gh: GitHubClient,
    spec: config.RepoSpec,
    issue: Issue,
    state: PinnedState,
) -> _DecomposerRunPlan:
    # User-content drift FIRST, so it runs BEFORE the half-finished recovery:
    # otherwise recovery could finalize against a stale manifest when the issue
    # was edited during a crash window.
    _session._reset_decomposing_on_drift(gh, issue, state)

    if _recovery._recover_stale_manifest(gh, issue, state):
        return _DecomposerRunPlan(agent_result=None)

    if _route_disabled_to_implementing(gh, spec, issue, state):
        return _DecomposerRunPlan(agent_result=None)

    if state.get(_state._AWAITING_HUMAN):
        decomposer_result = _session._resume_decomposer_on_human_reply(
            gh, spec, issue, state,
        )
        return _DecomposerRunPlan(
            agent_result=decomposer_result,
            # A no-reply dirty park keeps its inspection worktree intact.
            keep_worktree=decomposer_result is None,
        )
    return _DecomposerRunPlan(
        agent_result=_session._spawn_fresh_decomposer(gh, spec, issue, state),
    )


def _process_decomposer_run(
    gh: GitHubClient,
    spec: config.RepoSpec,
    issue: Issue,
    state: PinnedState,
    run_plan: _DecomposerRunPlan,
) -> None:
    from orchestrator import workflow as _wf

    decomposer_result = run_plan.agent_result
    if decomposer_result is None:
        return

    if _settle_decomposer_run(gh, issue, state, decomposer_result):
        return

    # The decomposer is read-only. Preserve a changed worktree for operator
    # inspection, setting the cleanup policy before parking or persistence can
    # raise and trigger the handler's finally block.
    wt = _wf._decompose_worktree_path(spec, issue.number)
    if _wf._has_new_commits(spec, wt) or _wf._worktree_dirty_files(wt):
        run_plan.keep_worktree = True
        _guards._park_awaiting_human(
            gh, issue, state,
            f"{config.HITL_MENTIONS} decomposer left commits or "
            "uncommitted changes in the worktree, but it must be "
            "read-only. Reset the worktree before resuming.",
            reason="decomposer_dirty",
        )
        gh.write_pinned_state(issue, state)
        return

    # An interrupted run has no trustworthy manifest. The read-only check
    # stays first so changes left by a killed run remain available to inspect.
    if _guards._ignore_if_interrupted(issue, decomposer_result):
        return

    _outcomes._dispatch_decomposer_manifest(gh, issue, state, decomposer_result)


def _handle_decomposing(gh: GitHubClient, spec: config.RepoSpec, issue: Issue) -> None:
    state = gh.read_pinned_state(issue)
    cleanup = _DecomposerCleanup(
        spec=spec,
        issue_number=issue.number,
        run_plan=_DecomposerRunPlan(agent_result=None),
    )
    with ExitStack() as cleanup_stack:
        cleanup_stack.callback(cleanup.close)
        cleanup.run_plan = _prepare_decomposer_run(
            gh,
            spec,
            issue,
            state,
        )
        _process_decomposer_run(
            gh,
            spec,
            issue,
            state,
            cleanup.run_plan,
        )
