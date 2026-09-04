# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The local reads a per-issue artifact scan is assembled from.

What this host holds for an issue is a branch in the clone's
`refs/heads/orchestrator/` namespace and a checkout under one of two roots:
the spec's own worktrees directory, and -- for an issue that was in flight
before the slug went into the path -- the flat `WORKTREES_DIR` every entry
once shared. All of that is read here, and none of it writes, fetches, or asks
GitHub anything: the scan above exists to answer from artifacts alone, so an
issue nobody remembers is still found by what it left behind.

One read here is not a listing at all. A checkout under the flat root carries
nothing in its name saying whose it is, so the scan has to ask the directory
itself which clone it is a worktree of -- the same identity the classification
tests a named checkout by, which is why the read lives here for both of them
rather than twice.

Every listing fails closed, and for the same reason. A directory that could
not be listed and a ref store that could not be read are answered with `None`
rather than with the empty answer they resemble, because emptiness is what a
caller spends to conclude that a repository is holding nothing -- and a scan
that reports a clone as artifact-free because git could not be run is the
reading that costs an issue its branch. A reading that came back short of what
is there is answered the same way, since nothing in it says that it is short.
An absence that was actually established, on the other hand, is a real answer
and is returned as one.

Only `refs/heads/` is walked. The snapshot refs this orchestrator also writes
live outside it by design, so they are not something this scan has to know
about, let alone exclude.
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from stat import S_ISDIR

from orchestrator import config
from orchestrator.git import commands, locks
from orchestrator.git.worktrees import paths

# The channel is named for the worktree-lifecycle domain rather than for this
# module's path: operators filter the rendered `orchestrator.worktree_lifecycle`
# prefix and attach handlers to it, so an unreadable clone reports where their
# filters already point.
log = logging.getLogger("orchestrator.worktree_lifecycle")

# The namespace every branch this orchestrator publishes lives under, in the
# pattern form `for-each-ref` matches by: a trailing separator so the ref
# `refs/heads/orchestrator` itself, were somebody to create it, is not one of
# the branches beneath it.
_ORCHESTRATOR_BRANCH_REFS = "refs/heads/orchestrator/"

_LOCAL_BRANCH_PREFIX = "refs/heads/"


def _read_orchestrator_refs(root: Path) -> subprocess.CompletedProcess | None:
    """Run the branch listing in one clone, or report that it could not run.

    Hardened and lock-held for the reasons every read of this clone is: the
    worktrees hanging off it are trees agents write in, and a planted
    `core.hooksPath` or `core.fsmonitor` runs on an ordinary read too. The
    lock is the one the worktree mutations serialize under, so a listing
    cannot land between a `worktree add` and the ref it creates.

    `None` is the reading that never happened at all -- a `root` that is not
    a directory, a git that could not be spawned -- as opposed to the
    non-zero result the caller reads off a listing that ran.
    """
    try:
        with locks._target_root_lock(root):
            return commands._git_hardened(
                "for-each-ref",
                "--format=%(refname)",
                "--end-of-options",
                _ORCHESTRATOR_BRANCH_REFS,
                cwd=root,
            )
    except OSError as spawn_error:
        log.warning(
            "could not run the branch listing in %s: %s", root, spawn_error,
        )
        return None


def _local_orchestrator_branches(root: Path) -> tuple[str, ...] | None:
    """Every local branch under the orchestrator-owned namespace in one clone.

    Named as the derivations in ``paths`` spell them, which is why the
    `refs/heads/` prefix is stripped here rather than asked for as
    `%(refname:short)`: the short form git computes is the shortest
    unambiguous one, so a tag sharing a branch's name makes git answer
    `heads/orchestrator/...` and that name matches nothing any derivation
    produces -- the branch would read as a stranger's.

    `None` when the ref store could not be read, which is not the same
    answer as the empty tuple a clone with no orchestrator branches gives.

    A zero exit is not on its own a whole reading, which is why anything on
    stderr is answered the same way. git skips a ref it cannot parse, says so
    in a warning, and still succeeds -- so the listing comes back short by
    exactly the branch something is wrong with, and short is the one thing a
    caller cannot see: an issue whose branch was dropped from the answer reads
    as a checkout that no longer has one, which is a different situation
    entirely and the one a cleanup acts on.
    """
    listed = _read_orchestrator_refs(root)
    if listed is None:
        return None
    complaint = (listed.stderr or "").strip()
    if listed.returncode != 0:
        log.warning(
            "could not read the orchestrator branch namespace in %s: %s",
            root, complaint,
        )
        return None
    if complaint:
        log.warning(
            "the orchestrator branch listing in %s warned (%s); taking the "
            "namespace as unread rather than as the part of it that survived",
            root, complaint,
        )
        return None
    return tuple(
        line[len(_LOCAL_BRANCH_PREFIX):]
        for line in (listed.stdout or "").splitlines()
        if line.startswith(_LOCAL_BRANCH_PREFIX)
    )


