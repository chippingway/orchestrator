# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a candidate contributes over its base, reduced to one comparable id.

The contribution is the prospective pull request itself -- the frozen base
against the exact candidate commit, three-dot, the same range the count is
taken over and the same one an agent is pointed at, so a base that moved on
since the branch forked is not read as work this branch did. What this owner
answers about it is not how big it is but WHICH one it is: a digest two hosts,
two ticks, and two processes compute the same value for when, and only when,
the contribution in front of them is the same contribution.

Every cheaper answer to that question is wrong in a way somebody can arrange.
An added-line count is equal for any two candidates of the same size. A
subject is prose the agent writes. A rename similarity score is a percentage,
and one that says two paths are related says nothing about what was written
into either. Tree equality asks about the candidate alone, so it calls two
candidates the same when they differ by every line the base already carried
between them, and different when they differ by nothing that will be reviewed.
And `git patch-id` was built to survive rebases, which it does by throwing away
the very things a contribution is: it skips binary content outright, ignores
file modes, and normalizes whitespace, so an executable bit, a swapped image,
and a reindentation are all invisible to it.

So the digest is taken over a canonical byte representation of the whole
contribution: git's raw listing of it, and then the content of every object
that listing names. Neither half is a patch, and that is what makes the answer
independent of everything a repository this host does not own can say. A patch
is rendered content, and rendering is where `.gitattributes`, the user and
system attribute files, a diff driver, textconv, an external diff helper, the
algorithm that pairs a change up, and the threshold above which a blob stops
being text all get their say -- the whole surface the added-line count has to
pin one setting at a time and refuse outright where it cannot. Raw format
renders nothing: each record is the pre-image mode and object id, the
post-image mode and object id, the status, and the path. The content behind
those ids is read as the bytes it is, through plumbing that applies no filter
and converts no line ending. Binary is not a special case, because nothing
here looks inside a blob to decide it is one.

The content is in the digest rather than left to the ids that name it, and the
reason is what a repository this host cannot vouch for can do. An object id IS
a hash of content, but only where something checks the two against each other,
and git does not: it serves a loose object under the name the file sits at, so
one swapped for a different, perfectly valid object is handed out under an id
it does not hash to, and nothing short of `fsck` ever says otherwise. The
store here is the one an agent works in. Hashing the bytes git actually
produces makes that a non-question -- substituted content simply is not the
same contribution and does not fingerprint like one -- and it is what lets the
listing stay a listing rather than becoming a claim somebody has to verify.

What the two halves cover is the whole of what a reviewer would be handed. The
path bytes are in the record, so relocating a file changes the digest. The
content is in the stream, on both sides, binary as much as text. The modes are
their own fields, so a file made executable and nothing else changes it. A
deletion is a record of its own with a post-image of all zeros, so removing a
path is not the absence of evidence. And a rename is reported as the deletion
and the addition it literally is, because `--no-renames` is what makes that
representation deterministic: with detection on, whether one record or two come
back is decided by a similarity threshold and a rename limit that a `git
config` beside the work can retune, so the same contribution would fingerprint
two ways on two hosts.

The remaining pins are the ones a repository could otherwise move: object
names are unabbreviated, since `core.abbrev` shortens them and a prefix is a
weaker claim than an id; submodule changes stay in, since
`diff.ignoreSubmodules` drops a moved gitlink out of a listing that claims to
be complete; the listing is held to the whole repository rather than to a
directory; and the output order is neutralized with an empty order file,
because `diff.orderFile` reorders the records and a digest over a permutation
is a different digest for the same work. The two ends are named as object ids
the caller has already proven, never as refs, so nothing that moves a branch
moves the answer.

