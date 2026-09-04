# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a contribution's digest covers, survives, and refuses to be taken over.

The covering cases run against real commits because every one of them is a
question about git's own output: whether a mode change appears in a listing at
all, what a moved file comes back as with detection off, which bytes of a path
arrive when git is told not to quote it. A fake would answer whatever the test
expected, which proves nothing about a digest whose whole value is that two
hosts computing it agree. The changes that have to produce a modification, a
deletion, or a rename record are made to paths the BASE branch carries, since
a path first written on the candidate's own branch is an addition however it
is edited afterwards.

The interference cases plant what an agent can really plant, since whether a
`-c` on the command line reaches a setting is not something a mock can answer.
The failure cases drive the reading off the rails, which is where a digest is
dangerous: a `git diff` that failed writes the same empty stdout a candidate
changing nothing writes, and a listing over content this host has lost reads
exactly like one over content it holds -- so those are taken against a real
store with the objects really removed, corrupted, and swapped for others under
the names they were filed at.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

from orchestrator.git import commands
from orchestrator.git.measurement import additions, fingerprint
from orchestrator.git.measurement.models import FingerprintFailure
from tests.git.measurement import measurement_test_support as _support

_FEATURE_PATH = "feature.py"
_OTHER_PATH = "other.py"
_MOVED_PATH = "moved/legacy.py"
_BINARY_PATH = "logo.png"
_SUBMODULE_PATH = "vendor/dep"
_ORDER_FILE = "order.txt"
_GIT_FAILURE = 128
_HARDENED_BYTES = "_git_hardened_bytes"

_TWO_LINES = "one\ntwo\n"
_THREE_LINES = "one\ntwo\nthree\n"
_TWO_LINE_COUNT = 2

# How many characters of an object id name the directory it is stored under.
_OBJECT_DIR_LENGTH = 2

# What a checked-out file is set to when the case is the executable bit and
# nothing else. Every path a fresh checkout writes is readable-by-all already.
_EXECUTABLE_MODE = 0o755

# The parts of a repository this file reaches into directly, because what is
# being planted or counted is not something git offers a command for.
_SHALLOW_FILE = ".git/shallow"
_PACK_DIR = ".git/objects/pack"
_PACK_GLOB = "*.pack"

# The clone that leaves its content behind: no blobs, no checkout to pull them
# in, and a real transport rather than the hardlinks a local path would get.
_ORIGIN_DIR = "origin"
_CLONE_DIR = "clone"
_QUIET = "-q"
_EMPTY_COMMIT = "--allow-empty"
_ORDER_KEY = "diff.orderFile"
_BLOBLESS = "--filter=blob:none"
_NO_CHECKOUT = "--no-checkout"
_NO_LOCAL = "--no-local"

# Content git has to call binary, and the same content with one byte changed.
# Neither has a line in it to add, so the added-line count is the same number
# for both -- which is the reading a fingerprint exists to be better than.
_BINARY_PAYLOAD = b"\x00\x01\x02not text at all\x00\xff"
_BINARY_VARIANT = b"\x00\x01\x02not text at all\x00\xfe"

# Two paths that differ by one byte, and by exactly the byte a decoded capture
# throws away: text mode folds a CR LF pair into a single LF, so a listing read
# as text names the same path for both of these.
_CARRIAGE_RETURN_PATH = "cr\r\nname.txt"
_NEWLINE_PATH = "cr\nname.txt"

# Paths git would quote in its default output, and one of them is not text at
# all: a name is bytes, and nothing says they decode.
_TABBED_PATH = "tab\tname.txt"
_UNDECODABLE_PATH = os.fsdecode(b"undecodable-\xff.txt")

