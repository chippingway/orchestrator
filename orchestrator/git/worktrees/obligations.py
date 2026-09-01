# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The notes this host keeps while it takes one issue's artifacts down.

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

The value is the commit the classification cleared, which is what a caller
reports and what a fresh deletion is measured against. It is not what any of
them is authorized by: the pass that reads a record back asks the
classification again, so the value says where the branch was last known to
stand rather than what may be done to it.

That is what lets a record be written for a branch nothing cleared at all --
one the classification found on neither host and something has published
again since, or one the remote would not answer for. There is no commit to
name there, so the value is `_REMINDER_MARK`: git's empty tree, an object
every repository has and no branch is ever at. What it says is the whole of
what such a record is for -- go and ask about this branch again -- and a later
pass reaches the same answer it reaches for any other record, since none of
them carries a permission.

The name says which repository owes it, and that is not decoration. Several
`REPOS` entries may share one `target_root` -- a clone with a public and a
private remote is the shape the branch namespacing already exists for -- and
their ref stores are then the same store. The one branch name those entries
all derive is the legacy flat `orchestrator/issue-<n>`, which is exactly why
the attribution behind the scan refuses to charge it to any of them; a ledger
keyed on the branch alone would hand that record to whichever entry read it
first, and the deletion it authorizes would go to a remote that never carried
the branch. So every note sits under `_repository_key`, and a repository reads
back only what it wrote.

The second kind of note is an anchor, and it is about a commit rather than a
branch: what a checkout was standing on at the moment it was removed. A
linked worktree holds its HEAD and its own reflog and nothing else has to,
so a commit made in one between the reading that cleared it and the removal
that follows would be reachable from neither afterwards. The anchor is
written from inside the checkout, one process before the removal, and read
back after it: equal to what the verdict cleared, it is dropped, and anything
else is work somebody made in that window -- kept under the anchor, and said
so.

Both kinds are read back the same way, off their own namespace, because both
outlive what they are about. A record outlives the branch it names and an
anchor outlives the checkout it was taken from, so a pass that walked this
host's artifacts would find neither -- the ledger is where a leftover of
either kind is still named after everything else has gone.

Nothing here reads a remote or deletes anything on one. This owner writes the
note, reads it back, and takes it away; what is done about one belongs to
``reclamation``.
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from orchestrator import config
from orchestrator.git import commands, locks
from orchestrator.git.worktrees import paths
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

# Where the commit a removal was about to take is pinned. Beside the records
# rather than under them, so a listing of what is owed is not a listing of
# what was preserved.
ANCHOR_NAMESPACE = "refs/orchestrator/reclaim-anchor"

# What separates the readable half of a repository's key from the digest that
# makes it exact, in the spelling the branch namespace already uses for its
# own lossy rewrites.
_DIGEST_MARK = "__h"

# What an anchor is written at: whatever the checkout it is taken from is
# standing on, resolved by git in the same process that writes it, so nothing
# lands between the reading and the note.
_HEAD = "HEAD"

# How an anchor names the issue it is about, which is the spelling the reader
# of the namespace parses the number back out of.
_ISSUE_SEGMENT = "issue-"

# The lease that says the ref must not exist yet, which is the only lease an
# anchor may be written under: one already there is holding a commit an
# earlier pass could not account for, and a write that replaced it would be
# the one thing this whole note exists to prevent.
_ABSENT_LEASE = ""

# What one record answers with: the ref, and the commit it was written at.
_RECORD_FORMAT = "--format=%(refname) %(objectname)"

_RECORD_FIELDS = 2

# The value a record carries when this host has never had a commit cleared
# for the branch it names. Git's empty tree, which every repository knows
# without being told -- it resolves in a clone with no objects in it at all --
# and which no branch is ever at, so a reader can tell a reminder from a
# commit somebody adjudicated. A repository whose objects are named by another
# hash refuses the write, which is the fail-closed answer a caller already
# handles: the reminder is not there, and the pass says so.
_REMINDER_MARK = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

# The exit status `rev-parse --verify --quiet` answers with for a ref that is
# not there, as against the ones that mean the repository would not answer.
# An anchor is read before it is written, so the ordinary reading is this one.
_GIT_NO_SUCH_REF = 1

