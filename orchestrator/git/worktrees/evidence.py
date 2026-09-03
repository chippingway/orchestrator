# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The reads an artifact has to survive before it can be reclaimed.

Six questions: whether a checkout is carrying anything loose, whether it is
the checkout this issue's own creator made, what its branch is on, what its
HEAD is on, what the remote says a branch is at, and whether the base the
remote named already contains a given tip. What the answers are spent on is
``eligibility``'s subject; what they ARE is this module's.

A checkout's HEAD is asked about beside the branches because it is a tip in
its own right. A linked worktree keeps a HEAD and a reflog no branch has to
back, so a branch deleted out from under one leaves the checkout holding a
commit nothing else names -- and a reclaim that only ever asked about branches
would take it.

The two questions about the remote are put to the remote. A
`refs/remotes/<remote>/<branch>` looks like the remote's answer and is a local
ref in the object store every per-issue worktree shares, so an agent that
repoints `refs/remotes/<remote>/<base>` at its own tip makes an unpublished
branch read as already merged -- and a reclaim measuring against it would
delete the only copy of that work. `branch_transport._remote_branch_tip` asks
over the authenticated transport instead, which is the one answer nothing on
this host can rewrite. It is a read on both sides, so a verdict still leaves
no state behind it anywhere.

Every local read is hardened, for the reason every read of these paths is: the
per-issue checkout is a tree an agent writes in and it shares a clone with
the repository these probes run in, so a planted `core.hooksPath`,
`core.fsmonitor`, or replacement object runs on an ordinary `rev-parse` too.
The clone-side reads take the lock the worktree mutations serialize under, so
a reading cannot land between a `worktree add` and the ref it creates; the
checkout-side ones do not, because what they inspect is one tree rather than
the ref store everybody shares.

Every read is also tri-state, and that is the whole point of the module. The
caller's next step is deleting a branch and a directory, so "this artifact
carries nothing" and "nobody could say what this artifact carries" must not
arrive as one answer -- the first is what reclaims, and a failed read wearing
its clothes is how a probe that never ran becomes the reason work was thrown
away.
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from orchestrator import config
from orchestrator.git import branch_transport, commands, locks
from orchestrator.git.verification import probes as verification_probes
from orchestrator.git.worktrees import paths
from orchestrator.git.worktrees.models import BranchTip, ProbeAnswer

# The channel is named for the worktree-lifecycle domain rather than for this
# module's path: operators filter the rendered `orchestrator.worktree_lifecycle`
# prefix and attach handlers to it, so a read that could not be taken reports
# where their filters already point.
log = logging.getLogger("orchestrator.worktree_lifecycle")

# The exit status git answers a question with when the answer is no, as
# opposed to the ones that mean it could not answer at all. `rev-parse
# --verify --quiet` and `merge-base --is-ancestor` both spell their negative
# this way, and both spell an unreadable repository 128.
_GIT_NEGATIVE = 1

_LOCAL_REF_PREFIX = "refs/heads/"

# What every tip read asks for: the object id, or silence and an exit status
# that says which kind of no this is. Without `--quiet` a ref that does not
# resolve is a complaint on stderr and exit 128, which is the status a
# repository that would not open answers with -- and the two must not arrive
# as one.
_VERIFY_QUIETLY = ("--verify", "--quiet")

_HEAD = "HEAD"


def _hardened_read(
    root: Path, *args: str,
) -> subprocess.CompletedProcess | None:
    """Run one hardened read in `root`, or report that it never ran.

    `None` is the reading that did not happen -- a git that could not be
    spawned, a `root` the host will not run a process in -- as against the
    non-zero result a caller reads off a command that did. Both fail closed
    downstream, but only one of them says anything about the artifact, so
    they are not folded together here.
    """
    try:
        return commands._git_hardened(*args, cwd=root)
    except OSError as spawn_error:
        log.warning("could not run a git read in %s: %s", root, spawn_error)
        return None


def _clone_read(
    spec: config.RepoSpec, *args: str,
) -> subprocess.CompletedProcess | None:
    """The same read against the clone, under the lock its refs move behind.

    Every mutation of this clone's worktrees and branches serializes on that
    lock, so a ref read taken outside it can land between a `worktree add`
    and the branch it creates -- and answer that a branch this orchestrator
    is in the middle of publishing does not exist. The lock is re-entrant, so
    a caller already holding it pays nothing for asking again.
    """
    with locks._target_root_lock(spec.target_root):
        return _hardened_read(spec.target_root, *args)