# What an agent can write into the shared repository to move a reading that
# was left to config: rename detection back on, object names shortened to a
# prefix, another algorithm, a threshold below the size of any real file, a
# driver that declares a path binary, submodules dropped, and a diff narrowed
# to one directory.
_PLANTED_CONFIG = (
    ("diff.renames", "copies"),
    ("core.abbrev", "4"),
    ("diff.algorithm", "histogram"),
    ("core.bigFileThreshold", "1"),
    ("diff.sneaky.binary", "true"),
    ("diff.ignoreSubmodules", "all"),
    ("diff.relative", "true"),
)

# What an agent can leave beside its work to change how content is rendered.
# The count has to pin this one and refuse over its neighbours; a listing that
# renders nothing is not asking.
_ATTRIBUTES_PATH = ".gitattributes"
_HIDE_EVERYTHING = "* -diff\n"

# Content big enough that its compressed form outruns the read that answers
# for an object's type. Corrupt the tail of a payload this size and git still
# unpacks the header off the front, reports `blob`, and only fails once
# something reads the object through -- which is the whole reason the objects
# are streamed rather than merely typed.
_BYTE_VALUES = 256
_PAYLOAD_REPEATS = 16
_PAST_THE_HEADER_PAYLOAD = bytes(range(_BYTE_VALUES)) * _PAYLOAD_REPEATS

# The four ways an object named by a listing stops being content this store
# can hand back: the file under `.git/objects` goes, what is left there is not
# an object at all, the stream stops inflating past a header that still does,
# or what answers is another kind of object entirely. None of them shows up in
# the listing itself. Each case commits its own payload into a world of its
# own, since what it then does to the store is damage the next commit into
# that repository would trip over.
_REMOVED = "removed"
_REPLACED = "replaced by bytes git cannot unpack"
_CORRUPTED_TAIL = "corrupted past a header that still inflates"
_ANOTHER_KIND = "answered as an object that is not a blob"

_LOST_CONTENT = (
    (_REMOVED, _BINARY_PAYLOAD),
    (_REPLACED, _BINARY_VARIANT),
    (_CORRUPTED_TAIL, _PAST_THE_HEADER_PAYLOAD),
    (_ANOTHER_KIND, _TWO_LINES.encode()),
)

# A whole valid object of the wrong type: git reads the kind off the header it
# finds rather than off what was asked for, so this answers `tree` under a
# name a listing gave as a blob.
_EMPTY_TREE_OBJECT = b"tree 0\0"

# What a replaced object is filled with, and the byte flipped in a corrupted
# one -- the last, so everything git reads before it is intact.
_NOT_AN_OBJECT = b"not an object at all"
_FLIPPED = 0xff

# The fourth thing that can sit where an object was, and the only one git
# never complains about: a different payload, correctly framed and compressed,
# filed under the name the real one hashed to. Git serves it as the object it
# was asked for -- `fsck` is the one thing that notices -- so a digest that
# named content by id and never read it would call two different
# contributions the same.
_SUBSTITUTED = "substituted for another valid object"
_SUBSTITUTE_CONTENT = b"a completely different payload\n"

# Listings no set of objects can be read out of: a stream that stops before a
# record's path arrives, a record that is not one, one whose metadata is a
# field short, and one whose last path lost its terminator -- which is a path
# cut off mid-name, and would otherwise pass for a whole record because the
# fields still pair up. None may be hashed: the shape is unaccounted for, so
# what is inside it went unchecked.
_UNREADABLE_LISTINGS = (
    b":100644 100644 aaaa bbbb M\0",
    b"100644 100644 aaaa bbbb M\0src/app.py\0",
    b":100644 aaaa bbbb M\0src/app.py\0",
    b":100644 100644 aaaa bbbb M\0src/app.p",
)

# One line of git's own output, the way a failed listing hands it up.
_LISTING_DETAIL = "fatal: bad object 0000000000000000000000000000000000000000"

# The real hardened read, bound before anything patches that name, so a test
# that installs its own can still take the listing git really answers with.
_REAL_HARDENED_BYTES = commands._git_hardened_bytes


