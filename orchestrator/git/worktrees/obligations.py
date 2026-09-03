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

It is also what every note is taken away under. These refs live in the store
the per-issue checkouts share, and each caller here reads a note before
deciding what to do about it, so a deletion that did not say what it expected
would take whatever the window between the two left there -- an anchor
repointed onto a commit nothing else names, a record another pass wrote again.
The lease makes the reading and the deletion one step, and a note that has
already gone is told from one that moved by asking a second time.

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
note, reads it back, and takes it away; what is done about one belongs to the
teardown that spends it.
"""
from __future__ import annotations

import logging
import os
import stat
import subprocess
import threading
from collections.abc import Callable, Mapping
from pathlib import Path
from types import MappingProxyType

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

# The root of that namespace as a room rather than as a name, which is what
# tells a record from an anchor when only the ref is in hand.
_RECLAIM_ROOM = f"{RECLAIM_NAMESPACE}/"

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

# What one record answers with: the ref, the value it was written at, what
# this repository says that value IS, and the name it points at when somebody
# has made it a symbolic ref. The last field is empty for every note this
# owner writes -- one that is filled is a ref whose value belongs to whatever
# it was aimed at, so the listing refuses rather than reporting that value as a
# note this host stands behind. The type field is asked for because a ref file
# carries an id and nothing else: git resolves one for an object it does not
# have, and a blob or a stray tree reads back exactly like a commit somebody
# adjudicated. Asking makes git read the object, so a note left at an id
# nothing was ever written under ends the listing rather than riding out on it.
_RECORD_FORMAT = "--format=%(refname) %(objectname) %(objecttype) %(symref)"

_RECORD_FIELDS = 4

# The single space the format above puts between its fields. Split on exactly
# that rather than on runs of whitespace, so the empty symref field an
# ordinary note carries stays a field that is there and empty instead of one
# that disappears and takes the count with it.
_RECORD_SEPARATOR = " "

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

# The exit status `symbolic-ref --quiet` answers with for a name that holds no
# symbolic ref -- a direct one, or nothing at all. A name git will not parse
# at all comes back at neither this nor zero, which is why the two are told
# apart rather than one being read as "anything but symbolic".
_GIT_NOT_SYMBOLIC = 1

# The one thing a note this owner writes ever stands at, beside the reminder
# mark: the commit a classification cleared.
_COMMIT_OBJECT = "commit"

# What keeps every command here local. A clone made with a filter keeps a
# promisor remote, and git answers an object it is missing by FETCHING it
# rather than by failing: the write that checks a value, the listing that asks
# what one is, and the type read under both each reach that remote on their
# own. Two things go wrong at once. This owner reaches a remote, which is the
# one thing it never does -- and a note left at an object nothing on this host
# has comes back as one somebody adjudicated, so the leftover that exists to
# be found never fails closed.
_NO_LAZY_FETCH: Mapping[str, str] = MappingProxyType({
    "GIT_NO_LAZY_FETCH": "1",
})

# What a note read answers with for a name nothing is at, as against the
# `None` a read that established nothing answers with. Spelled once, because
# the whole point of the pair is that a caller can tell them apart.
_NO_NOTE = ""

# What git calls the file it holds a ref under while it is writing it. One of
# those is a write in flight rather than a note, so the name it carries is not
# one the listing has to have answered for.
_REF_LOCK_SUFFIX = ".lock"

# What keeps a write to a record from travelling somewhere else. The ref store
# these live in is one the per-issue checkouts share, so a record can be made
# a symbolic ref pointing anywhere -- and every update-ref that does not say
# this follows it: the write would move whatever it names, and the delete
# would take it away.
_NO_DEREF = "--no-deref"


def _store_held(spec: config.RepoSpec) -> threading.RLock:
    """The lock every reading and every writing of these notes runs under.

    One name for it, because what it protects is one thing: a note is read
    before it is acted on, and git offers no write here that states what the
    name may BE as well as what it stands at. Holding this across the pair is
    what makes them one step against anything else this process is running.

    It does not reach the agents. They write in checkouts of their own and
    take no lock of this orchestrator's, which is why every one of those
    readings is taken again rather than trusted once.
    """
    return locks._target_root_lock(spec.target_root)


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
    return f"{_RECLAIM_ROOM}{_repository_key(spec)}/"


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

    Neither the flag nor the lease says anything about the path the name is
    filed under, and git follows that path a room at a time. So the rooms are
    walked first: a namespace replaced with a link to somewhere else has this
    write land there instead, and the note a host keeps for itself becomes an
    edit to whatever lives at the far end.

    What the note would stand at is established too, since git will file a ref
    at any object it has: a note left at a blob or a stray tree is one every
    reader here refuses from then on, so this would report a state a restart
    could read back while what a restart finds is a ledger it has to refuse
    whole -- and the caller that went on because its record was kept went on
    over nothing.
    """
    argv = ("update-ref", _NO_DEREF, ref, written_at)
    if lease is not None:
        argv += (lease,)
    try:
        with _store_held(spec):
            if not _writes_here(spec, root, ref):
                return False
            if not _a_note_to_write(root, ref, written_at):
                log.warning(
                    "%s would stand at %s, which is no note this host writes",
                    ref, written_at,
                )
                return False
            written = commands._git_hardened(
                *argv, cwd=root, env_extra=_NO_LAZY_FETCH,
            )
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