def _resolved_tip(
    resolved: subprocess.CompletedProcess | None, subject: str,
) -> BranchTip:
    """What one `rev-parse --verify --quiet` established, in three answers.

    `--verify --quiet` is what makes them separable: git exits 0 with the
    object id on stdout, 1 with nothing when what was named does not resolve,
    and 128 when the repository itself would not answer. A caller that only
    tested for a non-zero exit would read the last as the second and reclaim
    an artifact on the strength of a repository it could not open.

    Every caller here names a ref in full or names `HEAD`, so a branch named
    like an option cannot be read as one and a branch sharing a tag's name
    cannot be resolved to the tag instead. An exit of 0 with nothing on stdout
    is not a reading either -- nothing here produces it, which is exactly why
    it is answered as the failure it would be.
    """
    if resolved is None:
        return BranchTip(answer=ProbeAnswer.UNREADABLE)
    if resolved.returncode == _GIT_NEGATIVE:
        return BranchTip(answer=ProbeAnswer.REFUTED)
    tip_sha = (resolved.stdout or "").strip()
    if resolved.returncode != 0 or not tip_sha:
        log.debug(
            "could not resolve %s: %s",
            subject, (resolved.stderr or "").strip(),
        )
        return BranchTip(answer=ProbeAnswer.UNREADABLE)
    return BranchTip(answer=ProbeAnswer.CONFIRMED, sha=tip_sha)


def _local_branch_tip(spec: config.RepoSpec, branch: str) -> BranchTip:
    """The commit one local branch in this clone stands on.

    The commit rather than a count of what the branch is ahead by, because
    everything the caller asks next is asked about an object id: whether the
    base contains it, whether the remote is standing on it, whether a pull
    request was made of it. A count answers none of those and cannot be
    compared against anything a pull request reports.

    `REFUTED` is the branch not being there. The scan named it a moment
    earlier, so between the two reads it was deleted -- by a human, by
    another tick's teardown -- which leaves nothing to reclaim rather than
    something to protect.
    """
    ref = f"{_LOCAL_REF_PREFIX}{branch}"
    return _resolved_tip(
        _clone_read(spec, "rev-parse", *_VERIFY_QUIETLY, ref),
        f"{ref} in {spec.target_root}",
    )


def _checkout_tip(worktree: Path) -> BranchTip:
    """The commit this checkout's HEAD stands on.

    What removing the checkout would take with it. A linked worktree keeps a
    HEAD and a reflog of its own, and when no ref points at the commit HEAD
    names -- a branch deleted out from under a live checkout, which git
    permits through `update-ref` -- those two are the only things keeping that
    commit reachable. The removal takes both.

    `REFUTED` is a HEAD that names no commit, which is that exact state: the
    symbolic ref is still there and still spells this issue's branch, so every
    reading of WHOSE checkout it is comes back the same, and only resolving it
    says that what it holds cannot be named. `UNREADABLE` is the read that
    could not say either way. Both leave a caller nothing to prove the commit
    with, which is not the same as proving there is nothing to lose.
    """
    return _resolved_tip(
        _hardened_read(worktree, "rev-parse", *_VERIFY_QUIETLY, _HEAD),
        f"HEAD in {worktree}",
    )


def _published_tip(spec: config.RepoSpec, branch: str) -> BranchTip:
    """What the REMOTE says one branch is at, ignoring every local ref.

    The evidence a reclaim is entitled to lean on, and the reason it is not
    read off `refs/remotes/<remote>/<branch>`: that ref is local, it lives in
    the object store every per-issue worktree shares, and an agent can point
    it wherever it likes. Asked of the mirror, a branch that was never pushed
    anywhere reads as one the remote agrees with, and a base repointed onto an
    agent's own tip reads as a base that carries its work.

    Its three answers are the transport's own, mapped: `None` is a read that
    established nothing -- no token, a repository whose config could hijack
    the transport, an unreachable remote -- and the empty string is the remote
    answering that it does not carry this branch. That second one is the
    ordinary terminal shape rather than a problem: a merged pull request's
    head branch is deleted there.

    The clone is named as the tree the read runs in, so the transport-config
    refusal in front of it inspects the repository this classification is
    about rather than a per-issue checkout that may already be gone.

    The transport answers with `None` for the failures it recognizes and
    raises for the ones underneath them -- a git that cannot be spawned, a
    clone that has been removed since the scan named it, an askpass script
    the host would not let this process write. Those are the same answer to
    this caller, and the boundary is here rather than left to the caller
    because a probe whose contract is three answers must not have a fourth:
    an exception out of a classification takes down every other candidate in
    the pass along with this one.
    """
    try:
        published = branch_transport._remote_branch_tip(
            spec, spec.target_root, branch,
        )
    except Exception:
        log.warning(
            "could not ask the remote what %r is at from %s",
            branch, spec.target_root, exc_info=True,
        )
        return BranchTip(answer=ProbeAnswer.UNREADABLE)
    if published is None:
        return BranchTip(answer=ProbeAnswer.UNREADABLE)
    if not published:
        return BranchTip(answer=ProbeAnswer.REFUTED)
    return BranchTip(answer=ProbeAnswer.CONFIRMED, sha=published)