def _completed(returncode: int, stdout: bytes) -> subprocess.CompletedProcess:
    """A git result carrying the given exit status and undecoded stdout."""
    return subprocess.CompletedProcess(
        args=[],
        returncode=returncode,
        stdout=stdout,
        stderr=_LISTING_DETAIL.encode(),
    )


class _FingerprintWorld(unittest.TestCase):
    """A candidate checkout, and the digest of one pair taken over it."""

    def setUp(self) -> None:
        self._repo = _support.CandidateRepo()
        self._repo.prepare(self)
        self._base = self._repo.base()

    def _fingerprint(self, candidate: str, base: str = ""):
        """The record one pair fingerprints to."""
        return fingerprint._fingerprint_contribution(
            self._repo.worktree, base or self._base, candidate,
        )

    def _digest(self, candidate: str, base: str = "") -> str:
        """The digest of one pair, failing the test if there is not one."""
        fingerprinted = self._fingerprint(candidate, base)

        self.assertTrue(
            fingerprinted.is_fingerprinted, fingerprinted.failure,
        )
        return fingerprinted.digest

    def _count(self, candidate: str) -> int:
        """What the added-line count makes of the same pair."""
        return additions._count_added_lines(
            self._repo.worktree, self._base, candidate,
        ).additions

    def _remove(self, path: str) -> str:
        """Delete a committed path in the checkout, and commit that alone."""
        _support.run_git(
            "rm", _support.QUIET_FLAG, path, cwd=self._repo.worktree,
        )
        return _support.commit_all(self._repo.worktree, "remove")

    def _opening_work(self) -> str:
        """Commit the candidate's own first change, and name that commit."""
        return self._repo.commit({_FEATURE_PATH: _TWO_LINES})

    def _make_executable(self, path: str) -> str:
        """Set the executable bit on a committed path, and commit that alone."""
        (self._repo.worktree / path).chmod(_EXECUTABLE_MODE)
        return _support.commit_all(self._repo.worktree, "chmod")