def _a_note_to_write(root: Path, ref: str, written_at: str) -> bool:
    """Whether what a write would file is a value a note is written at.

    Asked in the tree the write runs in, which for an anchor is the checkout
    whose own `HEAD` is being pinned. What can move between this and the write
    is that HEAD, and only another commit moves it -- so the value filed may
    differ from the one asked about, and is a commit either way.
    """
    return _a_note_stands_at(ref, written_at, _object_kind(root, written_at))


def _writes_here(spec: config.RepoSpec, root: Path, ref: str) -> bool:
    """Whether a note written from `root` lands where this repository reads.

    The tree a command runs in is what decides which ref store it writes to,
    and only a record's write runs in the clone: an anchor's runs inside the
    checkout it is about, because only from in there does `HEAD` mean that
    checkout's own. A checkout of somebody ELSE'S repository -- a path
    repointed at one, an operator's own clone left where this issue's belongs
    -- keeps a store of its own, so the anchor would be filed where nothing on
    this repository's side ever looks while the caller was told it was kept:
    the checkout comes down, and the commit it was holding is named nowhere.

    So the store the write would land in is asked for and held to the one this
    repository reads, and the rooms are then walked in that same store rather
    than in whichever one the command happens to find.
    """
    store = _shared_ref_store(spec.target_root)
    if store is None or _shared_ref_store(root) != store:
        log.warning(
            "%s written in %s would not land in the store %s keeps",
            ref, root, spec.target_root,
        )
        return False
    return _own_way_down(store, ref)


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


def _discharge_obligation(
    spec: config.RepoSpec, branch: str, expected: str,
) -> bool:
    """Take away the record of a deletion nobody owes any more.

    `expected` is the value the caller read and acted on, and it is stated for
    the reason every deletion in this domain states one: between the read and
    this, another pass can have written the record again -- at a commit of its
    own, or as the reminder that says the branch has to be asked about again
    -- and a deletion that took whatever it found would drop the note that
    second pass is relying on.

    Undereferenced for the reason the write is: a record turned into a
    symbolic ref would otherwise have this take away the branch it names
    rather than the record.
    """
    return _dropped_note(spec, _obligation_ref(spec, branch), expected)


