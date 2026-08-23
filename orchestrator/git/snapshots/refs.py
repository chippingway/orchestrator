# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Creating, proving, and reclaiming one immutable snapshot ref.

Three operations, each of which answers with what it established rather than
with a bare boolean, because the caller's next move differs per answer: a ref
already at the exact candidate is the crashed tick's own work and the step is
done, a ref at some other commit is a namespace collision nobody may resolve
automatically, and a remote nobody could ask is a retry rather than a verdict.

**Create is create-or-verify.** The remote is asked first, and what it says
decides the write: nothing there is created under a lease that says so, the
exact candidate is the answer this call wanted, and anything else is reported
as a mismatch and left exactly where it is. There is no branch here that
overwrites -- an immutable ref that can be re-pointed is not immutable, and the
one thing worse than failing to preserve a candidate is preserving something
else under the name every child is about to be told to read.

**Proving is a fetch, not a read.** `ls-remote` says a ref resolves to a SHA on
the server; it does not say the objects behind it can be obtained. What every
child is promised is that they can obtain this candidate, so the ref is fetched
back into the clone the worktrees share and resolved there, and only a local
resolution equal to the frozen candidate is a proof. A namespace the token can
write and not read would otherwise pass every check until the first child tried
to use it.

Where it lands is qualified by the repository it came from, and the fetch and
the resolution are one locked step. Several `REPOS` entries may share a
`target_root`, so the clone a snapshot is fetched into is a store two of them
write: an unqualified local name would have the second force-fetch overwrite
the first, and a resolution taken after the lock was released would answer for
whichever fetch landed last. Both are the same failure read two ways -- a
verification against a candidate this call never saw, and a child copying files
out of the other repository's work.

**Absent is success.** A deletion that finds no ref has nothing to reclaim, and
saying so is what makes reclamation idempotent across the crash between the
push that deleted a ref and the write that would have recorded it. What is
still there is deleted under a lease pinned to the SHA this call just read, so
a ref somebody re-pointed in between is refused rather than destroyed.