class ContributionCoverageTest(_FingerprintWorld):
    """The digest moves for every part of a contribution, and for nothing else."""

    def test_each_kind_of_change_moves_the_digest(self) -> None:
        # Every step commits exactly one kind of change on top of the last, so
        # a digest that repeats names the kind the representation does not
        # cover. The mode, the rename, and the deletion are made to paths the
        # base carries, which is what makes each of them the record it is
        # named after rather than another addition.
        seen = {"the opening commit": self._digest(self._opening_work())}

        for label, commit in self._single_changes().items():
            with self.subTest(change=label):
                digest = self._digest(commit())

                self.assertNotIn(digest, seen.values())
                seen[label] = digest

    def test_the_same_contribution_fingerprints_alike(self) -> None:
        # Two commits, two subjects, two ids, and one contribution: what a
        # branch arrived at is what a reviewer reads, and a digest that moved
        # with the route taken to it would call that work new on every pass.
        first = self._repo.commit({_FEATURE_PATH: _TWO_LINES}, "the work")
        self._repo.commit({_OTHER_PATH: _THREE_LINES}, "a detour")
        returned = self._remove(_OTHER_PATH)

        self.assertNotEqual(first, returned)
        self.assertEqual(self._digest(first), self._digest(returned))

    def test_the_base_decides_the_contribution(self) -> None:
        # One candidate tree, two bases, two contributions. Equal trees are no
        # answer: measured from the base a pull request would open against,
        # this candidate carries everything; measured from its own last
        # commit, it carries nothing anybody would review.
        opening = self._opening_work()
        candidate = self._repo.commit({_OTHER_PATH: _THREE_LINES})

        self.assertNotEqual(
            self._digest(candidate), self._digest(candidate, base=opening),
        )

    def test_an_empty_contribution_is_still_one(self) -> None:
        # The one contribution that is legitimately empty. It is an answer
        # rather than a failure, and it is its own answer: nothing else may
        # fingerprint to what an empty contribution does.
        empty = self._digest(self._base)
        candidate = self._opening_work()

        self.assertTrue(empty)
        self.assertNotEqual(empty, self._digest(candidate))

    def test_a_carriage_return_is_not_folded(self) -> None:
        # These two names differ by one byte, and by the byte a decoded
        # capture destroys: read as text, both listings name the same path and
        # two different contributions fingerprint alike.
        carriage_return = self._repo.commit({_CARRIAGE_RETURN_PATH: _TWO_LINES})
        newline = self._repo.move(_CARRIAGE_RETURN_PATH, _NEWLINE_PATH)

        self.assertNotEqual(
            self._digest(carriage_return), self._digest(newline),
        )

    def test_a_name_git_would_quote_is_taken_raw(self) -> None:
        # `-z` hands these over unquoted, so the listing carries a tab inside
        # one record and a byte that is not text at all inside another. Both
        # are legal names, and a reading that could not take them would refuse
        # a candidate over a file that changed like any other.
        for path in (_TABBED_PATH, _UNDECODABLE_PATH):
            with self.subTest(path=ascii(path)):
                self.assertTrue(self._digest(self._repo.commit({
                    path: _TWO_LINES,
                })))

    def _single_changes(self):
        """One commit per kind of change a contribution can be made of."""
        return {
            "modified text": lambda: self._repo.commit({
                _support.SEED_FILE: _THREE_LINES,
            }),
            "binary content": lambda: self._repo.commit({
                _BINARY_PATH: _BINARY_PAYLOAD,
            }),
            "one byte of it": lambda: self._repo.commit({
                _BINARY_PATH: _BINARY_VARIANT,
            }),
            "a mode": lambda: self._make_executable(_support.BASE_FILE),
            "a rename": lambda: self._repo.move(
                _support.BASE_FILE, _MOVED_PATH,
            ),
            "a deletion": lambda: self._remove(_support.SEED_FILE),
        }


class CountBlindChangeTest(_FingerprintWorld):
    """A change with no lines in it is still a change the digest sees."""

    def setUp(self) -> None:
        super().setUp()
        self._opening = self._opening_work()

    def test_a_mode_alone_moves_the_digest(self) -> None:
        # A base-carried file made executable and nothing else: same object on
        # both sides of the record, different modes. A count cannot see it,
        # and neither can a patch-id.
        chmodded = self._make_executable(_support.BASE_FILE)

        self._assert_only_the_digest_moved(chmodded)

    def test_a_deleted_base_file_moves_the_digest(self) -> None:
        # Removing a path the base carries is a deletion record with a
        # post-image of all zeros. Deleting a line is not adding one, so the
        # count is the same number it was before the file went.
        deleted = self._remove(_support.BASE_FILE)

        self._assert_only_the_digest_moved(deleted)

    def test_a_swapped_binary_moves_the_digest(self) -> None:
        # Neither payload has a line in it to add, so the count is the same
        # number for both -- which is what makes "the same size" no evidence
        # at all that two candidates carry the same work.
        self._repo.commit({_BINARY_PATH: _BINARY_PAYLOAD})
        swapped = self._repo.commit({_BINARY_PATH: _BINARY_VARIANT})

        self._assert_only_the_digest_moved(swapped)

    def _assert_only_the_digest_moved(self, candidate: str) -> None:
        """The count is what it was for the opening commit; the digest is not."""
        self.assertEqual(self._count(self._opening), _TWO_LINE_COUNT)
        self.assertEqual(self._count(candidate), _TWO_LINE_COUNT)
        self.assertNotEqual(
            self._digest(self._opening), self._digest(candidate),
        )