def _dropped_note(spec: config.RepoSpec, ref: str, expected: str) -> bool:
    """Take one note away, if it is still the note the caller read.

    Named old value rather than a bare delete, because these refs live in the
    store the per-issue checkouts share and every caller here has read the
    note before deciding what to do about it. An anchor repointed in that
    window is holding a commit nothing else names -- the very thing it exists
    for -- and a delete that did not say what it expected would take it.

    Still idempotent, and by a second reading rather than by git's own answer:
    a leased delete is refused for a ref that has ALREADY gone as squarely as
    for one that moved, and the first of those is this deletion having
    happened. So a refusal is asked about once more, and a name nothing
    resolves is the success it looks like from every other angle.

    That second reading has to be the ref genuinely not being there, which is
    why it is the answer rather than the value that decides. A read that
    failed says nothing at all, and spent as an absence it would report a note
    still standing as one this pass took away -- and an anchor still holding
    somebody's commit as a surface that came back clean.

    The name is established undereferenced first, because the lease alone does
    not establish it: git compares the stated value against what the name
    RESOLVES to even here, so a note turned into a symbolic ref onto anything
    standing at that same value passes the comparison. What would then be
    taken away is a ref this pass never read, and the note it replaced would
    be reported as one this pass discharged.

    That reading and this deletion are one hold of the lock, because two holds
    would leave the window the reading exists to close: git has no delete that
    states what the name may BE as well as what it stands at, so what makes
    the pair one step is that nothing else in this process runs between them.
    """
    try:
        with _store_held(spec):
            if not _direct_note(spec, ref):
                return False
            dropped = commands._git_hardened(
                "update-ref", "-d", _NO_DEREF, ref, expected,
                cwd=spec.target_root, env_extra=_NO_LAZY_FETCH,
            )
            if dropped.returncode == 0:
                return True
            gone = _note_at(spec, ref) == _NO_NOTE
    except Exception:
        log.exception("%s could not be taken away", ref)
        return False
    if gone:
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
    after it would discharge what it found.

    The lease saying the ref must not exist is one half of that, and it is the
    half git can hold across the write: what it compares against is what the
    name RESOLVES to, and a name resolving to nothing is what it accepts. A
    symbolic ref onto a ref that does not exist resolves to nothing too, so
    the lease alone would let this replace one -- and what such a name is
    standing over is exactly the note nobody could read. So the name is asked
    about undereferenced first, and anything but genuine absence refuses the
    write. The asking and the write are one hold of the lock, since a name
    that came to hold something between them is one this would write over
    having established it was free.

    Answered as whether the note IS there, because a caller that could not
    take it has to leave the checkout alone: removing it is what would strand
    whatever it turns out to have been holding.
    """
    ref = _anchor_ref(spec, issue_number)
    with _store_held(spec):
        if _note_at(spec, ref) != _NO_NOTE:
            log.warning("%s is already standing, so the checkout stays", ref)
            return False
        return _written_note(worktree, spec, ref, _HEAD, lease=_ABSENT_LEASE)


def _anchored_commit(spec: config.RepoSpec, issue_number: int) -> str:
    """The commit one issue's anchor pinned, or "" when nobody could say.

    The two negatives the read below keeps apart arrive here as one, because
    this caller spends them the same way: what it has to establish is that the
    commit taken with the checkout is the one that was cleared, and neither a
    note that is not there nor a read that failed establishes it.
    """
    return _note_at(spec, _anchor_ref(spec, issue_number)) or ""


def _direct_note(spec: config.RepoSpec, ref: str) -> bool:
    """Whether a resolution of this name may be believed, read without following.

    True for a name holding a direct ref and for one holding nothing at all --
    the only two shapes a note this owner ever leaves -- and False for one
    holding a symbolic ref or one git would not read.

    The reading every read of a note is gated on, because the resolution
    beside it cannot answer this and cannot say that it did not. That one
    follows a symbolic ref: it reports the far end for a name aimed at
    something that exists, and reports NOTHING -- git's own answer for a ref
    that is not there -- for one aimed at something that does not. So a record
    somebody turned into a dangling symbolic ref reads as a record this host
    had already taken away, and the deletion that never ran gets reported as
    done.

    `symbolic-ref` is the read that does not follow, so it answers for the
    name rather than for the far end. A direct ref and an empty name are one
    answer here, which is what leaves the object id to the resolution beside
    it; a name git will not read at all is neither, and both refusals are
    reported, since they are two different things to go and look at.

    Run inside the lock its caller holds, like every other reading here: what
    it establishes is spent one step later, and a hold of its own would end
    before that step began.

    That read is about the ref, and one about the file under it comes first,
    because git has a second way of following a name that no ref read reports
    on: it opens a note by path, so a note somebody replaced with a filesystem
    link is read as whatever the link leads to -- and a link leading nowhere
    is read as a name nothing is at, by every command here. Looked at without
    following, such a name is the thing standing there that it is.
    """
    store = _shared_ref_store(spec.target_root)
    if store is None or not _stands_as(store / ref, store, stat.S_ISREG):
        return False
    try:
        asked = commands._git_hardened(
            "symbolic-ref", "--quiet", "--end-of-options", ref,
            cwd=spec.target_root, env_extra=_NO_LAZY_FETCH,
        )
    except Exception:
        log.exception("%s could not be read undereferenced", ref)
        return False
    if asked.returncode == _GIT_NOT_SYMBOLIC:
        return True
    if asked.returncode == 0:
        log.warning(
            "%s holds a symbolic ref rather than a note this host wrote", ref,
        )
    else:
        log.warning(
            "%s did not read undereferenced: %s",
            ref, (asked.stderr or "").strip(),
        )
    return False


def _note_at(spec: config.RepoSpec, ref: str) -> str | None:
    """What one note in this clone stands at, in three answers.

    The object id when the note is there, `_NO_NOTE` when nothing is at the
    name at all, and `None` when nobody could say. The last two are worth
    telling apart for the caller that asks after a deletion it could not run:
    only the ref genuinely being gone is that deletion having happened, and a
    read that failed spent as an absence would report a note still standing as
    one this host took away.

    What this owner writes is a direct ref at a commit this repository has --
    or at the reminder mark -- so a name holding anything else is a name it
    cannot read a note off -- and the undereferenced
    reading in front of the resolution is what keeps the two apart. Without it
    a symbolic ref onto a ref that does not exist arrives here as absence,
    which is the one answer that turns a note still standing into a deletion
    reported as done.

    Only the failure is reported. An issue with no anchor is what every
    removal that has not started yet looks like -- the read runs before the
    write, so the note it is looking for is the one about to be made -- and a
    line on each of those would bury the one about a note nobody could read.

    Both halves under one hold of the lock, so what the resolution answers for
    is the name the reading in front of it established: two holds would let
    the name become a symbolic ref in between, and the object id at the far
    end of it would come back as the value a note stands at.

    The lock is re-entrant, so the leased deletion that reads a ref back after
    a refusal pays nothing for asking inside the lock it already holds -- and
    what answers is the store that deletion just ran against rather than one
    another thread has since moved on.
    """
    try:
        with _store_held(spec):
            if not _direct_note(spec, ref):
                return None
            resolved = commands._git_hardened(
                "rev-parse", "--verify", "--quiet", ref,
                cwd=spec.target_root, env_extra=_NO_LAZY_FETCH,
            )
            if resolved.returncode == _GIT_NO_SUCH_REF:
                return _NO_NOTE
            if resolved.returncode != 0:
                log.warning(
                    "%s did not resolve: %s",
                    ref, (resolved.stderr or "").strip(),
                )
                return None
            return _note_value(spec, ref, (resolved.stdout or "").strip())
    except Exception:
        log.exception("%s could not be read", ref)
        return None


def _note_value(spec: config.RepoSpec, ref: str, stood: str) -> str | None:
    """One note's value, once it is one this owner could have written.

    The id a ref file carries is not evidence that anything is behind it: a
    ref may be written and resolved for an object this repository does not
    have, and `rev-parse --verify` answers for the NAME being well formed
    rather than for the object. So a note left at a well-formed id nothing was
    ever written under comes back looking exactly like a commit somebody
    adjudicated, and a note left at a blob comes back as one a caller would go
    and delete a branch over.
    """
    if _a_note_stands_at(ref, stood, _object_kind(spec.target_root, stood)):
        return stood
    log.warning("%s stands at %s, which is no note this host wrote", ref, stood)
    return None


def _object_kind(root: Path, revision: str) -> str:
    """What this repository says one revision is, or "" when it has no object.

    The empty answer covers both the object not being there and the repository
    declining to say, because the caller spends them alike: neither one
    establishes that the value it read is a value a note is ever written at.

    Asked of a tree rather than of the repository, because an anchor's value
    is `HEAD` and only from inside the checkout it is about does that name the
    commit being pinned.
    """
    try:
        told = commands._git_hardened(
            "cat-file", "-t", "--end-of-options", revision,
            cwd=root, env_extra=_NO_LAZY_FETCH,
        )
    except Exception:
        log.exception("%s could not be looked up in %s", revision, root)
        return ""
    if told.returncode != 0:
        log.warning(
            "%s is no object %s has: %s",
            revision, root, (told.stderr or "").strip(),
        )
        return ""
    return (told.stdout or "").strip()


def _a_note_stands_at(ref: str, sha: str, kind: str) -> bool:
    """Whether one value is a value a note under THAT name is written at.

    Both kinds are written at a commit -- the one a classification cleared for
    a branch, the one a checkout was standing on while it came down. Only a
    record has a second thing to say, and the reminder mark is how it says it:
    a branch nothing was cleared for, to be asked about again. An anchor has
    nothing of the sort to say, because a commit is the whole of what it is
    FOR; one standing at the mark names no work at all, and handing it back as
    a commit to account for would have a caller settle a removal against a
    value no reading ever produced.

    Anything else -- a blob, a tree that is not the mark, an id this
    repository has no object for -- is a note nobody here wrote, and handing
    one back as a proven tip would have a caller measure a deletion against a
    value nothing ever proved.
    """
    if kind == _COMMIT_OBJECT:
        return True
    return sha == _REMINDER_MARK and ref.startswith(_RECLAIM_ROOM)


def _discard_anchor(
    spec: config.RepoSpec, issue_number: int, expected: str,
) -> bool:
    """Let go of an anchor that pinned nothing anybody has to keep.

    `expected` is the commit the caller read there and established was safe to
    stop naming. An anchor moved between that reading and this is one holding
    something nobody has established anything about -- the store it lives in
    is one the agents this orchestrator runs can write -- so the lease is what
    keeps the safety check and the deletion one decision.
    """
    return _dropped_note(spec, _anchor_ref(spec, issue_number), expected)


def _read_notes(
    spec: config.RepoSpec, prefix: str,
) -> subprocess.CompletedProcess | None:
    """Run one namespace's note listing in this clone, or say it never ran.

    Hardened for the reason every read of this clone is: the worktrees hanging
    off it are trees agents write in, and a planted `core.hooksPath` or
    `core.fsmonitor` runs on an ordinary read too. The lock is the caller's,
    which holds it across this and the check that what came back was whole.
    """
    try:
        return commands._git_hardened(
            "for-each-ref",
            _RECORD_FORMAT,
            "--end-of-options",
            prefix,
            cwd=spec.target_root,
            env_extra=_NO_LAZY_FETCH,
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
    The note it drops with no warning at all is checked for beneath, since
    every reason to refuse this answer has to arrive before it is given.

    The whole of it under one hold of the lock, so the listing and the check
    that it is complete answer for one ref store rather than for two moments
    of it: a note this process writes between them would otherwise read as one
    the listing lost.
    """
    with _store_held(spec):
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
        records = _parsed_records(listed.stdout or "", prefix)
        if records is None or not _every_note_listed(spec, prefix, records):
            return None
    return records


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