Every ref is checked against the namespace before anything is asked of the
remote, because the value arrives from a durable ledger a human can edit and
all three operations are writes -- or, in the delete's case, a destruction --
against somebody's repository.
"""
from __future__ import annotations

import logging
from enum import Enum
from pathlib import Path
from typing import Optional

from orchestrator import config
from orchestrator.git import authentication, commands, locks
from orchestrator.git.snapshots import namespace
from orchestrator.git.worktrees import paths

# The channel the authenticated transport already reports on: these are an
# `ls-remote`, a push, a fetch, and a `rev-parse`, so an operator following a
# snapshot that could not be taken reads the same plumbing they filter for
# when a fetch or a push misbehaves.
log = logging.getLogger("orchestrator.git_plumbing")

# The lease that says the ref must not exist yet, which is the only lease a
# create may run under.
_ABSENT_LEASE = ""

# What separates a truncated repository segment from the digest that keeps it
# injective, in the spelling the branch namespace already uses for its own
# lossy rewrites.
_DIGEST_MARK = "__h"


class SnapshotOutcome(Enum):
    """What one snapshot operation established.

    A plain `Enum` rather than a `StrEnum`: nothing here is written to a pinned
    comment or a sink -- what a caller records is the ledger entry's own state
    -- so a member renamed here is a refactor rather than a migration.
    """

    CREATED = "created"
    PRESENT = "present"
    PROVEN = "proven"
    MISMATCH = "mismatch"
    UNREADABLE = "unreadable"
    REFUSED = "refused"
    ABSENT = "absent"
    DELETED = "deleted"


# The two readings a reclamation may act on: the ref this generation
# preserved, and one an earlier attempt already took. Anything else -- another
# commit under the name, or a remote that could not be asked -- is left exactly
# as it stands, mirror included.
_RECLAIMABLE = frozenset((
    SnapshotOutcome.PRESENT, SnapshotOutcome.ABSENT,
))


def create_snapshot_ref(
    spec: config.RepoSpec, worktree: Path, *, ref: str, sha: str,
) -> SnapshotOutcome:
    """Preserve one exact commit under `ref`, or say why it was not.

    `PRESENT` and `CREATED` are both success and are kept apart because only
    one of them wrote anything: a retry after a crash finds the ref it already
    pushed and reports `PRESENT`, which is what tells an operator reading the
    log that the second attempt cost a read rather than a write.

    `MISMATCH` is never resolved here. A ref in this namespace is derived from
    one generation's identity, so another commit under it means either an
    identity two adjudications shared or somebody writing into the namespace by
    hand -- and both of those are questions for a human, while the automatic
    answer would be overwriting the only copy of somebody's candidate.
    """
    if not namespace.is_snapshot_ref(ref):
        log.error("refusing to create %r: not a snapshot ref", ref)
        return SnapshotOutcome.REFUSED
    observed = authentication._remote_ref_sha(spec, worktree, ref)
    if observed is None:
        return SnapshotOutcome.UNREADABLE
    if observed == sha:
        return SnapshotOutcome.PRESENT
    if observed:
        log.error(
            "%s already carries %s at %s, not the candidate %s it was to "
            "preserve; leaving it untouched",
            spec.slug, ref, observed, sha,
        )
        return SnapshotOutcome.MISMATCH
    created = authentication._push_ref(
        spec, worktree, ref=ref, revision=sha, expected=_ABSENT_LEASE,
    )
    return SnapshotOutcome.CREATED if created else SnapshotOutcome.REFUSED


def prove_snapshot_ref(
    spec: config.RepoSpec, worktree: Path, *, ref: str, sha: str,
) -> SnapshotOutcome:
    """Fetch the snapshot back and prove it resolves here to `sha`.

    The half an `ls-remote` cannot answer. Every child this split creates is
    told to read the candidate out of this ref, so what has to be established
    is that the ref can be OBTAINED -- a namespace a token may write and not
    read, or one a fetch refspec cannot name, would pass a remote read and fail
    the first child that tried to use it.

    `MISMATCH` here is the sharper of the two mismatches: the remote agreed a
    moment ago and what landed locally is a different commit, so nothing about
    the candidate the children would be cut from can be vouched for.
    """
    if not namespace.is_snapshot_ref(ref):
        log.error("refusing to fetch %r: not a snapshot ref", ref)
        return SnapshotOutcome.REFUSED
    mirror = local_snapshot_ref(spec, ref)
    # One lock over both, because the answer is about what THIS fetch brought:
    # another worktree of the same target root fetching the same ref between
    # them would have the resolution report on its landing rather than ours.
    with locks._target_root_lock(spec.target_root):
        fetched = authentication._authed_fetch(
            spec, f"+{ref}:{mirror}", cwd=worktree,
        )
        if fetched.returncode != 0:
            log.error(
                "%s: %s could not be fetched back after it was created: %s",
                spec.slug, ref, (fetched.stderr or "").strip(),
            )
            return SnapshotOutcome.REFUSED
        resolved = _local_ref_sha(worktree, mirror)
    if resolved == sha:
        return SnapshotOutcome.PROVEN
    log.error(
        "%s: %s was fetched but resolves here to %r rather than to the "
        "candidate %s", spec.slug, ref, resolved, sha,
    )
    return SnapshotOutcome.MISMATCH


def delete_snapshot_ref(
    spec: config.RepoSpec, worktree: Path, *, ref: str, sha: str,
) -> SnapshotOutcome:
    """Reclaim one snapshot ref, treating an absent one as already reclaimed.

    `ABSENT` is a success and is reported as its own answer rather than folded
    into `DELETED`, because the two describe different histories: one of them
    is this call's write, and the other is a call that already happened and
    whose record never landed. A reclamation retried after a crash is the
    second one, every time.

    `sha` is the commit the caller preserved, and it is required rather than
    inferred. Leasing against whatever the ref happens to be at now would
    delete a re-pointed ref as readily as ours: the read would observe the new
    commit, the lease would match it, and the delete would succeed -- which is
    the blind write the create refuses, aimed at destruction, and this is the
    one operation whose blast radius is somebody else's content rather than a
    refused push. So a ref carrying anything but the exact candidate this
    generation preserved is a `MISMATCH` and is left alone for a human, and
    the lease is pinned to that expected commit rather than to the reading.

    **This host's copy goes first, and the remote is not touched until it has
    provably gone.** A child of a split reads a surviving mirror as proof that
    nobody has reclaimed its ancestor's ref, which is what keeps a per-tick
    guard off the network -- and that reading is only sound if the mirror can
    never outlive the remote ref. Taking the remote first left exactly the
    state the guard cannot tell from an untouched world whenever the local
    delete failed, since that delete is best-effort against this host's disk.
    So the order is inverted, and a mirror that will not go -- or that cannot
    be PROVEN gone -- is a `REFUSED` reclamation: the obligation stays owed,
    the umbrella stays open, and an operator has something to see. Dropping a
    cache early is the harmless direction -- the ref is still on the remote,
    and the reuse instructions every child carries fetch it again.

    Which is also why the read comes before the drop rather than after it. A
    ref carrying another commit is somebody else's content, and a mirror
    dropped ahead of discovering that would throw away this host's only copy
    of a candidate this call then refuses to reclaim.
    """
    if not namespace.is_snapshot_ref(ref):
        log.error("refusing to delete %r: not a snapshot ref", ref)
        return SnapshotOutcome.REFUSED
    observed = observed_snapshot_ref(spec, worktree, ref=ref, sha=sha)
    if observed not in _RECLAIMABLE:
        return observed
    if not _mirror_dropped(spec, worktree, ref):
        return SnapshotOutcome.REFUSED
    if observed == SnapshotOutcome.ABSENT:
        return observed
    return _taken_from_remote(spec, worktree, ref, sha)


def observed_snapshot_ref(
    spec: config.RepoSpec, worktree: Path, *, ref: str, sha: str,
) -> SnapshotOutcome:
    """What the remote holds under one snapshot ref, writing nothing.

    The read half of the deletion, published because a caller sometimes has
    to know whether a ref is still there WITHOUT being allowed to take it: a
    reclamation already ordered against consumers that have since come back
    is retryable only if what it is retrying has already happened. Asking is
    one request and answers that question exactly; assuming either way
    answers it wrong -- either by stranding a ledger against a ref nothing
    can prove is gone, or by deleting one a live child came back for.

    `PRESENT` is the candidate this generation preserved and nothing else. A
    ref carrying another commit is a `MISMATCH` whether it is being read or
    reclaimed, and is left alone under both.

    `sha` is that candidate and is required, for the reason the delete
    requires it: an occupancy check is not an obtainability check. A caller
    with no commit to name would be told a re-pointed ref is `PRESENT` and
    would act on a promise nobody made -- so a caller that does not hold the
    commit establishes it first, from the record that preserved it, rather
    than asking a weaker question here.
    """
    if not namespace.is_snapshot_ref(ref):
        log.error("refusing to ask about %r: not a snapshot ref", ref)
        return SnapshotOutcome.REFUSED
    observed = authentication._remote_ref_sha(spec, worktree, ref)
    if observed is None:
        return SnapshotOutcome.UNREADABLE
    if not observed:
        return SnapshotOutcome.ABSENT
    if observed != sha:
        log.error(
            "%s: %s carries %s rather than the candidate %s it preserved; "
            "leaving it untouched", spec.slug, ref, observed, sha,
        )
        return SnapshotOutcome.MISMATCH
    return SnapshotOutcome.PRESENT


def _taken_from_remote(
    spec: config.RepoSpec, worktree: Path, ref: str, sha: str,
) -> SnapshotOutcome:
    """Ask the remote to let go of the one ref this generation preserved."""
    deleted = authentication._delete_remote_ref(
        spec, worktree, ref=ref, expected=sha,
    )
    return SnapshotOutcome.DELETED if deleted else SnapshotOutcome.REFUSED


def local_snapshot_ref(spec: config.RepoSpec, ref: str) -> str:
    """The local ref THIS repository's copy of one snapshot lands under.

    The repository segment is the same sanitized slug the per-issue branch
    namespace is built from, so what keeps two `REPOS` entries off one
    another's branches keeps them off one another's snapshots. Published
    because the child a split creates is told to read the snapshot out of this
    name, so the instruction and the fetch have to be one string.

    Bounded here rather than by the namespace, because bounding it is a
    rewrite and a rewrite has to stay injective: configuration bounds a slug
    at nothing, so a long one is replaced by a prefix of itself plus the
    content digest the branch namespace already uses for its own lossy
    rewrites. Two repositories with a shared prefix therefore still land on
    two refs, which is the whole property the segment exists for.
    """
    return namespace.local_snapshot_ref(
        ref=ref, repository=_repository_segment(spec.slug),
    )


def local_snapshot_present(
    spec: config.RepoSpec, worktree: Path, *, ref: str, sha: str,
) -> bool:
    """Whether this host still holds its copy of one snapshot, at `sha`.

    The free half of "is this snapshot still there", and it is sound because
    of the ORDER a reclamation runs in rather than as a guess about it: the
    mirror is taken down first and the remote ref is not touched until it has
    provably gone, so a mirror still here says this host has reclaimed
    nothing. That is enough for a reader that only needs to know whether it
    may still reuse the candidate, and it costs a local `rev-parse` and no
    network at all -- which is what keeps a per-tick guard off the wire for
    every child of a live split.

    `sha` is the commit the caller was promised, and it is required rather
    than optional because this ref lives in the object store the agents' own
    worktrees share. A name that resolves to SOMETHING says only that a ref
    exists under it: an agent -- or anything else with the clone -- can point
    it at whatever it likes, and a reader that asked about existence alone
    would then answer "not reclaimed" for a mirror carrying another commit
    entirely. That answer is spent twice over: the child resumes against work
    nobody adjudicated, and the remote it would otherwise have asked -- the
    one that would have said `ABSENT` or `MISMATCH` and parked it -- is never
    asked at all. So the reading is an identity check, and only the exact
    candidate this ref preserved answers yes.

    Peeled to a commit by the resolution below, so a mirror pointed at a tag
    object wrapping the candidate still answers for the candidate; every other
    commit, and every unreadable store, answers no and sends the caller to the
    remote, which is the authority anyway.
    """
    if not sha:
        return False
    return _local_ref_sha(worktree, local_snapshot_ref(spec, ref)) == sha


def _repository_segment(slug: str) -> str:
    """A ref-safe, bounded, injective segment naming one repository."""
    sanitized = paths._sanitize_branch_segment(slug)
    if len(sanitized) <= namespace.MAX_REPOSITORY_SEGMENT:
        return sanitized
    digest = paths._slug_digest(slug)
    kept = namespace.MAX_REPOSITORY_SEGMENT - len(digest) - len(_DIGEST_MARK)
    return _DIGEST_MARK.join((sanitized[:kept], digest))


def _mirror_dropped(
    spec: config.RepoSpec, worktree: Path, ref: str,
) -> bool:
    """Take this host's copy of a snapshot down, and say whether it went.

    Answered by a READ rather than by an exit code, for the reason every
    teardown in this repository is: `update-ref -d` is best-effort against a
    ref store other worktrees of the same clone share, and a caller whose next
    step depends on the answer may not trust the return of the command that
    was supposed to produce it. A ref that was never fetched is already gone
    and answers yes without a complaint of its own.

    What depends on the answer is the remote delete above it, and through that
    the child-side reuse guard: a mirror is what says "no reclamation has
    happened" without spending a request, so one left standing beside a
    reclaimed remote ref is a child cleared to work from a candidate nobody
    vouches for any more. A mirror nothing deletes also holds the snapshot's
    objects against `gc` for as long as the clone lives.

    Which is why the read has to ESTABLISH the mirror is gone rather than
    merely fail to find it: a delete that failed and a verification that could
    not run are the same tick, and that tick is precisely the one this order
    exists to stop.
    """
    mirror = local_snapshot_ref(spec, ref)
    with locks._target_root_lock(spec.target_root):
        dropped = commands._git_hardened(
            "update-ref", "-d", mirror, cwd=worktree,
        )
        gone = _local_ref_absent(worktree, mirror)
    if gone:
        return True
    log.error(
        "%s: local snapshot %s was not proven gone (%s); leaving %s on the "
        "remote rather than reclaiming it behind a copy that may outlive it",
        spec.slug, mirror, (dropped.stderr or "").strip(), ref,
    )
    return False


def _local_ref_absent(worktree: Path, ref: str) -> bool:
    """Whether the ref store was read and holds nothing under `ref`.

    An established absence rather than a resolution that failed, and the two
    are different answers however alike they look: `rev-parse` reports a ref
    that is not there, a git directory that has gone, and a store nothing can
    read with the same non-zero exit. A teardown verified through it therefore
    reads "could not ask" as "already gone" -- so the one tick where both the
    delete and the check fail is the one that takes the remote ref while this
    host's copy is still standing, which is the exact state the child-side
    guard cannot tell from a world nothing was reclaimed in, and it lasts
    until a receipt lands.

    `for-each-ref` separates the two by exit code: it succeeds and names
    nothing when the store holds no such ref, and fails when the store could
    not be read at all. What it printed is matched by name rather than
    counted, because a ref is also a prefix pattern -- what was asked about is
    this exact ref, and something nested under its name is not it.
    """
    listed = commands._git_hardened(
        "for-each-ref", "--format=%(refname)", "--end-of-options", ref,
        cwd=worktree,
    )
    if listed.returncode != 0:
        log.error(
            "could not read %s in %s: %s",
            ref, worktree, (listed.stderr or "").strip(),
        )
        return False
    return ref not in (listed.stdout or "").split()


def _local_ref_sha(worktree: Path, ref: str) -> Optional[str]:
    """Resolve a fetched snapshot ref in this checkout, or None.

    Hardened for the reason every read of an agent-writable worktree is, and
    for the one that matters most to a commit named by id: `refs/replace/` and
    the graft file both make git answer for one commit under another's name,
    and both live in the clone the agent's worktree shares. Peeled to a commit
    so a ref somebody pointed at a tag object reads as the work rather than as
    the label on it.
    """
    resolved = commands._git_hardened(
        "rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}",
        cwd=worktree,
    )
    named = (resolved.stdout or "").strip()
    if resolved.returncode != 0 or not named:
        return None
    return named