class PinnedListingTest(_FingerprintWorld):
    """What the checkout can say about the listing decides none of it."""

    def setUp(self) -> None:
        super().setUp()
        self._repo.commit({
            _FEATURE_PATH: _TWO_LINES, _BINARY_PATH: _BINARY_PAYLOAD,
        })
        # A move of a path the BASE carries, so rename detection has something
        # to collapse: without it, a planted `diff.renames` would change
        # nothing and every case below would pass for the wrong reason.
        self._candidate = self._repo.move(_support.BASE_FILE, _MOVED_PATH)
        self._pinned = self._digest(self._candidate)

    def test_planted_diff_config_decides_nothing(self) -> None:
        # The last of these is a file as much as a setting: `diff.orderFile`
        # promotes matching paths to the front of the listing, and a digest
        # over a permutation of the same records is a different digest for the
        # same work.
        order_file = self._repo.worktree / _ORDER_FILE
        order_file.write_text(f"{_MOVED_PATH}\n")
        for key, setting in (*_PLANTED_CONFIG, (_ORDER_KEY, str(order_file))):
            with self.subTest(planted=key):
                _support.run_git(
                    "config", key, setting, cwd=self._repo.worktree,
                )

                self.assertEqual(self._digest(self._candidate), self._pinned)

    def test_uncommitted_attributes_decide_nothing(self) -> None:
        # What decides how content is RENDERED cannot reach a listing that
        # renders none: `* -diff` beside the work makes every path in this
        # candidate report as binary to a patch, and says nothing about which
        # objects sit at which paths.
        (self._repo.worktree / _ATTRIBUTES_PATH).write_text(_HIDE_EVERYTHING)

        self.assertEqual(self._digest(self._candidate), self._pinned)

    def test_a_planted_shallow_file_decides_nothing(self) -> None:
        # `$GIT_DIR/shallow` is a file rather than a setting, so nothing on
        # the command line reaches it, and it lives in the git directory the
        # agent's worktree shares. A commit named there is walked as though it
        # had no parents, which is what moves the base a three-dot range
        # resolves to -- here it removes it, and the same two objects read as
        # no contribution at all.
        shallow = self._repo.clone / _SHALLOW_FILE
        shallow.write_text(f"{self._candidate}\n")

        self.assertEqual(self._digest(self._candidate), self._pinned)

    def test_a_promisor_remote_is_not_reached(self) -> None:
        # A clone made with a filter answers an id it does not hold by
        # fetching it, and every step of this reading asks after one: the ends
        # before anything else, then the content. Left to that, a reading
        # would turn into a network call -- answered by what the remote still
        # serves rather than by what this store holds -- and leave packs
        # behind in a repository the tick was only reading.
        clone, held, absent = self._blobless_checkout()

        for failure, pair in absent:
            with self.subTest(absent=failure):
                self.assertEqual(
                    fingerprint._fingerprint_contribution(
                        clone, *pair,
                    ).failure,
                    failure,
                )

        self.assertEqual(
            len(list((clone / _PACK_DIR).glob(_PACK_GLOB))), held,
        )

    def _blobless_checkout(self):
        """A partial clone, the packs it holds, and what it cannot answer for.

        Cloned over `file://` with `--no-local` so the filter is really
        negotiated rather than short-cut into a hardlink, and without a
        checkout so nothing pulls the blobs in on the way past. Two things are
        then out of its reach and in the remote's: the content of the
        contribution it does carry, and an end committed after it was made --
        which is what a candidate recorded on another host looks like. That
        second one is empty on purpose, so the range over it names no content
        and what the reading turns on is the end alone.
        """
        scratch = Path(self.enterContext(
            tempfile.TemporaryDirectory(prefix="orch-partial-"),
        ))
        origin, base, candidate = self._filtered_origin(scratch)
        clone = scratch / _CLONE_DIR
        _support.run_git(
            "clone", _QUIET, _BLOBLESS, _NO_CHECKOUT, _NO_LOCAL,
            f"file://{origin}", str(clone), cwd=scratch,
        )
        _support.run_git(
            "commit", _QUIET, _EMPTY_COMMIT, _support.MESSAGE_FLAG, "later",
            cwd=origin, env_extra=_support.AUTHOR_ENV,
        )
        return clone, len(list((clone / _PACK_DIR).glob(_PACK_GLOB))), (
            (FingerprintFailure.CONTENT_ABSENT, (base, candidate)),
            (
                FingerprintFailure.CANDIDATE_ABSENT,
                (candidate, _support.head_of(origin)),
            ),
        )

    def _filtered_origin(self, scratch: Path):
        """A repository that serves filtered clones, and the pair in it."""
        origin = scratch / _ORIGIN_DIR
        origin.mkdir()
        _support.run_git(
            "init", _QUIET, "-b", _support.BASE_BRANCH, ".", cwd=origin,
        )
        _support.run_git(
            "config", "uploadpack.allowFilter", "true", cwd=origin,
        )
        (origin / _support.SEED_FILE).write_text(_support.SEED_TEXT)
        base = _support.commit_all(origin, "initial")
        (origin / _BINARY_PATH).write_bytes(_PAST_THE_HEADER_PAYLOAD)
        return origin, base, _support.commit_all(origin, "work")