def _every_note_listed(
    spec: config.RepoSpec, prefix: str, records: tuple[ProvenTip, ...],
) -> bool:
    """Whether the listing named every note the ref store is holding.

    The one thing the listing cannot answer for itself. `for-each-ref` reports
    a ref it cannot parse and a ref outside its own name -- both come back as
    a warning it can be refused over -- but a note somebody made a symbolic
    ref onto a ref that does not exist is dropped from the iteration with no
    warning at all and a zero status. git does that deliberately, in every
    mode it has: the paranoia that widens ref iteration to broken refs turns
    dangling symbolic ones off in the same breath. So the listing comes back
    short by exactly that note, exit zero and stderr empty, and a caller
    spending it on "everything this host began has finished" reads a leftover
    nothing else on this host names as nothing owed at all.

    What the store is holding is asked of the store instead. A symbolic ref is
    never packed -- `packed-refs` has no spelling for one -- so every note
    that could be in that shape is a file under the namespace, and a name
    found there that the listing did not report is a note nobody could read.
    That runs the comparison one way only: a name the listing reported and the
    directory does not hold is an ordinary packed note.
    """
    held = _loose_note_names(spec, prefix)
    if held is None:
        return False
    unlisted = sorted(held - {record.subject for record in records})
    if unlisted:
        log.warning(
            "the notes under %s in %s left out %s",
            prefix, spec.target_root, unlisted,
        )
        return False
    return True