def _checkout_clone(root: Path) -> Path | None:
    """The one git directory a checkout or a clone shares, or None.

    What makes two paths the same repository: a linked worktree has a git
    directory of its own, and the store it is registered in is the parent's
    -- so the common directory is the only spelling that answers equal for a
    checkout and the clone that created it.

    Two callers ask exactly this, one from each half of the domain. The scan
    asks it of a checkout whose NAME says nothing about whose it is -- the flat
    pre-namespacing layout -- and the classification asks it of a checkout
    whose name does, to establish that the directory at that path really is a
    worktree of the clone the name claims. It lives here because this is the
    lower of the two, and because it is one read rather than two.

    Resolved against the directory the read ran in rather than asked for
    absolutely, because git answers this one relatively whenever it can and
    the two spellings would otherwise compare unequal for a healthy checkout.
    A path that will not resolve at all is answered `None` for the reason the
    listings answer their own root that way: the failure is version-dependent
    and a caller must not read it as a repository identity that was
    established.
    """
    try:
        located = commands._git_hardened(
            "rev-parse", "--git-common-dir", cwd=root,
        )
    except OSError as spawn_error:
        log.warning(
            "could not ask which repository %s belongs to: %s",
            root, spawn_error,
        )
        return None
    if located.returncode != 0:
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


def _issue_checkout_number(entry: Path) -> int | None:
    """The issue a directory under the worktrees root belongs to, or None.

    Two conditions, and the answer is an issue candidate only under both: the
    name is the exact one `paths` builds for that issue, and what carries it
    is a directory in its own right. The first keeps the decomposer's scratch
    checkout and a padded `issue-007` out of a scan; the second keeps out a
    file left beside the checkouts, and a symlink to a directory anywhere on
    the host -- what a caller acts on is the path, so a candidate reported
    through one names a tree this orchestrator never created and never wrote.

    The mode is read with `lstat` rather than through `is_dir` / `is_symlink`,
    which answers both questions in one call and, more to the point, in a call
    that reports the failures those two suppress. What they suppress is
    version-dependent -- Python 3.14 answers `False` for any `OSError` where
    3.12 and 3.13 raise the ones outside a small ignorable set -- and an entry
    the host would not let this process read is not one to pass over quietly:
    it belongs to the caller's boundary, which refuses the whole repository
    rather than reporting a directory it could only see part of.

    An entry that is simply gone by the time its mode is read is the one
    failure that is not a refusal. A checkout removed between the listing and
    this read is a checkout this host no longer holds, which is the same
    answer as never having listed it.
    """
    issue_number = paths._issue_segment_number(entry.name)
    if issue_number is None:
        return None
    try:
        entry_mode = entry.lstat().st_mode
    except FileNotFoundError:
        return None
    return issue_number if S_ISDIR(entry_mode) else None


def _checkout_entries(root: Path) -> tuple[int, ...]:
    """Every issue a checkout directory under `root` names.

    One pass with every `lstat` it takes inside it, so the caller's boundary
    is around the per-entry reads as well as the listing. They fail
    differently and for the same kinds of reason: a root that lists is not a
    root whose entries can be inspected -- readable without being searchable
    is one directory mode away -- and a read refused on one entry says nothing
    about what the rest of them are.
    """
    numbers = (
        _issue_checkout_number(entry) for entry in sorted(root.iterdir())
    )
    return tuple(number for number in numbers if number is not None)


def _checkout_numbers(root: Path) -> frozenset[int] | None:
    """Every issue a checkout directly under `root` names, or None.

    The empty set when `root` is not there at all: a directory nothing was
    ever checked out into is one with no checkouts, and that is an established
    answer rather than a failed one. Only the listing can report it missing --
    an entry that disappears while the pass walks it is dropped where it is
    read, not raised over -- so the two answers stay apart even though one
    boundary covers both reads.

    `None` is kept for everything else: a root that is there and could not be
    listed, a file sitting where it belongs, an entry whose `stat` was refused.
    A caller must not read any of those as a host that has finished its work.
    """
    try:
        return frozenset(_checkout_entries(root))
    except FileNotFoundError:
        return frozenset()
    except OSError as read_error:
        log.warning(
            "could not read the checkouts under %s: %s", root, read_error,
        )
        return None


def _worktree_issue_numbers(spec: config.RepoSpec) -> frozenset[int] | None:
    """Every issue this host still holds a per-repository checkout for."""
    return _checkout_numbers(paths._repo_worktrees_root(spec))


def _legacy_checkout_numbers() -> frozenset[int] | None:
    """Every issue a flat pre-namespacing checkout still stands for.

    One read for the whole host rather than one per repository, because the
    layout it reads is the one that had no per-repository parent: every
    configured entry put its `issue-<n>` checkout directly under
    `WORKTREES_DIR`, so what this finds is a set of issue numbers with nothing
    on them saying whose they are. Deciding that is ``attribution``'s.

    The per-repository roots live under the same directory and are passed over
    on their names alone -- `<owner>__<name>` is not an `issue-<n>` -- so this
    reads the legacy layout without ever descending into the current one.
    """
    return _checkout_numbers(config.WORKTREES_DIR)
