# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The local branch reads a per-issue artifact scan is assembled from.

What this host has published for an issue is a branch in the clone's
`refs/heads/orchestrator/` namespace, and that is what is read here. None of
it writes, fetches, or asks GitHub anything: the scan above exists to answer
from artifacts alone, so an issue nobody remembers is still found by what it
left behind.

The listing fails closed. A ref store that could not be read is answered with
`None` rather than with the empty answer it resembles, because emptiness is
what a caller spends to conclude that a repository is holding nothing -- and a
scan that reports a clone as artifact-free because git could not be run is the
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

from orchestrator.git import commands, locks

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