Two more sit in the environment, where a `-c` on the command line does not
reach them, and both are about what this store is allowed to be while the
reading is taken. `$GIT_DIR/shallow` is a file the agent's checkout shares
rather than a setting, and a commit named in it is walked as though it had no
parents -- which moves the base a three-dot range resolves to, or removes it,
so the same two objects read as another contribution or as none. And a clone
made with a filter keeps a promisor remote, so git answers an object it is
missing by fetching it rather than by failing: a store that does not hold this
contribution would go and get it mid-reading, and what came back would depend
on what some remote still serves. The shallow file is pointed at an empty one
and lazy fetching is turned off, on this reading's own calls rather than on
every hardened call, because a shallow clone and a partial clone are things a
repository legitimately IS and other operations need them honored. Here the
answer has to come from this store, over the whole history these commits have,
or not at all.

The endpoints decide what is fingerprinted and are deliberately not IN the
fingerprint. Two commits carrying the same work over the same base have to
fingerprint alike -- that is the entire use of an id like this -- and putting
either end in the digest would reduce it to the pair, which the caller already
has.

A reading that could not be taken is never a contribution. Both commits are
proven present before the listing is asked for, so an end this host does not
hold is named as the end it is rather than surfacing as a diff error, and a
listing that failed is a typed failure with no digest beside it -- because
what a failed `git diff` writes to stdout is nothing, the same thing a
candidate that changes nothing writes, and a digest over that would be one
value every broken reading in the fleet agrees on.