# What keeps a write to a record from travelling somewhere else. The ref store
# these live in is one the per-issue checkouts share, so a record can be made
# a symbolic ref pointing anywhere -- and every update-ref that does not say
# this follows it: the write would move whatever it names, and the delete
# would take it away.
_NO_DEREF = "--no-deref"


def _repository_key(spec: config.RepoSpec) -> str:
    """One ref-safe name per repository, and never one name for two.

    The branch namespace's segment is readable and NOT injective. The
    filesystem-safe sanitizer under it rewrites every character outside its
    own alphabet to `_`, and the digest that would tell two rewrites apart is
    appended only when the ref-safety rules changed something -- so
    `acme/wid:get` and `acme/wid_get` come back as one segment. That is
    precisely the ambiguity the attribution behind the scan refuses to
    resolve, and a ledger keyed on the segment would resolve it silently and
    wrongly: either entry's pass would read the other's notes, classify them
    against its own GitHub, and delete on its own remote.

    So the segment is kept for what it is good for -- an operator reading
    `git for-each-ref` sees whose note this is -- and the digest of the
    untransformed slug is appended unconditionally to make it exact. Two
    slugs that sanitize alike still hash apart, which is the whole property
    the key exists for.
    """
    return (
        f"{paths._sanitize_branch_segment(spec.slug)}"
        f"{_DIGEST_MARK}{paths._slug_digest(spec.slug)}"
    )


def _records_prefix(spec: config.RepoSpec) -> str:
    """Where one repository's records live, and nowhere else's.

    The trailing separator is what makes the prefix a namespace rather than a
    name: the ref spelling this repository's key itself, were somebody to
    create it, is not one of the records beneath it.
    """
    return f"{RECLAIM_NAMESPACE}/{_repository_key(spec)}/"


def _obligation_ref(spec: config.RepoSpec, branch: str) -> str:
    """The ref one branch's outstanding remote deletion is recorded under.

    The branch spelled in full after the repository's own namespace, so the
    name reads back to exactly the branch it is about, and only for the
    repository whose remote that branch was published to. Every branch this
    orchestrator publishes is already a valid ref path, which is what lets one
    be carried inside another's name without a rewrite that could lose a
    distinction.
    """
    return f"{_records_prefix(spec)}{branch}"


def _record_obligation(
    spec: config.RepoSpec, branch: str, sha: str,
) -> bool:
    """Write down that this host has unfinished business with one branch.

    Answered as whether the record IS there, because of what the caller does
    next: the deletion this covers is the one that can fail after the last
    local trace of its issue is gone, so a caller that could not write the
    record has to refuse the deletion rather than run it uncovered.

    Written before the attempt rather than after the failure, because the
    failure that matters most is the one that takes the process with it: a
    record written afterwards is a record the crash in between never reaches.

    Written without dereferencing, because where it goes is a ref store the
    per-issue checkouts share: a record made symbolic there would have this
    write land on whatever it points at, and a note to self would become an
    edit to somebody's branch.
    """
    return _written_note(
        spec.target_root, spec, _obligation_ref(spec, branch), sha,
    )


def _written_note(
    root: Path,
    spec: config.RepoSpec,
    ref: str,
    written_at: str,
    lease: str | None = None,
) -> bool:
    """Put one note where this host will find it again, or say it is not there.

    Undereferenced, because the store these live in is one the per-issue
    checkouts share: a note somebody made a symbolic ref would otherwise have
    this write land on whatever it points at, turning a note to self into an
    edit to somebody's branch.

    `root` is the tree the write runs in -- the clone for a record, and the
    checkout for an anchor, since only from inside one does `HEAD` mean that
    checkout's own. The lock is the clone's either way: what is being written
    is the ref store the clone keeps.

    `lease` is the value the ref has to be at for the write to land, and the
    empty string is git's spelling for "not there at all". A record is written
    without one -- what it carries is this host's own note about a branch, and
    the last pass to write it is the one that knows -- while an anchor may
    only ever be created.
    """
    argv = ("update-ref", _NO_DEREF, ref, written_at)
    if lease is not None:
        argv += (lease,)
    try:
        with locks._target_root_lock(spec.target_root):
            written = commands._git_hardened(*argv, cwd=root)
    except Exception:
        log.exception("%s could not be written down", ref)
        return False
    if written.returncode == 0:
        return True
    log.warning(
        "%s could not be written down: %s",
        ref, (written.stderr or "").strip(),
    )
    return False


