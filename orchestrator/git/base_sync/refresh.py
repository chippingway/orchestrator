# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The per-tick base refresh: which worktrees sync, and by which route.

One authenticated fetch of `origin/<base>` per spec feeds every issue
worktree that survived the previous tick, so the gates that decide whether a
worktree may be touched at all belong together: an in-flight scheduler claim,
a dispatcher hard-skip, the read-only conversation stages, an unreadable
issue, and a dirty pre-PR tree each end the sync before any rewrite is
attempted.
What survives is routed by whether pinned state already carries a PR --
`pre_pr` rebases the local branch nobody has pushed yet, while the PR-aware
coordinator has to keep the pushed head and the reviewer's SHA in step.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from github.Issue import Issue

from orchestrator import config
from orchestrator.git import authentication as _authentication, commands as _commands
from orchestrator.git.base_sync import (
    pr as _pr,
    pre_pr as _pre_pr,
    state as _state,
)
from orchestrator.git.verification import probes as _probes
from orchestrator.git.worktrees import paths as _paths
from orchestrator.github import (
    client as _client,
    labels as _labels,
    pinned_state as _pinned_state,
)
from orchestrator.scheduler import IssueScheduler
from orchestrator.workflow.state import WorkflowLabel

log = _state.log

_READ_ONLY_STAGE_LABELS: tuple[str, ...] = (
    str(WorkflowLabel.QUESTION), str(WorkflowLabel.DISCUSSION),
)

# Every record that freezes a branch on its own, whatever the labels and flags
# beside it say: the tip a read-only relabel handed over and has not spent, and
# the two a discussion tick leaves while it is mid-flight. They are spelled here
# the way every pinned key this module reads is -- what this gate pins down is
# how the refresh reads state written by stages it never calls into, so a shared
# constant would let a rename pass unnoticed on the side that has to keep
# understanding it. The two discussion records do not depend on
# `awaiting_human`: an opening round leaves the issue unparked by design, so the
# park read below would never see them.
_FROZEN_BY_KEYS: tuple[str, ...] = (
    "read_only_baseline_sha",
    "discussion_round_open",
    "discussion_publishing_sha",
)


def _issue_worktree_number(worktree: Path) -> Optional[int]:
    """Return an issue number only for a valid issue worktree directory."""
    if not worktree.is_dir() or not worktree.name.startswith("issue-"):
        return None
    try:
        return int(worktree.name[len("issue-"):])
    except ValueError:
        return None


def _base_sync_issue(
    gh: _client.GitHubClient, issue_number: int,
) -> Optional[Issue]:
    """Return the issue for a worktree, or None when it is not retrievable."""
    try:
        return gh.get_issue(issue_number)
    except Exception:
        log.debug(
            "issue=#%d not retrievable; skipping base sync", issue_number,
        )
        return None