Proving the commits is not proving the contribution. A raw listing is produced
by walking trees; it never opens a blob. So a repository holding both commits
and every tree under them, but missing the content at one changed path -- a
fetch that half-arrived, a store pruned under a running tick, an object file
that will not inflate -- lists exactly as a repository holding all of it does,
and git exits 0. Reading the content is what closes that, and the read is
where it is closed rather than in a check standing in front of it. Asking
first and reading second would leave a window between the two answers wide
enough for a `gc` in the checkout or an agent still running beside the tick,
and what falls into it does not come back as an error: an object git cannot
find is reported as the bare word `missing` on the same stdout the digest is
taken over, with a successful exit status to say the request was well formed.
So the answer is read as a protocol rather than as bytes -- every id asked
for, in the order asked, answered as a blob of the length its header claims --
and the content is folded into the digest as it passes that check. What breaks
after a header that inflated fine is caught by the same read, since git stops
mid-stream and says so on the way out. A gitlink is left out of all of it: its
id belongs to the submodule's repository, and requiring it here would refuse
every candidate that touches one.
"""
from __future__ import annotations

import hashlib
import logging
import os
from collections import deque
from pathlib import Path
from types import MappingProxyType

from orchestrator.git import commands
from orchestrator.git.measurement.models import (
    ContributionFingerprint,
    FingerprintFailure,
)
from orchestrator.git.verification import probes as verification_probes

# The channel the rest of this domain reports on, so an operator following a
# reading that could not be taken reads the plumbing they already filter for.
log = logging.getLogger("orchestrator.git_plumbing")

# The format the contribution is canonicalized as. `--raw` is the one that
# names modes and object ids instead of rendering content, so nothing that
# decides how a blob would be DISPLAYED decides what is hashed; `-z` because a
# path is bytes and git's default output would quote an unusual one, which
# makes the representation a function of what the path happens to contain.
_RAW = "--raw"

_NUL_DELIMITED = "-z"

# Object names in full. `core.abbrev` sets how many characters git prints, and
# it lives in the config the agent's worktree shares -- so a listing left to it
# commits to a prefix that a repository can shorten at will.
_NO_ABBREV = "--no-abbrev"

# What makes a rename representable the same way twice: the deletion and the
# addition it consists of. Left detected, whether the contribution comes back
# as one record or two is decided by a similarity threshold and a rename limit
# that `diff.renames`, `diff.renameLimit`, and the size of the diff all move,
# and a score is not evidence about content anyway.
_NO_RENAMES = "--no-renames"

# Spelled on the command line because `diff.ignoreSubmodules=all` in the
# agent-writable config would drop a moved gitlink out of a listing that claims
# to cover the whole contribution.
_IGNORE_SUBMODULES_NONE = "--ignore-submodules=none"

# `diff.relative` restricts a diff to the directory it is run from. Every call
# here runs at the root of the worktree, so it changes nothing today -- and it
# is stated anyway, because completeness is the whole of what this digest
# claims and no config in the checkout may narrow it.
_NO_RELATIVE = "--no-relative"

# The order the records come out in, pinned by handing git an order file with
# no patterns in it: `diff.orderFile` promotes matching paths to the front, and
# a digest over a permutation of the same records is a different digest for
# the same work. An empty file overrides the config and reorders nothing, and
# `/dev/null` is the one empty file no repository can plant content into.
_NO_ORDER_FILE = f"-O{os.devnull}"

# The two things this reading is pinned against in the ENVIRONMENT, because
# neither answers to config and so no `-c` on the command line reaches either.
#
# `$GIT_DIR/shallow` is a file in the git directory the agent's worktree
# shares, and what it does is cut history: a commit named in it is walked as
# though it had no parents, which moves the merge base a three-dot range
# resolves to -- or removes it, so the same two objects read as a different
# contribution, or as none. Pointed at an empty file, the range is taken over
# the whole history the objects really have.
#
# Lazy fetching is the other. A clone made with a filter keeps a promisor
# remote, and git answers an object it is missing by fetching it rather than
# by failing -- so a store that does not hold this contribution would go and
# get it mid-reading, turning a local digest into a network operation whose
# result depends on what some remote still serves. Off, an object that is not
# here is an object that is not here.
#
# Neither is disabled for every hardened call, because a shallow clone and a
# partial clone are things a repository legitimately IS: a rebase in one needs
# the objects fetched, and a checkout of one has no history past the boundary.
# What this reading needs is narrower -- that it be answerable from this store
# alone, over the whole history these commits have -- so the pins ride on its
# own calls, and a repository that cannot answer under them refuses rather
# than reporting something else.
_LOCAL_AND_WHOLE = MappingProxyType({
    "GIT_SHALLOW_FILE": os.devnull,
    "GIT_NO_LAZY_FETCH": "1",
})

# What the digest is domain-separated by. The bytes git writes are hashed
# behind a label naming what they are, so a fingerprint cannot collide with a
# digest something else in this system takes over some other listing, and a
# later representation is a different scheme rather than a silently different
# answer under the same name.
_SCHEME = b"chipping-orchestrator/prospective-diff/1\0"

# How the failing call's own line is read for a human. Lossy is fine here and
# nowhere else in this module: this is prose an operator reads, not the bytes
# the digest is taken over.
_DETAIL_ENCODING = "utf-8"

# The shape of one `--raw -z` record, which is read to find out which objects
# the digest would be committing to. The metadata is
# `:<srcmode> <dstmode> <srcsha> <dstsha> <status>`, and the path that follows
# it is a separate NUL-terminated field -- which is why the whole listing
# alternates metadata and path and a stream that does not is one this build
# cannot account for.
_RECORD_PREFIX = b":"

_FIELD_SEPARATOR = b" "

_NUL_SEPARATOR = b"\0"

_METADATA_FIELDS = 5

# The two sides of one record: a pre-image and a post-image, each a mode and
# an object id, laid out as the modes and then the ids.
_SIDES = 2

_RECORD_FIELDS = 2

# The one mode whose object id belongs to another repository. A gitlink names a
# commit in the submodule, which this store has no reason to hold and normally
# does not, so it is left out of what has to be readable here -- otherwise
# every candidate that touches a submodule would be refused a fingerprint.
_GITLINK_MODE = b"160000"

# The id git writes for the side of a record that does not exist: all zeros on
# an addition's pre-image and a deletion's post-image. It names no object, so
# nothing is asked about it.
_NULL_DIGIT = b"0"

# The one read that both hands over the content and says whether it is really
# the content asked for. `--batch` answers each id on stdin with either
# `<oid> blob <size>` and that many bytes, or the bare `<oid> missing` it
# prints for an object it cannot unpack -- and it exits 0 either way, so what
# separates the two is reading the answer rather than the status.
_BATCH = "--batch"

# What every answer has to be. Every non-gitlink side of a raw record is a
# blob, since `git diff --raw` reports no tree entries, so any other type is a
# listing this owner has misread rather than content to hash.
_BLOB = b"blob"

# The fields of one answered header, and the longest one worth waiting for.
# A header is an id, a type, and a count; the bound is what keeps a stream
# that never sends a newline from being accumulated forever.
_HEADER_FIELDS = 3

_HEADER_LIMIT = 256

_LINE_SEPARATOR = b"\n"


def _fingerprint_contribution(
    worktree: Path, base_sha: str, candidate_sha: str,
) -> ContributionFingerprint:
    """Fingerprint what `candidate_sha` contributes over `base_sha`.

    Both ends are ids the caller established, and naming them is what makes
    the answer comparable at all: the same pair fingerprints to the same digest
    on the next tick, on a retry after a crash, and on another host, and
    nothing here consults a ref, so neither the branch moving nor the base
    advancing changes what a proven pair says.

    Hardened for the reason every read of an agent-writable worktree is, and
    for one that belongs to a digest in particular: object replacement would
    have git list the contribution of a commit nobody wrote under the id the
    caller named, so the envelope that turns it off is what ties this
    fingerprint to the work that gets published.

    Read as bytes rather than as text, because that is what a digest is over.
    A decoded capture folds a CR LF pair and a lone CR into one LF, which is
    lossy about a path -- and a fingerprint that cannot tell two committed
    paths apart is the one thing it may never be.

    Nothing is hashed until every object the listing names has been proven
    present here, and what is hashed then is the content itself. The listing
    is produced from trees alone, so it succeeds over content this repository
    does not hold, and a digest taken on that reading alone would be a claim
    about bytes nobody here can produce -- one that compares equal to the same
    claim made on a host where the content really is.
    """
    absent = _absent_end(worktree, base_sha, candidate_sha)
    if absent is not None:
        return _refused(worktree, base_sha, candidate_sha, absent)
    listed = commands._git_hardened_bytes(
        "diff", _RAW, _NUL_DELIMITED, _NO_ABBREV, _NO_RENAMES,
        _IGNORE_SUBMODULES_NONE, _NO_RELATIVE, _NO_ORDER_FILE,
        f"{base_sha}...{candidate_sha}",
        cwd=worktree,
        env_extra=_LOCAL_AND_WHOLE,
    )
    if listed.returncode != 0:
        return _refused(
            worktree, base_sha, candidate_sha,
            FingerprintFailure.DIFF_FAILED,
            commands._first_reported_line(
                (listed.stderr or b"").decode(
                    _DETAIL_ENCODING, commands._UNDECODABLE_BYTES,
                ),
            ),
        )
    required = _required_objects(listed.stdout or b"")
    if required is None:
        return _refused(
            worktree, base_sha, candidate_sha,
            FingerprintFailure.DIFF_UNREADABLE,
        )
    digest = _digest_over(worktree, listed.stdout or b"", required)
    if not digest:
        return _refused(
            worktree, base_sha, candidate_sha,
            FingerprintFailure.CONTENT_ABSENT,
        )
    return ContributionFingerprint(
        base_sha=base_sha, candidate_sha=candidate_sha, digest=digest,
    )


def _refused(
    worktree: Path,
    base_sha: str,
    candidate_sha: str,
    failure: FingerprintFailure,
    detail: str = "",
) -> ContributionFingerprint:
    """Report a pair that has no fingerprint, and build the record saying so.

    Every way this reading stops goes through here, so the line an operator
    finds names the same pair and the same worktree whichever step it was. The
    typed member is what the record carries and what a caller branches on; the
    line beside it is the failing call's own, and only some steps have one.
    """
    log.warning(
        "%s...%s cannot be fingerprinted in %s: %s",
        base_sha, candidate_sha, worktree,
        f"{failure} ({detail})" if detail else failure,
    )
    return ContributionFingerprint(
        base_sha=base_sha,
        candidate_sha=candidate_sha,
        failure=failure,
        detail=detail,
    )


def _required_objects(listing: bytes) -> tuple[bytes, ...] | None:
    """The batch input naming every object, or None if the listing is unread.

    Two ways a stream git exited 0 on can still be partial, and both are read
    off its shape. Every field a listing has -- each metadata block and each
    path -- is NUL-TERMINATED rather than NUL-separated, so a non-empty
    listing that does not end in one lost its tail somewhere: the last path
    arrived cut short, and a reader that took what came would name an object
    for a path that is not the committed one. An odd number of fields is the
    same loss one field earlier, with the path missing outright.

    Sorted and deduplicated: the same blob is routinely on both sides of one
    contribution, and the order the content is read in -- which is the order
    it is hashed in, and the order each answer is checked against -- has to
    come from the ids rather than from the order git happened to list them.
    """
    if not listing:
        return ()
    if not listing.endswith(_NUL_SEPARATOR):
        return None
    fields = listing.split(_NUL_SEPARATOR)
    fields.pop()
    if len(fields) % _RECORD_FIELDS:
        return None
    required: set[bytes] = set()
    for metadata in fields[::_RECORD_FIELDS]:
        named = _record_objects(metadata)
        if named is None:
            return None
        required.update(named)
    return tuple(sorted(required))


def _record_objects(metadata: bytes) -> tuple[bytes, ...] | None:
    """The object ids one record names, or None if it is not a record.

    Both sides are taken. The pre-image is as much of the contribution as the
    post-image -- it is the content the change was made against, and the digest
    commits to it by id -- so a base-side blob this host has lost leaves the
    same unverifiable claim a missing new one does.
    """
    if not metadata.startswith(_RECORD_PREFIX):
        return None
    fields = metadata[len(_RECORD_PREFIX):].split(_FIELD_SEPARATOR)
    if len(fields) != _METADATA_FIELDS:
        return None
    modes = fields[:_SIDES]
    shas = fields[_SIDES:_SIDES + _SIDES]
    return tuple(
        sha
        for mode, sha in zip(modes, shas, strict=True)
        if mode != _GITLINK_MODE and sha and sha.strip(_NULL_DIGIT)
    )


class _BatchReading:
    """One `--batch` answer, hashed and checked against the ask as it arrives.

    Both jobs are done in the same pass over the same bytes, and that is the
    point rather than an economy. Asking a separate command whether the
    objects are there and then reading them leaves a window between the two
    answers: an object that goes in it -- a `gc` in the checkout, an agent
    still running beside the tick -- comes back from the read as the bare word
    `missing`, on the very stdout the digest is taken over, with git exiting 0
    to say the request was well formed. A reading that checked beforehand
    would hash that sentence and hand back an id for it. Checked as it
    arrives, there is no beforehand to be wrong about.

    What is checked is the protocol itself: every id asked for is answered, in
    the order it was asked, as a blob, with the byte count the header claims;
    anything else leaves the reading not whole and there is no digest. The
    content is fed to the digest as it passes, so nothing is held but the
    header being assembled.
    """

    def __init__(self, asked: tuple[bytes, ...], digest) -> None:
        """Expect these ids, in this order, hashing into this digest."""
        self._awaited = deque(asked)
        self._digest = digest
        self._header = b""
        self._remaining = 0
        self._broken = False

    @property
    def is_whole(self) -> bool:
        """Whether every object asked for arrived, entire and as itself."""
        return not (
            self._broken or self._awaited or self._remaining or self._header
        )

    def consume(self, chunk: bytes) -> None:
        """Take one piece of the answer: hash it, and read what it says."""
        self._digest.update(chunk)
        while chunk and not self._broken:
            chunk = self._advance(chunk)

    def _advance(self, chunk: bytes) -> bytes:
        """Account for as much of this piece as the current record wants."""
        if self._remaining:
            taken = min(self._remaining, len(chunk))
            self._remaining -= taken
            return chunk[taken:]
        line, found, rest = (self._header + chunk).partition(_LINE_SEPARATOR)
        if not found:
            self._header = line
            self._broken = len(line) > _HEADER_LIMIT
            return b""
        self._header = b""
        self._open(line)
        return rest

    def _open(self, header: bytes) -> None:
        """Begin the record this header announces, or refuse the reading.

        The count is taken as the header states it and one byte is added for
        the newline git ends a record with: an object's content is bytes, so
        where it stops is not something to look for, and a count that did not
        match would leave the next header unreadable anyway.
        """
        fields = header.split(_FIELD_SEPARATOR)
        if len(fields) != _HEADER_FIELDS or not self._awaited:
            self._broken = True
            return
        named, kind, size = fields
        if named != self._awaited.popleft() or kind != _BLOB:
            self._broken = True
            return
        if not size.isdigit():
            self._broken = True
            return
        self._remaining = int(size) + 1


def _absent_end(
    worktree: Path, base_sha: str, candidate_sha: str,
) -> FingerprintFailure | None:
    """Which end this host cannot read, or None when it holds both.

    Asked before the listing rather than inferred from it, because a `git
    diff` naming an object that is not here fails the same way a `git diff`
    fails for any other reason, and the two send an operator to different
    places: a missing end is a fetch, and everything else is the checkout.
    Which end is missing matters for the same reason -- a base this clone has
    not caught up to and a candidate committed on another host are not the same
    situation, and neither is fixed by looking at the other.

    Base first, so a reading with both ends missing reports the one a caller
    would have to supply first anyway.

    Asked under this reading's own pins, like everything else it does. A clone
    made with a filter answers an id it does not hold by fetching it, so an
    end recorded on another host -- which is exactly what this step exists to
    catch -- would be brought in over the network and reported present, and
    the reading would go on to fingerprint a contribution the store never had.
    """
    if not verification_probes._commit_present(
        worktree, base_sha, env_extra=_LOCAL_AND_WHOLE,
    ):
        return FingerprintFailure.BASE_ABSENT
    if not verification_probes._commit_present(
        worktree, candidate_sha, env_extra=_LOCAL_AND_WHOLE,
    ):
        return FingerprintFailure.CANDIDATE_ABSENT
    return None


def _digest_over(
    worktree: Path, listing: bytes, asked: tuple[bytes, ...],
) -> str:
    """The digest of one contribution: its listing, then the content it names.

    Neither half needs framing of its own. Every field of the listing ends in
    a NUL and a path may hold any byte but that one, so it parses exactly one
    way; and git's own batch framing puts each object behind the id and byte
    count it is answering for, in the order the ids were asked in, so the
    content of one object cannot be read as the beginning of another.

    The content is here rather than left to the ids because an id is only a
    claim about content while something checks it. This store is one an agent
    can write into, and git does not re-hash an object it reads -- a loose
    file swapped for a different, perfectly valid object is served under the
    name it was filed as, and only `fsck` ever notices. Hashing what git
    actually hands over settles it without a verification step: a substituted
    object simply is not the same contribution, and it does not fingerprint
    like one.

    Streamed rather than collected, since the content of a contribution is as
    large as an agent committed it. Empty whenever the content cannot be
    accounted for -- an object this store will not answer for as a blob, or a
    stream that stopped partway -- so a caller cannot tell a half-hashed
    reading from a whole one by looking at the digest: there is not one.
    """
    digest = hashlib.sha256(_SCHEME + listing)
    if not asked:
        return digest.hexdigest()
    reading = _BatchReading(asked, digest)
    streamed = commands._git_hardened_streamed(
        "cat-file", _BATCH,
        cwd=worktree,
        stdin_bytes=_LINE_SEPARATOR.join(asked) + _LINE_SEPARATOR,
        consume=reading.consume,
        env_extra=_LOCAL_AND_WHOLE,
    )
    if streamed.returncode != 0 or not reading.is_whole:
        return ""
    return digest.hexdigest()