def _loose_note_names(
    spec: config.RepoSpec, prefix: str,
) -> frozenset[str] | None:
    """Every name the loose half of this ref store holds under `prefix`.

    Named relative to the namespace, so what comes back is spelled the way a
    parsed record's subject is and the two compare directly.

    A namespace with nothing under it is a directory that is not there, which
    is the empty answer rather than the failure one: it is what every clone
    that has never owed anything looks like. A store this cannot be located
    in, a namespace that will not be read, and anything under one that is not
    a note or a room for more of them ARE the failure -- what this answers is
    whether a listing was complete, and a walk that quietly left a corner out
    would report the one thing it exists to catch as nothing to catch.
    """
    store = _shared_ref_store(spec.target_root)
    if store is None:
        return None
    room = store / prefix
    if not _stands_as(room, store, stat.S_ISDIR):
        return None
    found: set[str] = set()
    if not _walked_into(room, room, found):
        return None
    return frozenset(found)


def _walked_into(here: Path, room: Path, found: set[str]) -> bool:
    """Collect every note name under `here`, or say the walk did not finish.

    Read entry by entry rather than through a glob, because a glob answers a
    directory it could not read the same way it answers an empty one: it
    swallows the refusal and yields nothing. What that costs here is the whole
    point of the walk -- a namespace this host cannot look into holds notes
    the listing beside it could not read either, and both coming back empty is
    a leftover reported as nothing owed.

    A name that has gone between the listing and this is not a failure. It is
    a note something packed away or took, and what this answers is only which
    names are still standing loose.
    """
    try:
        with os.scandir(here) as scan:
            entries = tuple(scan)
    except FileNotFoundError:
        return True
    except OSError as unreadable:
        log.warning("%s could not be walked: %s", here, unreadable)
        return False
    for entry in entries:
        if not _walked_entry(entry, room, found):
            return False
    return True