def _issue_skips_base_sync(
    issue: Issue, issue_number: int, state: _pinned_state.PinnedState,
) -> bool:
    """Apply dispatcher hard-skips and the conversation stage gate.

    Neither conversation stage builds anything in its checkout, so the tree
    under one of their labels is something to read rather than work in
    progress: an inspection target an unsafe park left for an operator, and --
    in the discussion stage, which preserves its tree on every exit -- the tree
    the next round opens on. Rebasing `origin/<base>` over either would rewrite
    the state someone was parked to look at.

    The discussion stage does push, once: the plan its humans confirmed, on the
    branch and at the SHA its own check read. That is the sharper reason to
    stand down rather than a reason not to. A rebase between that reading and
    the push would move the branch off the commit that was validated, and the
    same rebase after publication would move it off the tip the PR is open
    against and the record vouches for.

    The label answers that only while the stage still holds the issue, so the
    park is consulted beside it. An operator's relabel takes the label away a
    full tick before the implementing guard reads the recorded round tip and
    rules on the branch, and this refresh runs first in that tick: a rebase in
    the gap moves the tip off the anchor and the guard convicts a branch
    nobody touched. Its refusal then asks for a reset back to that same
    anchor, which only hands the next tick the same rebase to redo. The
    checkout therefore stays frozen until the guard's own write clears the
    park, from which tick on the branch syncs normally again.

    A discussion round or publication left in flight freezes the branch on the
    same terms and without any park at all. Those records are written before
    the thing they describe, so a tick that died mid-round leaves one standing
    with `awaiting_human` false -- and the commit it died holding is on the
    branch. Rebasing over it moves the tip off the anchor its own stage will
    measure it against, and on a PR-backed issue the PR-aware route would push
    that rewrite over a plan PR the publication may already have opened.

    Clearing the park does not end the freeze, because the guard replaces it
    with `read_only_baseline_sha` -- the tip it certified, which the dev run
    is measured against until that run commits something. A rebase would move
    the branch off that SHA while the inherited commits it names are still
    there, and the spawn path would then read them as a dev run whose
    publication was interrupted and push them without an agent ever running.
    The baseline is retired the moment there is committed work to publish, so
    this holds for the ticks the dev spends answering rather than building.
    """
    skip_label = _labels.hard_skip_control_label(issue)
    if skip_label is not None:
        log.debug(
            "issue=#%d has %r; skipping base sync",
            issue_number,
            skip_label,
        )
        return True
    held = [key for key in _FROZEN_BY_KEYS if state.get(key)]
    if held:
        log.debug(
            "issue=#%d holds unspent read-only state (%s); skipping base sync",
            issue_number, ", ".join(held),
        )
        return True
    park_reason = state.get("park_reason") if state.get("awaiting_human") else None
    for stage_label in _READ_ONLY_STAGE_LABELS:
        if _labels.issue_has_label(issue, stage_label):
            log.debug(
                "issue=#%d has %r label; skipping base sync (read-only stage)",
                issue_number,
                stage_label,
            )
            return True
        if isinstance(park_reason, str) and park_reason.startswith(f"{stage_label}_"):
            log.debug(
                "issue=#%d carries an unconsumed %r park; skipping base sync",
                issue_number,
                park_reason,
            )
            return True
    return False


def _worktree_behind_base(
    spec: config.RepoSpec, worktree: Path, issue_number: int,
) -> Optional[int]:
    """Return the base lag, or None when the comparison cannot be read."""
    base_ref = f"{spec.remote_name}/{spec.base_branch}"
    behind_result = _commands._git(
        "rev-list", "--count", f"HEAD..{base_ref}", cwd=worktree,
    )
    if behind_result.returncode != 0:
        log.debug(
            "issue=#%d skipping base sync: rev-list failed: %s",
            issue_number,
            (behind_result.stderr or "").strip(),
        )
        return None
    try:
        return int((behind_result.stdout or "0").strip() or "0")
    except ValueError:
        return None


def _sync_worktree_with_base(
    gh: _client.GitHubClient, spec: config.RepoSpec, worktree: Path, issue_number: int,
) -> None:
    """Bring one per-issue worktree up to date with the configured base.

    Pre-PR worktrees are rebased locally when clean. PR worktrees always
    reach the PR-aware coordinator so a pinned crash-recovery anchor is
    honored even when local HEAD already contains the latest base.
    """
    issue = _base_sync_issue(gh, issue_number)
    if issue is None:
        return

    state = gh.read_pinned_state(issue)
    if _issue_skips_base_sync(issue, issue_number, state):
        return

    pr_number = state.get("pr_number")
    if pr_number is None and _probes._worktree_dirty_files(worktree):
        log.debug(
            "issue=#%d skipping base sync: worktree has uncommitted changes",
            issue_number,
        )
        return

    behind = _worktree_behind_base(spec, worktree, issue_number)
    if behind is None:
        return
    if pr_number is not None:
        _pr._sync_pr_worktree_to_base(
            gh, spec, issue, state, worktree, int(pr_number), behind,
        )
        return
    if behind:
        _pre_pr._sync_pre_pr_worktree(spec, worktree, issue_number, behind)


def _sync_discovered_worktree(
    gh: _client.GitHubClient,
    spec: config.RepoSpec,
    worktree: Path,
    issue_number: int,
    scheduler: Optional[IssueScheduler],
) -> None:
    """Sync one discovered worktree unless its handler is still active."""
    if scheduler is not None and scheduler.is_active(
        spec.slug, issue_number,
    ):
        log.debug(
            "repo=%s issue=#%d active in scheduler; skipping base "
            "sync until the worker completes", spec.slug, issue_number,
        )
        return
    try:
        _sync_worktree_with_base(gh, spec, worktree, issue_number)
    except Exception:
        log.exception(
            "repo=%s issue=#%d base sync failed; continuing",
            spec.slug, issue_number,
        )