def _remind(spec: config.RepoSpec, branch: str) -> bool:
    """Write down that one branch is unfinished business, cleared or not.

    The record a teardown leaves when it has no commit to name: the branch was
    on neither host when the classification ran, and by the time the teardown
    reached the remote there was something under that name again -- or nobody
    could say. Neither is a deletion this may run, and both are leftovers with
    nothing on this host left to find them by, so what carries them to a later
    pass is this.
    """
    return _record_obligation(spec, branch, _REMINDER_MARK)


def _discharge_obligation(spec: config.RepoSpec, branch: str) -> bool:
    """Take away the record of a deletion nobody owes any more.

    Idempotent by git's own answer: `update-ref -d` succeeds on a ref that is
    not there, which is what a second pass over a record another one already
    settled finds. No old value is named, unlike every other deletion in this
    domain -- what would be pinned is this host's own note to itself, and a
    note somebody rewrote is not work that could be lost.

    Undereferenced for the reason the write is: a record turned into a
    symbolic ref would otherwise have this take away the branch it names
    rather than the record.
    """
    return _dropped_note(spec, _obligation_ref(spec, branch))


def _dropped_note(spec: config.RepoSpec, ref: str) -> bool:
    """Take one note away, whether or not it was there to take."""
    try:
        with locks._target_root_lock(spec.target_root):
            dropped = commands._git_hardened(
                "update-ref", "-d", _NO_DEREF, ref, cwd=spec.target_root,
            )
    except Exception:
        log.exception("%s could not be taken away", ref)
        return False
    if dropped.returncode == 0:
        return True
    log.warning(
        "%s could not be taken away: %s",
        ref, (dropped.stderr or "").strip(),
    )
    return False


def _anchors_prefix(spec: config.RepoSpec) -> str:
    """Where one repository's anchors live, and nowhere else's.

    The trailing separator makes it a namespace rather than a name, exactly as
    it does for the records: the ref spelling this repository's key itself is
    not one of the notes beneath it.
    """
    return f"{ANCHOR_NAMESPACE}/{_repository_key(spec)}/"


def _anchor_ref(spec: config.RepoSpec, issue_number: int) -> str:
    """The ref one issue's checkout is pinned under while it is removed."""
    return f"{_anchors_prefix(spec)}{_ISSUE_SEGMENT}{issue_number}"


def _anchor_checkout(
    spec: config.RepoSpec, worktree: Path, issue_number: int,
) -> bool:
    """Pin whatever this checkout is standing on, from inside the checkout.

    One process, and that is the point of it: git resolves the HEAD of the
    tree it is run in and writes the note in the same command, so nothing can
    land between the reading and the note. What the note is for is the window
    after it -- a `worktree remove` takes the tree's HEAD and its reflog with
    it, and a commit those two alone were holding would be reachable from
    nothing afterwards.

    The ref is shared rather than per-worktree, which is what lets it outlive
    the checkout it was taken from: `refs/orchestrator/...` lives in the store
    the clone keeps, and only `HEAD`, `refs/bisect/`, and `refs/worktree/` are
    a worktree's own.

    Created, never overwritten. An anchor already at this name is one an
    earlier pass left standing because what it pinned was not what anybody had
    cleared, so a write that replaced it would take the only reference that
    commit has -- the very loss the note exists to prevent -- and the pass
    after it would discharge what it found. The lease saying the ref must not
    exist is what makes the two cases one answer: this fails, and the caller
    leaves the checkout where it is.

    Answered as whether the note IS there, because a caller that could not
    take it has to leave the checkout alone: removing it is what would strand
    whatever it turns out to have been holding.
    """
    return _written_note(
        worktree,
        spec,
        _anchor_ref(spec, issue_number),
        _HEAD,
        lease=_ABSENT_LEASE,
    )


