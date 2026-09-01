# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Issue and PR worktree creation plus the unpushed-work probe they gate on.

Both creators open with the same question -- does the worktree already on
disk still carry commits the orchestrator never pushed? -- and
`_has_new_commits` is the answer. The probe lives beside its only two
callers because the reuse decision and the destructive `worktree remove`
that follows it are one unit; the creators diverge only in which ref a
missing local branch is restored from.

That reuse deliberately never moves a checkout it keeps: the commits it
preserves are work no push has published yet, and the whole point is that
nothing overwrites them. `_anchor_pr_worktree` is the one exception, and it is
not part of either creator for that reason -- it exists for the caller that has
already proved the checkout carries nothing of its own and needs the branch
brought forward onto the head a PR is really open against. It answers with the
tip the branch ended up on, or with nothing at all. The restore above reserves
the base for a branch the REMOTE says is gone, because a fetch that merely
failed leaves the same gap and rebuilding a live PR at base is how its commits
get force-pushed away; the anchor reserves it for the caller that names no head
at all, since only that caller has established the pull request is over and its
work is in the base. And the base they fall back to is one this
tick fetched or none at all: a cached ref names the base as of the last fetch
that worked, which for work that has only just merged is a base without it.
"""
from __future__ import annotations

import logging
from pathlib import Path

from orchestrator import config
from orchestrator.git import authentication, commands, locks
from orchestrator.git.worktrees import paths, recovery

# The channel is named for the worktree-lifecycle domain rather than for
# this module's path: operators filter the rendered
# `orchestrator.worktree_lifecycle` prefix and attach handlers to it, so
# every owner in this package reports where their filters already point.
log = logging.getLogger("orchestrator.worktree_lifecycle")

# The ref-existence probe every path here gates on, spelled once: three of
# them ask it, and a typo in any one would read as "that ref is gone".
_VERIFY_REF = ("rev-parse", "--verify", "--quiet")

_WORKTREE_ADD = ("worktree", "add")

_WORKTREE_REMOVE_FORCE = ("worktree", "remove", "--force")


def _ensure_worktree(
    spec: config.RepoSpec, issue_number: int, *, branch: str | None = None,
) -> Path:
    """Return a worktree on a per-issue branch, reusing one with unpushed work.

    The reuse is what lets the orchestrator survive a crash between codex
    committing and the orchestrator pushing -- without it, the next tick would
    wipe the worktree and we'd burn another codex run on the same prompt.

    `branch` overrides the default `_branch_name(spec, issue_number)`
    derivation so callers can anchor on an already-pinned branch (e.g.
    a legacy `orchestrator/issue-<n>` ref kept in pinned state when
    slug-namespacing landed) instead of forcing the issue onto a new
    branch and orphaning its existing PR.

    All git operations target `spec.target_root` and therefore mutate the
    parent clone's `.git/config`. The per-target_root lock (see
    `_target_root_lock`) serializes concurrent workers so two tick fan-out
    threads cannot collide on `.git/config.lock`. The lock is released
    before the caller starts the long-running agent run.
    """
    with locks._target_root_lock(spec.target_root):
        paths._repo_worktrees_root(spec).mkdir(parents=True, exist_ok=True)
        wt = paths._worktree_path(spec, issue_number)
        if branch is None:
            branch = paths._branch_name(spec, issue_number)

        if wt.exists():
            if _has_new_commits(spec, wt):
                log.info(
                    "issue=#%d worktree has unpushed commits; reusing",
                    issue_number,
                )
                return wt
            commands._git(
                *_WORKTREE_REMOVE_FORCE, str(wt),
                cwd=spec.target_root,
            )

        authentication._authed_target_fetch(spec, spec.base_branch)

        have_branch = commands._git(
            *_VERIFY_REF, branch, cwd=spec.target_root,
        ).returncode == 0
        if have_branch:
            worktree_result = commands._git(
                *_WORKTREE_ADD, str(wt), branch, cwd=spec.target_root,
            )
        else:
            worktree_result = commands._git(
                *_WORKTREE_ADD, "-b", branch, str(wt),
                f"{spec.remote_name}/{spec.base_branch}",
                cwd=spec.target_root,
            )
        if worktree_result.returncode != 0:
            raise RuntimeError(
                f"git worktree add failed: {worktree_result.stderr}"
            )
        return wt


def _ensure_pr_worktree(
    spec: config.RepoSpec, issue_number: int, *, branch: str | None = None,
) -> Path:
    """Like `_ensure_worktree`, but restores the local branch from
    `origin/<branch>` when it is missing instead of branching from
    `origin/<base>`.

    `_ensure_worktree`'s fallback (`worktree add -b <branch> ... origin/<base>`)
    is right for a fresh implementing run -- a brand-new PR branch should
    start at the base. It is the WRONG fallback for `_handle_resolving_conflict`:
    once a PR exists, the conflict resolver MUST land on the same branch
    the PR is open against, with the dev's commits intact. A host
    restart, manual cleanup, or `git branch -D` between ticks deletes
    the local ref but leaves the PR's `origin/<branch>` ref alive on
    GitHub; rebuilding off `origin/<base>` would silently discard the
    PR's commits and leave the PR's conflicts unresolved forever.

    The base fallback comes back only when the REMOTE says the branch is
    gone, because then there is nothing left to discard. A local ref
    that is merely missing does not say that, and neither does a
    remote-tracking ref left behind by a fetch that failed. A merged PR whose branch GitHub
    auto-deleted is the case that matters: the issue keeps its
    `pr_number`, so every later tick routes here, and on a host that no
    longer has the local ref -- a fresh clone, an operator's cleanup --
    a hard failure would raise on every tick and the implementer would
    never run again. Whatever that branch carried is in the base by
    then, or was closed unmerged and is unreachable either way, so the
    checkout is rebuilt at the base and the dev starts from what landed.

    All git invocations run from `spec.target_root` (the orchestrator's
    own clone, not the agent-writable worktree) so authenticated fetch
    uses the operator's git config / credential helpers / SSH keys
    directly. The transport hardening that `_push_branch` applies is
    unnecessary for these, which carry no token of their own: the fetch
    that does goes through `authentication`, which hardens itself. What a
    linked worktree CAN reach in the parent clone is why the anchor below
    hardens the operations that write there.

    Serialized by the per-target_root lock for the same `.git/config.lock`
    reason described on `_ensure_worktree`.
    """
    with locks._target_root_lock(spec.target_root):
        paths._repo_worktrees_root(spec).mkdir(parents=True, exist_ok=True)
        wt = paths._worktree_path(spec, issue_number)
        if branch is None:
            branch = paths._branch_name(spec, issue_number)

        if wt.exists():
            if _has_new_commits(spec, wt):
                log.info(
                    "issue=#%d worktree has unpushed commits; reusing",
                    issue_number,
                )
                return wt
            commands._git(
                *_WORKTREE_REMOVE_FORCE, str(wt),
                cwd=spec.target_root,
            )

        # Fetch both base and the PR's remote branch so either path
        # below has a fresh ref to anchor on. The base fetch decides
        # nothing on its own, but the branch fetch decides everything:
        # `refs/remotes/<remote>/<branch>` outlives the fetch that wrote
        # it, so a fetch that failed leaves a ref that still resolves and
        # still looks like the PR's head while naming whatever the last
        # successful fetch saw. The start point below is told whether
        # this one landed for exactly that reason.
        # `_authed_target_fetch` already uses the explicit
        # `+refs/heads/<branch>:refs/remotes/<remote>/<branch>` refspec
        # so single-branch / narrowed clones still create the
        # remote-tracking ref the `worktree add ... <remote>/<branch>`
        # fallback anchors on; the `+` prefix forces non-fast-forward
        # update against `--force-with-lease`-rewritten remote tips.
        _fetch_for_restore(spec, issue_number, spec.base_branch)
        fetched = _fetch_for_restore(spec, issue_number, branch)

        have_local = commands._git(
            *_VERIFY_REF, branch, cwd=spec.target_root,
        ).returncode == 0
        if have_local:
            worktree_result = commands._git(
                *_WORKTREE_ADD, str(wt), branch, cwd=spec.target_root,
            )
        else:
            worktree_result = commands._git(
                *_WORKTREE_ADD, "-b", branch, str(wt),
                _pr_branch_start_point(spec, issue_number, branch, fetched),
                cwd=spec.target_root,
            )
        if worktree_result.returncode != 0:
            raise RuntimeError(
                f"git worktree add failed: {worktree_result.stderr}"
            )
        return wt


def _fetch_for_restore(
    spec: config.RepoSpec, issue_number: int, branch: str,
) -> bool:
    """Fetch one ref a checkout may be restored from, saying so when it fails.

    Neither of these fetches gates the restore -- the ref checks below decide --
    but a silent failure is what turns a network blip into a checkout rebuilt
    from the wrong place, so it is logged where an operator reading the tick can
    see it beside the decision it feeds.
    """
    fetch_result = authentication._authed_target_fetch(spec, branch)
    if fetch_result.returncode != 0:
        log.warning(
            "issue=#%d fetch of %s failed while restoring the checkout: %s",
            issue_number, branch, (fetch_result.stderr or "").strip(),
        )
    return fetch_result.returncode == 0


def _pr_branch_start_point(
    spec: config.RepoSpec, issue_number: int, branch: str, fetched: bool,
) -> str:
    """Where a PR branch with no local ref left is rebuilt from.

    The PR's own remote head, whenever the remote still has one AND this tick
    just fetched it: the dev's commits live there and only there once the local
    ref is gone, so anchoring on `<remote>/<base>` would hand back a checkout
    the PR's work is missing from -- and the publication that follows would
    force-push that over the PR.

    `fetched` is what makes that ref worth anchoring on. A remote-tracking ref
    outlives the fetch that wrote it, so one left behind by a fetch that failed
    resolves perfectly well and names whatever the last successful fetch saw --
    which on an interrupted publication can be the tip the round opened on.
    Restored there, the recovery reads a branch back at its anchor, retires the
    marker as an operator's reset, and lets the conversation open another round
    while the plan sits published on a pull request nobody recorded. So an
    unrefreshed ref is not used at all: what happens next is decided by asking
    the remote, exactly as a missing ref is.

    The base is the answer only when the remote ITSELF says there is no such
    branch, and then it is the only answer there is. A merged PR whose branch
    GitHub auto-deleted keeps its `pr_number` on the issue, so every later tick
    comes here; naming a ref neither side has would fail the `worktree add` on
    every one of them and the issue would retry forever without an implementer
    ever running.

    A missing remote-tracking ref is NOT that answer on its own. A fetch that
    could not run leaves exactly the same gap -- an expired token, a remote that
    was unreachable, a host that has never fetched this branch -- and reading it
    as a deletion rebuilds a live PR at base, hands the developer a tree its
    commits are missing from, and force-pushes that over the PR. So the remote
    is asked, and only "no such ref" is absence: an unanswerable read or a
    branch that is plainly still there raises instead, leaving the checkout,
    the branch, and the PR exactly as they were for the next tick to retry.
    """
    pr_ref = f"{spec.remote_name}/{branch}"
    have_remote = fetched and commands._git(
        *_VERIFY_REF, f"refs/remotes/{pr_ref}", cwd=spec.target_root,
    ).returncode == 0
    if have_remote:
        return pr_ref
    remote_tip = authentication._remote_branch_tip(
        spec, spec.target_root, branch,
    )
    if remote_tip is None:
        raise RuntimeError(
            f"cannot restore {branch}: no local ref, no fresh {pr_ref}, and "
            "the remote could not be asked whether that branch still exists",
        )
    if remote_tip:
        raise RuntimeError(
            f"cannot restore {branch}: no local ref and no fresh {pr_ref}, "
            f"but the remote still has that branch at {remote_tip}",
        )
    log.warning(
        "issue=#%d has no local %s and the remote has no such branch; "
        "rebuilding the checkout from %s/%s -- a merged PR's branch is "
        "deleted and what it carried is in the base", issue_number, branch,
        spec.remote_name, spec.base_branch,
    )
    return f"{spec.remote_name}/{spec.base_branch}"


def _anchor_pr_worktree(
    spec: config.RepoSpec, issue_number: int, *, branch: str, head_sha: str,
) -> str | None:
    """Bring the per-issue branch, and its checkout, onto a PR's own head.

    For the one handoff where the remote is ahead of everything local for a
    reason nothing here can see: a human edited the design on the plan PR the
    `discussion` stage opened, or merged the base into that branch to make it
    mergeable, while the checkout the conversation ran in still sits on the
    commit this orchestrator published. Left there, the developer builds on a
    plan the humans have moved past, and the push that follows sends a tip that
    does not contain the head they reviewed at the branch that head is on --
    where the lease, measured against a remote ref this branch simply does not
    descend from, is the only thing between an amendment and being overwritten.

    Only for a caller that has already established the checkout is clean and
    sitting exactly where it certified. The reuse paths above must never do
    this: what they keep is unpushed local work, and a reset there would destroy
    the very commits the reuse exists to preserve.

    Returns the SHA the branch now sits at, which is what the caller records as
    the tip the work that follows starts from -- the reviewed head normally, and
    the base when that head is gone along with its branch. None means nothing
    moved and nothing could be established, and the caller must not treat the
    handoff as taken: the checkout is still on a commit the reviewers have moved
    past, and a push from it would take their work with it.

    `head_sha` is what the caller read off GitHub before this ran, so it is
    checked against the remote here rather than taken on trust. A head the
    humans pushed in between is exactly the state this exists to protect, and it
    arrives looking like success -- the fetch brings their commit, and the one
    the caller named still resolves underneath it.

    An EMPTY `head_sha` asks for the base outright, and it is how a caller says
    the pull request is over: a merged plan is in the base along with everything
    else that landed while it was open, so leaving the checkout on the commit
    that merged would start the developer behind the branch they are building
    for.
    """
    with locks._target_root_lock(spec.target_root):
        _fetch_for_restore(spec, issue_number, branch)
        target = _anchor_target(spec, issue_number, branch, head_sha)
        if target is None:
            return None
        if not _move_branch_onto(spec, issue_number, branch, target):
            return None
        return target


def _anchor_target(
    spec: config.RepoSpec, issue_number: int, branch: str, head_sha: str,
) -> str | None:
    """The commit the branch has to end up on, or None when nothing says which.

    A caller that names no head at all has said the pull request is finished,
    and the base is the answer without the remote being asked about the branch
    at all -- though the base itself still has to be brought forward before it
    can stand in for what merged.

    Otherwise the remote decides, and it is asked FIRST rather than only when
    something is missing locally. `head_sha` was read off GitHub a moment ago,
    and the humans can push to that branch in the moment between: the fetch
    above then brings their commit and leaves the reviewed one resolving
    perfectly well underneath it as an ancestor, so "the object is here" would
    anchor the branch on a head the pull request has already moved past. The
    developer would build on it, and the push that follows takes a lease read
    live off the remote -- so it matches the commit nobody here has seen and
    overwrites it. Only a remote still ON that head says the reading the caller
    made is still the reading that holds.

    A branch the remote no longer has does NOT fall back to the base once a
    head is named, and this is the difference between the two ways a pull
    request ends. The caller that knows the design landed says so by naming no
    head at all, and only that caller gets the base. A named head with the
    branch gone is a pull request somebody closed and cleaned up after -- what
    it carried went with the branch, and it is nowhere in the base -- so
    anchoring there would retire the plan records and start the developer from
    a base the plan was never in. Nothing was established, and the caller is
    told so.

    That is the same answer a branch the remote has MOVED, one it could not be
    asked about, and a head it still names that this host could not fetch all
    get: no ref may be moved on the strength of any of them, so the handoff
    waits and the next tick reads the pull request again.
    """
    if not head_sha:
        return _base_anchor(spec, issue_number, branch)
    remote_tip = authentication._remote_branch_tip(
        spec, spec.target_root, branch,
    )
    if remote_tip != head_sha:
        log.warning(
            "issue=#%d cannot anchor %s on %s: the remote %s",
            issue_number, branch, head_sha,
            _unanchorable_branch_reading(remote_tip),
        )
        return None
    if not _resolved_commit(spec, f"{head_sha}^{{commit}}"):
        log.warning(
            "issue=#%d cannot anchor %s on %s: the remote is still on that "
            "commit but this host could not fetch it",
            issue_number, branch, head_sha,
        )
        return None
    return head_sha


def _unanchorable_branch_reading(remote_tip: str | None) -> str:
    """Say which of the three the remote gave, since the remedy differs.

    A branch that moved is a head to re-read next tick; one the remote could
    not be asked about is a reading to take again; one it no longer has at all
    is a pull request somebody closed and deleted the branch of, which no tick
    will ever resolve on its own -- and an operator reading this is the only
    thing that can.
    """
    if remote_tip is None:
        return "could not be asked about the branch"
    if not remote_tip:
        return (
            "no longer has that branch at all, so what it carried is not in "
            "the base and there is nothing to anchor on"
        )
    return f"has moved that branch on to {remote_tip}"


def _base_anchor(
    spec: config.RepoSpec, issue_number: int, branch: str,
) -> str | None:
    """The base tip, freshly fetched, as the commit a finished PR ends on.

    Fetched here rather than trusted, and the fetch DECIDES, because this is the
    answer for a branch whose own pull request is over: what the developer
    starts from has to be the base as it stands now, not as it stood when this
    clone last looked. A remote-tracking ref outlives the fetch that wrote it,
    so one a failure left behind resolves perfectly well and names the base from
    before the merge -- which for a plan that just landed is the one base the
    plan is not in. Anchored there, the handoff retires the plan records and
    spawns the developer without the artifact its humans approved, on a checkout
    that never carried it.

    A refresh that did not run therefore establishes nothing, and the caller is
    told so rather than handed a commit: the handoff stays pending, the checkout
    stays where it is, and the next tick fetches again.
    """
    if not _fetch_for_restore(spec, issue_number, spec.base_branch):
        log.warning(
            "issue=#%d cannot anchor %s on the base: its refresh failed, so "
            "%s/%s names the base only as this clone last saw it",
            issue_number, branch, spec.remote_name, spec.base_branch,
        )
        return None
    base_ref = f"refs/remotes/{spec.remote_name}/{spec.base_branch}"
    log.info(
        "issue=#%d anchoring %s on %s: its pull request is over, so what it "
        "carried is in the base", issue_number, branch, base_ref,
    )
    return _resolved_commit(spec, base_ref) or None


def _resolved_commit(spec: config.RepoSpec, revision: str) -> str:
    """The SHA a revision names in the parent clone, or '' when it names none."""
    resolved = commands._git_hardened(
        *_VERIFY_REF, revision, cwd=spec.target_root,
    )
    if resolved.returncode != 0:
        return ""
    return (resolved.stdout or "").strip()


def _move_branch_onto(
    spec: config.RepoSpec, issue_number: int, branch: str, head_sha: str,
) -> bool:
    """Move the branch to `head_sha`, taking its checkout with it.

    A checkout on disk is reset rather than the ref rewritten under it: moving
    the ref alone would leave the tree it belongs to a commit behind, so the
    difference would read as uncommitted local edits and the next probe would
    call the tree dirty. Only a branch with no worktree of its own is moved as
    a ref.

    Both go through the hardened envelope, like every other reset in this
    repository, because both run over a repository an agent has had. The
    checkout is its own writable tree, and a linked worktree can write the
    common repo it shares -- so `core.fsmonitor` on the index refresh a reset
    performs, a `reference-transaction` hook on the ref update either one makes,
    and a planted replacement object behind the SHA being moved onto are all
    reachable from here, and would otherwise run with this process's
    environment attached.

    The reset also NAMES the tree it is aimed at, because that is the one thing
    the envelope cannot override. `core.worktree` in the per-worktree config --
    which an agent enables by writing `extensions.worktreeConfig` into the repo
    its checkout shares -- points every path operation at another directory,
    and a `-c` on the command line does not win against it. Left to discovery,
    the reset reports success and moves the ref while writing the reviewed
    commit's files into whatever directory it was pointed at: the issue's
    checkout stays on the plan it had, the caller records a baseline the tree
    does not match, and somebody else's files are overwritten on the way past.
    """
    worktree = paths._worktree_path(spec, issue_number)
    if worktree.exists():
        moved = commands._git_hardened(
            commands._work_tree_arg(worktree),
            "reset", "--hard", head_sha, cwd=worktree,
        )
    else:
        moved = commands._git_hardened(
            "update-ref", f"refs/heads/{branch}", head_sha,
            cwd=spec.target_root,
        )
    if moved.returncode != 0:
        log.warning(
            "issue=#%d could not put %s on %s: %s",
            issue_number, branch, head_sha, (moved.stderr or "").strip(),
        )
        return False
    log.info(
        "issue=#%d anchored %s on the reviewed head %s",
        issue_number, branch, head_sha,
    )
    return True


def _has_new_commits(spec: config.RepoSpec, worktree: Path) -> bool:
    commit_count_result = commands._git(
        "rev-list", "--count",
        f"{spec.remote_name}/{spec.base_branch}..HEAD",
        cwd=worktree,
    )
    if commit_count_result.returncode != 0:
        return False
    return recovery._commit_count_from_stdout(commit_count_result) > 0