def _walked_entry(entry: os.DirEntry, room: Path, found: set[str]) -> bool:
    """Take one entry as a note, as a room holding more of them, or refuse.

    Asked of the entry without following it, for the reason the per-name look
    is: a link is not a note, and a walk that followed one would answer for
    names this store does not keep -- or, for a link leading nowhere, pass
    over a name that IS standing there.

    The lock git holds a note under while it writes one is passed over rather
    than refused. That name is a write in flight, and no listing has to have
    accounted for it.
    """
    if entry.name.endswith(_REF_LOCK_SUFFIX):
        return True
    try:
        held = entry.stat(follow_symlinks=False)
    except OSError as unreadable:
        log.warning("%s could not be looked at: %s", entry.path, unreadable)
        return False
    if stat.S_ISDIR(held.st_mode):
        return _walked_into(Path(entry.path), room, found)
    if not stat.S_ISREG(held.st_mode):
        log.warning("%s is not a note this store wrote", entry.path)
        return False
    found.add(Path(entry.path).relative_to(room).as_posix())
    return True


def _stands_as(where: Path, root: Path, kind: Callable[[int], bool]) -> bool:
    """Whether `where` is one of `kind`, reached by rooms of this store's own.

    Every step from `root` down, looked at without following any of them,
    because following is the whole of what git does with a ref's path and
    `--no-deref` says nothing about it: that flag is about the ref's own
    value, one name deep. A namespace replaced with a link to `refs/heads`
    puts every note this owner writes under that name instead -- the note
    about an issue's branch becoming that branch, which the artifact scan then
    reads back as a candidate -- and has every listing here report somebody
    else's branches as notes this host wrote. Only the last step is a note;
    the ones above it are rooms, and a room that is anything else refuses.

    Nothing there is the ordinary answer, and it stops the walk rather than
    failing it: a note that is packed, a name never written to, a namespace
    nothing has been owed under, and everything below any of them. A path that
    could not be looked at is neither, and refuses.
    """
    walked = root
    for segment in where.relative_to(root).parts:
        walked /= segment
        try:
            held = walked.lstat()
        except FileNotFoundError:
            return True
        except OSError as unreadable:
            log.warning("%s could not be looked at: %s", walked, unreadable)
            return False
        wanted = kind if walked == where else stat.S_ISDIR
        if not wanted(held.st_mode):
            log.warning(
                "%s is not what this store keeps under that name", walked,
            )
            return False
    return True