def _anchored_commit(spec: config.RepoSpec, issue_number: int) -> str:
    """The commit one issue's anchor pinned, or "" when nobody could say.

    The empty string covers both an anchor that is not there and a read that
    failed, because a caller spends them the same way: what it has to
    establish is that the commit taken with the checkout is the one that was
    cleared, and neither answer establishes it.

    Only the second is reported. An issue with no anchor is what every removal
    that has not started yet looks like -- the read runs before the write, so
    the note it is looking for is the one about to be made -- and a line on
    each of those would bury the one about a note nobody could read.
    """
    try:
        with locks._target_root_lock(spec.target_root):
            resolved = commands._git_hardened(
                "rev-parse", "--verify", "--quiet",
                _anchor_ref(spec, issue_number),
                cwd=spec.target_root,
            )
    except Exception:
        log.exception("the anchor of #%d could not be read", issue_number)
        return ""
    if resolved.returncode == _GIT_NO_SUCH_REF:
        return ""
    if resolved.returncode != 0:
        log.warning(
            "the anchor of #%d did not resolve: %s",
            issue_number, (resolved.stderr or "").strip(),
        )
        return ""
    return (resolved.stdout or "").strip()


def _discard_anchor(spec: config.RepoSpec, issue_number: int) -> bool:
    """Let go of an anchor that pinned nothing anybody has to keep."""
    return _dropped_note(spec, _anchor_ref(spec, issue_number))


def _read_notes(
    spec: config.RepoSpec, prefix: str,
) -> subprocess.CompletedProcess | None:
    """Run one namespace's note listing in this clone, or say it never ran.

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
                prefix,
                cwd=spec.target_root,
            )
    except OSError as spawn_error:
        log.warning(
            "could not run the note listing for %s in %s: %s",
            prefix, spec.target_root, spawn_error,
        )
        return None


def _recorded_notes(
    spec: config.RepoSpec, prefix: str,
) -> tuple[ProvenTip, ...] | None:
    """Every note this clone carries under one of the two namespaces.

    Each one as the name it is filed under and the commit it was written at,
    which is the same pair a verdict hands over -- a note IS a proven tip
    somebody wrote down, so a caller settling one spends it exactly as it
    spends the verdict's own.

    `None` when the notes could not be read, which is not the empty answer a
    clone holding none gives: a caller reading the second as the first would
    conclude that everything this host began has finished. A listing that
    warned is answered the same way, because git skips a ref it cannot parse
    and still exits zero -- the answer comes back short by exactly the note
    something is wrong with, and short is the one thing a caller cannot see.
    """
    listed = _read_notes(spec, prefix)
    if listed is None:
        return None
    complaint = (listed.stderr or "").strip()
    if listed.returncode != 0 or complaint:
        log.warning(
            "could not read the notes under %s in %s: %s",
            prefix, spec.target_root, complaint,
        )
        return None
    return _parsed_records(listed.stdout or "", prefix)


def _recorded_obligations(
    spec: config.RepoSpec,
) -> tuple[ProvenTip, ...] | None:
    """Every remote deletion this clone still carries a record of."""
    return _recorded_notes(spec, _records_prefix(spec))


def _recorded_anchors(
    spec: config.RepoSpec,
) -> tuple[ProvenTip, ...] | None:
    """Every commit this clone is still holding an anchor over.

    Read back the way the records beside them are, and for the same reason: an
    anchor outlives the checkout it was taken from, so once that checkout and
    the branches beside it are gone the ledger is the only place the commit is
    named at all. What comes back is the issue segment the note is filed under
    and the commit it pinned; whether it still has to be held is the caller's
    question, not this one's.
    """
    return _recorded_notes(spec, _anchors_prefix(spec))


def _parsed_records(
    listed: str, prefix: str,
) -> tuple[ProvenTip, ...] | None:
    """The records one listing reports, or None when one of them did not read.

    A line that does not carry a ref under this repository's own namespace and
    a commit beside it is not a record this understands, and one unreadable
    line refuses the whole listing rather than the line: what a caller spends
    the answer on is finishing everything this host began, and a listing
    quietly short by one is indistinguishable from one that is complete.
    """
    records = []
    for line in listed.splitlines():
        fields = line.split()
        if len(fields) != _RECORD_FIELDS:
            log.warning("a reclaim record did not read: %r", line)
            return None
        ref, sha = fields
        if not ref.startswith(prefix):
            log.warning("a reclaim record named %r, outside its own name", ref)
            return None
        records.append(ProvenTip(ref[len(prefix):], sha))
    return tuple(records)