def _refresh_base_and_worktrees(
    gh: _client.GitHubClient,
    spec: config.RepoSpec,
    *,
    scheduler: Optional[IssueScheduler] = None,
) -> None:
    """Fetch `origin/<base>` once for the spec and bring every existing
    per-issue worktree up to date.

    Runs at the start of each tick so a base-branch update on the remote
    propagates into in-flight issue worktrees. The per-stage
    `_ensure_*_worktree` helpers only fetch base on (re)creation, so a
    worktree that survives across ticks would otherwise stay anchored at
    whatever `origin/<base>` looked like when it was first added.

    Two paths depending on whether a PR already exists for the issue:

    * **Pre-PR worktrees** (no `pr_number` in pinned state): rebase
      the local worktree onto `origin/<base>` -- no remote yet, so there
      is nothing to push.

    * **PR-having worktrees** (validating / documenting / in_review /
      fixing): rebasing
      locally WITHOUT pushing would diverge local HEAD from `pr.head.sha` and
      break the validating reviewer (it reads local HEAD, so it would
      review a SHA that isn't on the PR) and
      `_squash_and_force_push`'s `--force-with-lease=<original_head>`
      (the lease compares against the un-rebased remote tip). So
      `_sync_pr_worktree_to_base` attempts the rebase in the refresh
      itself: on a clean rebase it pushes (force-with-lease pinned to
      the pre-rebase SHA), resets `review_round`, and relabels to
      `validating` so the reviewer re-runs against the rewritten
      branch directly; the single docs pass is deferred to the post-
      approval handoff to `documenting` in `_handle_validating`. Only
      when the rebase actually leaves conflicted files does the issue
      get relabeled to `resolving_conflict` -- the
      `_handle_resolving_conflict` handler then drives the dev agent to
      resolve the conflict. Issues already labeled
      `resolving_conflict` are left alone (the handler runs this tick
      anyway); other labels are skipped (no PR worktree to refresh in
      those states).

    Rebase keeps the PR history linear after sibling PRs land. Every
    pushed rebase resets `review_round`, so the reviewer must re-run
    against the rewritten SHA before any merge gate can pass.

    Conflicts on the pre-PR path abort the rebase so the worktree stays
    on its original SHA -- conflict resolution still belongs to
    `_handle_resolving_conflict`. Dirty worktrees are skipped so a
    crash-recovered tree with uncommitted edits is never disturbed
    (mirrors `_on_dirty_worktree`'s rule). All failures are logged at
    info/warning and swallowed: keeping every issue moving matters more
    than perfect base sync.

    `scheduler`, when supplied, is consulted before each per-issue
    worktree sync: an issue whose handler is currently in flight in
    that scheduler is skipped this tick. Without this gate, a polling
    pass can rebase a pre-PR worktree under a still-running agent or
    relabel/state-mutate a PR worktree while its handler is still
    running, racing the base refresh against the live worker. The
    scheduler's `submit` path also rejects a duplicate active issue,
    so the workflow handler itself does not run for the in-flight
    issue this tick -- the refresh skip keeps the worktree contract
    matching that "active issues are skipped until completion"
    guarantee. `None` preserves the legacy behavior so direct test
    invocations that supply no scheduler still refresh every worktree.
    """
    fetch_r = _authentication._authed_target_fetch(spec, spec.base_branch)
    if fetch_r.returncode != 0:
        log.warning(
            "repo=%s base fetch of %s/%s failed: %s",
            spec.slug, spec.remote_name, spec.base_branch,
            (fetch_r.stderr or "").strip(),
        )
        return

    root = _paths._repo_worktrees_root(spec)
    if not root.exists():
        return

    for worktree in sorted(root.iterdir()):
        issue_number = _issue_worktree_number(worktree)
        if issue_number is not None:
            _sync_discovered_worktree(
                gh, spec, worktree, issue_number, scheduler,
            )