def _own_way_down(store: Path, ref: str) -> bool:
    """Whether every room on the way to one note is a room of this store's own.

    What a write asks, where a read asks `_stands_as` for the note as well. A
    note already standing there may be anything a later write is allowed to
    replace -- a symbolic ref this repairs, a value an earlier pass left --
    and refusing over one would strand the teardown that has to record
    something before it may go on. The rooms above it are not like that: git
    walks them to reach the name, so a link among them sends the write
    somewhere this owner never writes.
    """
    return _stands_as((store / ref).parent, store, stat.S_ISDIR)


def _shared_ref_store(root: Path) -> Path | None:
    """The git directory one tree and the checkouts hanging off it share.

    Where the notes live whichever tree a command ran in: a linked worktree
    keeps a git directory of its own, and only `HEAD`, `refs/bisect/`, and
    `refs/worktree/` are in it.

    Resolved against the clone rather than asked for absolutely, because git
    answers this one relatively whenever it can and the spelling that pins it
    absolutely is newer than the spelling that does not.

    Run inside the lock its caller holds, since what it locates is where that
    caller is about to read or write.
    """
    try:
        located = commands._git_hardened(
            "rev-parse", "--git-common-dir", cwd=root,
            env_extra=_NO_LAZY_FETCH,
        )
    except Exception:
        log.exception("the ref store of %s could not be located", root)
        return None
    common = (located.stdout or "").strip()
    if located.returncode != 0 or not common:
        log.warning(
            "the ref store of %s did not answer: %s",
            root, (located.stderr or "").strip(),
        )
        return None
    try:
        return (root / common).resolve()
    except (OSError, RuntimeError) as unresolved:
        log.warning(
            "the ref store of %s did not resolve: %s", root, unresolved,
        )
        return None


def _parsed_records(
    listed: str, prefix: str,
) -> tuple[ProvenTip, ...] | None:
    """The records one listing reports, or None when one of them did not read.

    One unreadable line refuses the whole listing rather than the line: what a
    caller spends the answer on is finishing everything this host began, and a
    listing quietly short by one is indistinguishable from one that is
    complete.
    """
    records = []
    for line in listed.splitlines():
        record = _parsed_record(line, prefix)
        if record is None:
            return None
        records.append(record)
    return tuple(records)


def _parsed_record(line: str, prefix: str) -> ProvenTip | None:
    """The record one listing line carries, or None when it carries none.

    Four ways a line is not a record this understands, and all of them are the
    same answer: it does not carry the fields the format asks for, it names a
    ref outside this repository's own namespace, it stands at a value that is
    not its own -- a note somebody made a symbolic ref, whose object id is
    whatever it was aimed at -- or it stands at something no note here is ever
    written at. The last two are what the symref and type fields are asked for
    at all: a listing cannot refuse what it cannot see, and every other reader
    here refuses both outright.
    """
    fields = line.split(_RECORD_SEPARATOR)
    if len(fields) != _RECORD_FIELDS:
        log.warning("a reclaim record did not read: %r", line)
        return None
    ref, sha, kind, symbolic = fields
    if symbolic:
        log.warning("a reclaim record at %r merely points at %r", ref, symbolic)
        return None
    if not _a_note_stands_at(ref, sha, kind):
        log.warning("a reclaim record at %r stands at a %s", ref, kind)
        return None
    if not ref.startswith(prefix):
        log.warning("a reclaim record named %r, outside its own name", ref)
        return None
    return ProvenTip(ref[len(prefix):], sha)