class StoredContentTest(_FingerprintWorld):
    """The digest is over the content this store really hands back."""

    def test_content_this_host_lost_is_never_hashed(self) -> None:
        # A raw listing is walked out of trees and never opens a blob, so a
        # store missing the content at a changed path lists exactly like one
        # holding all of it and git exits 0. A digest taken there would
        # compare equal to the one taken where the content really is.
        for how, payload in _LOST_CONTENT:
            with self.subTest(content=how):
                # A world of its own per case: what each does to the store is
                # damage git trips over on the next commit into it, so the
                # cases cannot be run one after another in one repository.
                self.setUp()
                candidate = self._repo.commit({_BINARY_PATH: payload})
                self._replant(candidate, _BINARY_PATH, how)

                fingerprinted = self._fingerprint(candidate)

                self.assertEqual(
                    fingerprinted.failure, FingerprintFailure.CONTENT_ABSENT,
                )
                self.assertEqual(fingerprinted.digest, "")
                self.assertFalse(fingerprinted.is_fingerprinted)

    def test_content_lost_after_the_listing_refuses(self) -> None:
        # The window a check standing in front of the read would leave: the
        # listing names an object, and by the time the content is asked for
        # the store no longer has it -- a `gc` in the checkout, an agent still
        # running beside the tick. Git answers that with the word `missing` on
        # the stdout the digest is taken over and exits 0, so a reading that
        # had already satisfied itself would hash the sentence and hand back
        # an id for it.
        self._vanishing = self._repo.commit({_BINARY_PATH: _BINARY_PAYLOAD})
        with patch.object(
            commands, _HARDENED_BYTES, side_effect=self._listing_then_loss,
        ):
            fingerprinted = self._fingerprint(self._vanishing)

        self.assertEqual(
            fingerprinted.failure, FingerprintFailure.CONTENT_ABSENT,
        )
        self.assertEqual(fingerprinted.digest, "")
        self.assertFalse(fingerprinted.is_fingerprinted)

    def test_substituted_content_moves_the_digest(self) -> None:
        # The one damage git never reports: a valid object of different
        # content, filed under the name the real one hashed to. `cat-file`
        # serves it without a word, so an id is only a claim about content
        # until something reads the content -- which is why the content is in
        # the digest rather than named by it.
        candidate = self._repo.commit({_BINARY_PATH: _BINARY_PAYLOAD})
        stored = self._digest(candidate)
        self._replant(candidate, _BINARY_PATH, _SUBSTITUTED)

        self.assertNotEqual(self._digest(candidate), stored)

    def test_a_base_side_object_is_required_too(self) -> None:
        # The pre-image is as much of the contribution as the post-image: it
        # is the content the change was made against, and the digest commits
        # to it by id.
        candidate = self._repo.commit({_support.SEED_FILE: _THREE_LINES})
        self._replant(self._base, _support.SEED_FILE, _REMOVED)

        self.assertEqual(
            self._fingerprint(candidate).failure,
            FingerprintFailure.CONTENT_ABSENT,
        )

    def test_a_gitlink_is_not_required_here(self) -> None:
        # A submodule's commit lives in the submodule's repository, not this
        # one, so requiring it would refuse a fingerprint to every candidate
        # that moves a gitlink -- which is every candidate that touches a
        # submodule at all.
        _support.run_git(
            "update-index", "--add", "--cacheinfo",
            f"160000,{_support.ABSENT_SHA},{_SUBMODULE_PATH}",
            cwd=self._repo.worktree,
        )
        _support.run_git(
            "commit", _support.QUIET_FLAG, _support.MESSAGE_FLAG, "gitlink",
            cwd=self._repo.worktree, env_extra=_support.AUTHOR_ENV,
        )

        self.assertTrue(self._digest(_support.head_of(self._repo.worktree)))

    def _listing_then_loss(self, *args: str, **taken):
        """The real listing read, with the blob it names lost once it returns.

        Installed on the call the owner takes its listing with, so the object
        goes exactly where a check standing in front of the read would have
        stopped looking: after the contribution is known, before its content
        is asked for.
        """
        listed = _REAL_HARDENED_BYTES(*args, **taken)
        self._replant(self._vanishing, _BINARY_PATH, _REMOVED)
        return listed

    def _replant(self, commit: str, path: str, how: str) -> None:
        """Put something else where one committed path's loose object sits.

        The corrupting case flips the last byte and leaves the rest, since a
        payload damaged anywhere earlier stops answering for its type as well
        -- and an object that already fails the cheap question proves nothing
        about the read that goes past it. The substituting case writes a whole
        valid object, which is the case nothing but `fsck` objects to.
        """
        named = _support.run_git(
            "rev-parse", f"{commit}:{path}", cwd=self._repo.worktree,
        ).strip()
        loose = (
            self._repo.clone / ".git" / "objects"
            / named[:_OBJECT_DIR_LENGTH] / named[_OBJECT_DIR_LENGTH:]
        )
        stored = bytearray(loose.read_bytes())
        stored[-1] ^= _FLIPPED
        loose.unlink()
        if how == _REPLACED:
            loose.write_bytes(_NOT_AN_OBJECT)
        elif how == _CORRUPTED_TAIL:
            loose.write_bytes(bytes(stored))
        elif how == _SUBSTITUTED:
            loose.write_bytes(zlib.compress(
                b"blob %d\0%s" % (len(_SUBSTITUTE_CONTENT), _SUBSTITUTE_CONTENT),
            ))
        elif how == _ANOTHER_KIND:
            loose.write_bytes(zlib.compress(_EMPTY_TREE_OBJECT))