def _base_contains(
    spec: config.RepoSpec, base: BranchTip, revision: str,
) -> ProbeAnswer:
    """Whether the base the remote named already carries `revision`.

    The proof that an artifact's commits are not lost by deleting it: a tip
    the base contains is work that has already landed, whatever route it took
    to get there. BOTH ends are things the caller established -- the base from
    the remote itself, the tip from the artifact that is about to go -- so
    nothing an agent can write decides the answer. Naming
    `refs/remotes/<remote>/<base>` here instead would hand that decision back
    to the object store the agent shares.

    A base the remote would not answer for, and one it says does not exist,
    arrive where a comparison that could not be taken arrives: there is
    nothing to measure against, so nothing about the revision is established.
    That is decided here rather than by each caller, so no caller can reach
    the comparison holding a base nobody named.

    The comparison itself is local, and it is sound there: ancestry between
    two object ids is content-addressed, and the hardened envelope turns off
    the two ways a repository can be told to serve one commit under another's
    name.

    `REFUTED` is git's own no. Anything else -- a base commit this clone has
    not fetched, a revision it cannot resolve, a repository that would not
    open -- is `UNREADABLE`, since none of them establishes that the base
    carries the commit and none of them establishes that it does not.
    """
    if base.answer is not ProbeAnswer.CONFIRMED:
        return ProbeAnswer.UNREADABLE
    contained = _clone_read(
        spec, "merge-base", "--is-ancestor", revision, base.sha,
    )
    if contained is None:
        return ProbeAnswer.UNREADABLE
    if contained.returncode == 0:
        return ProbeAnswer.CONFIRMED
    if contained.returncode == _GIT_NEGATIVE:
        return ProbeAnswer.REFUTED
    log.debug(
        "could not measure %s against %s in %s: %s",
        revision, base.sha, spec.target_root, (contained.stderr or "").strip(),
    )
    return ProbeAnswer.UNREADABLE


def _clean_worktree(worktree: Path) -> ProbeAnswer:
    """Whether this checkout PROVED it is carrying nothing loose.

    Read through the verification probe rather than a `status` of its own,
    because that owner is where the ways a clean answer can be arranged are
    already handled: the tree is named on the command line so per-worktree
    `core.worktree` cannot redirect the read, untracked files and submodules
    are asked for explicitly so local config cannot hide them, the report is
    NUL-delimited so a path cannot be read as rename syntax, and the index is
    asked whether it has been told to stop comparing entries at all.

    Its `readable` flag is what separates the two negatives here. A tree
    whose status could not be taken -- and a tree whose index carries a
    suppressed entry, which that owner reports the same way -- is
    `UNREADABLE`, never `REFUTED`: nothing was established about what the
    checkout holds, and a reclamation that read it as merely dirty would go
    on to say so as though somebody had looked.

    A checkout the read cannot reach is answered the same way rather than
    raised over, and the boundary is total because the ways it fails are not
    all of one kind. The scan named the directory some moments earlier and an
    agent owns what is under it, so by now the path can be gone -- which fails
    the spawn with an `OSError` -- or be a symlink loop, which fails in the
    `Path.resolve` behind the `--work-tree` argument and fails as a
    `RuntimeError` on Python 3.12 while merely coming back unchanged on 3.13.
    A probe whose contract is three answers may not have a fourth: an
    exception out of one candidate's tree ends the pass for every other
    candidate in it, which is the one way an unreadable checkout can cost more
    than the artifact it is about.
    """
    try:
        status = verification_probes._worktree_status(worktree)
    except Exception:
        log.warning(
            "the checkout %s could not be reached", worktree, exc_info=True,
        )
        return ProbeAnswer.UNREADABLE
    if not status.readable:
        log.debug("the checkout %s would not report its status", worktree)
        return ProbeAnswer.UNREADABLE
    if status.paths:
        return ProbeAnswer.REFUTED
    return ProbeAnswer.CONFIRMED


