# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The remote deletions this host has begun and not finished.

One ref per branch, in a namespace of this orchestrator's own, written before
the deletion it is about and taken away once that deletion has happened or
stopped being owed. What it exists for is the one thing a teardown's ordering
cannot cover: what a later scan reads a candidate back off is local, so a
remote branch that outlives the last local artifact naming its issue is a
leftover nothing on this host can find again -- and a human deleting that
branch a moment before the teardown reaches it is all it takes. The record is
the name, kept where a restart still finds it.

A ref rather than a file, because the ref store is where this domain's durable
state already lives: it is written under the same lock every other ref is, it
survives a crash between the write and the next tick the way they do, and
reading it back costs what the branch listing beside it costs. `refs/heads/`
is not it -- a branch there would be read by the artifact scan as a candidate
of its own -- and neither is the snapshot namespace, which is a published
surface with a policy of its own. This is a sibling of that one under the
`refs/orchestrator/` root nothing else writes.

The value is the commit the classification cleared, which is what makes the
record enough on its own: what it authorizes is a deletion pinned to that
commit, so a branch the remote has moved on to since is not one anybody may
spend this record on.

Nothing here reads a remote or deletes anything on one. This owner writes the
record, reads it back, and takes it away; what is done about one belongs to
``reclamation``.
"""
from __future__ import annotations

import logging
import subprocess

from orchestrator import config
from orchestrator.git import commands, locks
from orchestrator.git.worktrees.models import ProvenTip

# The channel is named for the worktree-lifecycle domain rather than for this
# module's path: operators filter the rendered `orchestrator.worktree_lifecycle`
# prefix and attach handlers to it, so a record that could not be kept reports
# where their filters already point.
log = logging.getLogger("orchestrator.worktree_lifecycle")

# Where an outstanding deletion is written down. Under the root this
# orchestrator's own namespaces live in, and named for what is owed rather
# than for the branch family it is about, so nothing that walks branches or
# snapshots walks these.
RECLAIM_NAMESPACE = "refs/orchestrator/remote-reclaim"

# The pattern form the listing matches by, and the prefix a recorded name is
# read back through: a trailing separator, so the ref `RECLAIM_NAMESPACE`
# itself -- were somebody to create it -- is not one of the records beneath it.
_NAMESPACE_PREFIX = f"{RECLAIM_NAMESPACE}/"

# What one record answers with: the ref, and the commit it was written at.
_RECORD_FORMAT = "--format=%(refname) %(objectname)"

_RECORD_FIELDS = 2


def _obligation_ref(branch: str) -> str:
    """The ref one branch's outstanding remote deletion is recorded under.

    The branch spelled in full after the namespace, so the name reads back to
    exactly the branch it is about. Every branch this orchestrator publishes
    is already a valid ref path, which is what lets one be carried inside
    another's name without a rewrite that could lose a distinction.
    """
    return f"{_NAMESPACE_PREFIX}{branch}"


def _record_obligation(
    spec: config.RepoSpec, branch: str, sha: str,
) -> bool:
    """Write down the deletion this host is about to attempt on the remote.

    Answered as whether the record IS there, because of what the caller does
    next: the deletion this covers is the one that can fail after the last
    local trace of its issue is gone, so a caller that could not write the
    record has to refuse the deletion rather than run it uncovered.

    Written before the attempt rather than after the failure, because the
    failure that matters most is the one that takes the process with it: a
    record written afterwards is a record the crash in between never reaches.
    """
    try:
        with locks._target_root_lock(spec.target_root):
            recorded = commands._git_hardened(
                "update-ref", _obligation_ref(branch), sha,
                cwd=spec.target_root,
            )
    except Exception:
        log.exception(
            "the remote deletion of %r could not be recorded", branch,
        )
        return False
    if recorded.returncode == 0:
        return True
    log.warning(
        "the remote deletion of %r could not be recorded: %s",
        branch, (recorded.stderr or "").strip(),
    )
    return False


def _discharge_obligation(spec: config.RepoSpec, branch: str) -> bool:
    """Take away the record of a deletion nobody owes any more.

    Idempotent by git's own answer: `update-ref -d` succeeds on a ref that is
    not there, which is what a second pass over a record another one already
    settled finds. No old value is named, unlike every other deletion in this
    domain -- what would be pinned is this host's own note to itself, and a
    note somebody rewrote is not work that could be lost.
    """
    try:
        with locks._target_root_lock(spec.target_root):
            discharged = commands._git_hardened(
                "update-ref", "-d", _obligation_ref(branch),
                cwd=spec.target_root,
            )
    except Exception:
        log.exception(
            "the record of the remote deletion of %r could not be taken away",
            branch,
        )
        return False
    if discharged.returncode == 0:
        return True
    log.warning(
        "the record of the remote deletion of %r could not be taken away: %s",
        branch, (discharged.stderr or "").strip(),
    )
    return False


def _read_records(spec: config.RepoSpec) -> subprocess.CompletedProcess | None:
    """Run the record listing in this clone, or report that it never ran.

    Hardened and lock-held for the reason every read of this clone is: the
    worktrees hanging off it are trees agents write in, and a planted
    `core.hooksPath` or `core.fsmonitor` runs on an ordinary read too.
    """
    try:
        with locks._target_root_lock(spec.target_root):
            return commands._git_hardened(
                "for-each-ref",
                _RECORD_FORMAT,
                "--end-of-options",
                _NAMESPACE_PREFIX,
                cwd=spec.target_root,
            )
    except OSError as spawn_error:
        log.warning(
            "could not run the reclaim record listing in %s: %s",
            spec.target_root, spawn_error,
        )
        return None


def _recorded_obligations(
    spec: config.RepoSpec,
) -> tuple[ProvenTip, ...] | None:
    """Every remote deletion this clone still carries a record of.

    Each one as the branch it is about and the commit it was cleared at, which
    is the same pair a verdict hands over -- a record IS a proven tip somebody
    wrote down, so a caller settling one spends it exactly as it spends the
    verdict's own.

    `None` when the records could not be read, which is not the empty answer a
    clone owing nothing gives: a caller reading the second as the first would
    conclude that every deletion this host began has finished. A listing that
    warned is answered the same way, because git skips a ref it cannot parse
    and still exits zero -- the answer comes back short by exactly the record
    something is wrong with, and short is the one thing a caller cannot see.
    """
    listed = _read_records(spec)
    if listed is None:
        return None
    complaint = (listed.stderr or "").strip()
    if listed.returncode != 0 or complaint:
        log.warning(
            "could not read the reclaim records in %s: %s",
            spec.target_root, complaint,
        )
        return None
    return _parsed_records(listed.stdout or "")


def _parsed_records(listed: str) -> tuple[ProvenTip, ...] | None:
    """The records one listing reports, or None when one of them did not read.

    A line that does not carry a ref under this namespace and a commit beside
    it is not a record this understands, and one unreadable line refuses the
    whole listing rather than the line: what a caller spends the answer on is
    finishing everything this host began, and a listing quietly short by one
    is indistinguishable from one that is complete.
    """
    records = []
    for line in listed.splitlines():
        fields = line.split()
        if len(fields) != _RECORD_FIELDS:
            log.warning("a reclaim record did not read: %r", line)
            return None
        ref, sha = fields
        if not ref.startswith(_NAMESPACE_PREFIX):
            log.warning("a reclaim record named %r, outside its own name", ref)
            return None
        records.append(ProvenTip(ref[len(_NAMESPACE_PREFIX):], sha))
    return tuple(records)