class FingerprintFailureTest(_FingerprintWorld):
    """A reading that could not be taken hands back no id at all."""

    def test_an_absent_end_is_named_first(self) -> None:
        # A `git diff` naming an object that is not here fails the way it
        # fails for any other reason, and the two send an operator to
        # different places. Base first, since that is the end a caller would
        # have to supply before the other one could help.
        for (base, named), failure in self._absent_pairs():
            with self.subTest(failure=failure):
                fingerprinted = fingerprint._fingerprint_contribution(
                    self._repo.worktree, base, named,
                )

                self.assertEqual(fingerprinted.failure, failure)
                self.assertEqual(fingerprinted.digest, "")
                self.assertFalse(fingerprinted.is_fingerprinted)
                self.assertEqual(
                    (fingerprinted.base_sha, fingerprinted.candidate_sha),
                    (base, named),
                )

    def test_unrelated_histories_have_no_range(self) -> None:
        # Both objects are here and the range still cannot be resolved: there
        # is no commit the two branches share, so there is no prospective pull
        # request to fingerprint and git says so.
        unrelated = self._commit_unrelated_history()

        fingerprinted = self._fingerprint(unrelated)

        self.assertEqual(
            fingerprinted.failure, FingerprintFailure.DIFF_FAILED,
        )
        self.assertEqual(fingerprinted.digest, "")
        self.assertTrue(fingerprinted.detail)

    def test_a_failed_listing_is_never_hashed(self) -> None:
        # What a failed `git diff` writes to stdout is nothing, which is what
        # a candidate that changes nothing writes -- and anything it did write
        # is a partial listing. Hashing either would mint an id that reads
        # like a contribution.
        candidate = self._opening_work()
        with patch.object(
            commands, _HARDENED_BYTES,
            return_value=_completed(_GIT_FAILURE, b":100644 100644 "),
        ):
            fingerprinted = self._fingerprint(candidate)

        self.assertEqual(
            fingerprinted.failure, FingerprintFailure.DIFF_FAILED,
        )
        self.assertEqual(fingerprinted.digest, "")
        self.assertEqual(fingerprinted.detail, _LISTING_DETAIL)

    def test_the_canonical_range_is_asked_for(self) -> None:
        # Three-dot, so what is fingerprinted is the pull request rather than
        # everything that happened on the base since the fork. `--raw` and
        # `-z` are the representation: modes and object ids instead of
        # rendered content, and paths as the bytes they are. The rest is what
        # a repository would otherwise decide -- rename detection, the length
        # of an object name, submodules, the directory the listing is held to,
        # and the order the records come out in.
        candidate = self._opening_work()
        with patch.object(
            commands, _HARDENED_BYTES, return_value=_completed(0, b""),
        ) as git:
            self._fingerprint(candidate)

            self.assertEqual(
                git.call_args.args,
                (
                    "diff", "--raw", "-z", "--no-abbrev", "--no-renames",
                    "--ignore-submodules=none", "--no-relative",
                    f"-O{os.devnull}",
                    f"{self._base}...{candidate}",
                ),
            )
            self.assertEqual(
                git.call_args.kwargs["cwd"], self._repo.worktree,
            )

    def test_a_listing_this_build_cannot_read_refuses(self) -> None:
        # A stream whose shape is unaccounted for is not something to hash:
        # the digest would stand for a representation nobody can parse, and
        # the objects inside it would never have been checked.
        candidate = self._opening_work()
        for listing in _UNREADABLE_LISTINGS:
            with self.subTest(listing=listing):
                with patch.object(
                    commands, _HARDENED_BYTES,
                    return_value=_completed(0, listing),
                ):
                    fingerprinted = self._fingerprint(candidate)

                self.assertEqual(
                    fingerprinted.failure,
                    FingerprintFailure.DIFF_UNREADABLE,
                )
                self.assertEqual(fingerprinted.digest, "")

    def _absent_pairs(self):
        """Each pair with an end this host does not hold, and what it stops at."""
        absent = _support.ABSENT_SHA
        candidate = self._opening_work()
        return (
            ((absent, candidate), FingerprintFailure.BASE_ABSENT),
            ((self._base, absent), FingerprintFailure.CANDIDATE_ABSENT),
            ((absent, absent), FingerprintFailure.BASE_ABSENT),
        )

    def _commit_unrelated_history(self) -> str:
        """Commit onto a branch sharing no commit with the base, and name it.

        An orphan checkout keeps the files and drops the history, so what it
        commits is a root commit: a candidate this clone holds, over content
        the base also has, with no commit in common to diff from.
        """
        _support.run_git(
            "checkout", _support.QUIET_FLAG, "--orphan", "unrelated",
            cwd=self._repo.worktree,
        )
        return self._repo.commit({_FEATURE_PATH: _TWO_LINES}, "unrelated")


if __name__ == "__main__":
    unittest.main()