def _common_git_dir(root: Path) -> Path | None:
    """The one git directory a checkout or a clone shares, or None.

    What makes two paths the same repository: a linked worktree has a git
    directory of its own, and the store it is registered in is the parent's
    -- so the common directory is the only spelling that answers equal for a
    checkout and the clone that created it.

    Resolved against the directory the read ran in rather than asked for
    absolutely, because git answers this one relatively whenever it can and
    the two spellings would otherwise compare unequal for a healthy checkout.
    A path that will not resolve at all is answered `None` for the reason the
    scan answers its own root that way: the failure is version-dependent and
    a caller must not read it as a repository identity that was established.
    """
    located = _hardened_read(root, "rev-parse", "--git-common-dir")
    if located is None or located.returncode != 0:
        return None
    common_dir = (located.stdout or "").strip()
    if not common_dir:
        return None
    try:
        return (root / common_dir).resolve()
    except (OSError, RuntimeError) as resolve_error:
        log.debug(
            "could not resolve the git directory of %s: %s",
            root, resolve_error,
        )
        return None


def _shared_repository(spec: config.RepoSpec, worktree: Path) -> ProbeAnswer:
    """Whether this checkout is a worktree of the configured clone.

    A directory sitting at the path this issue's checkout belongs at is not
    the checkout: an agent can run `git init` in it, an operator can park an
    unrelated clone there, and a reclaim that read the path as the identity
    would take a repository this orchestrator never created. What answers is
    the store the two share -- a linked worktree keeps its own git directory
    and registers it under the parent's, so the common directory is the one
    spelling that comes back equal for a checkout and the clone that made it.
    """
    checkout_dir = _common_git_dir(worktree)
    clone_dir = _common_git_dir(spec.target_root)
    if checkout_dir is None or clone_dir is None:
        return ProbeAnswer.UNREADABLE
    if checkout_dir != clone_dir:
        return ProbeAnswer.REFUTED
    return ProbeAnswer.CONFIRMED


def _head_ref(worktree: Path) -> tuple[ProbeAnswer, str]:
    """Whether this checkout's HEAD is on a branch, and which one.

    The pair rather than either half alone, because one read answers two
    questions its callers ask separately: whether the tree belongs to this
    issue at all, and -- once it does -- which branch to ask the remote and
    GitHub about the commit under it. A caller that only ever got the verdict
    would have to read HEAD a second time to learn the name.

    A detached HEAD is `REFUTED` rather than unreadable: `symbolic-ref
    --quiet` spells it as the plain no it is, and every checkout the issue
    creators make is on a branch. What made it detached is somebody else's
    doing, and a commit sitting on no branch is exactly the work a reclaim
    must not take.

    The name comes back stripped of `refs/heads/`, which is how every
    derivation in ``paths`` spells a branch, so it can be compared against
    them and handed to a lookup without either side adjusting it.
    """
    head = _hardened_read(worktree, "symbolic-ref", "--quiet", _HEAD)
    if head is None:
        return ProbeAnswer.UNREADABLE, ""
    if head.returncode == _GIT_NEGATIVE:
        return ProbeAnswer.REFUTED, ""
    named = (head.stdout or "").strip()
    if head.returncode != 0 or not named.startswith(_LOCAL_REF_PREFIX):
        log.debug(
            "could not read the HEAD of %s: %s",
            worktree, (head.stderr or "").strip(),
        )
        return ProbeAnswer.UNREADABLE, ""
    return ProbeAnswer.CONFIRMED, named[len(_LOCAL_REF_PREFIX):]


def _head_is_own_branch(
    spec: config.RepoSpec, issue_number: int, worktree: Path,
) -> ProbeAnswer:
    """Whether this checkout's HEAD is on a branch this issue publishes under.

    The half of the identity that says the tree belongs to this issue rather
    than to whatever was checked out into it afterwards. Both names one issue
    can be published under are accepted, since a checkout made before slug
    namespacing landed is still on the flat one.
    """
    answer, branch = _head_ref(worktree)
    if answer is not ProbeAnswer.CONFIRMED:
        return answer
    if branch not in paths._issue_branch_names(spec, issue_number):
        return ProbeAnswer.REFUTED
    return ProbeAnswer.CONFIRMED


def _checkout_identity(
    spec: config.RepoSpec, issue_number: int, worktree: Path,
) -> ProbeAnswer:
    """Whether this checkout is the one this issue's own creator made.

    Both halves have to hold and neither implies the other: a worktree of the
    configured clone can be sitting on any branch in it, and a HEAD naming
    this issue's branch can belong to a repository somebody else made. The
    repository is asked first, because a HEAD read against a tree that is not
    ours answers about a ref store this classification is not entitled to
    reason about.
    """
    shared = _shared_repository(spec, worktree)
    if shared is not ProbeAnswer.CONFIRMED:
        return shared
    return _head_is_own_branch(spec, issue_number, worktree)
