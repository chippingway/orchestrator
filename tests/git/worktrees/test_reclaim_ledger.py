# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The notes a teardown leaves itself, and who is allowed to read them back.

The half of a teardown that no local artifact carries. A remote branch whose
issue has nothing left on this host is one the artifact scan will never report
again, and a commit a linked checkout's HEAD alone was holding is one nothing
names once that checkout comes down -- so what leads a later pass back to
either is the note written before the step that could lose it. These cases are
about the ledger those notes live in: that a note is read back where a restart
still finds it, that one repository reads only its own, that a note repointed
between the reading and the deletion is not taken, and that a ledger nobody
could read fully is told apart from one with nothing in it.

Real refs in a real clone throughout, because the ledger IS a ref store: a
double of it would prove only that the fixture remembered something. There is
no remote registered anywhere here, which is itself the point -- this owner
writes notes, reads them back, and takes them away, and reaches no remote to
do any of it.
"""

from __future__ import annotations

import os
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from orchestrator.git import commands
from orchestrator.git.worktrees import inventory, obligations
from orchestrator.git.worktrees.models import ProvenTip
from tests.git.worktrees.artifact_test_support import (
    BASE_BRANCH,
    COLLIDING_SLUGS,
    GADGET_SLUG,
    STRANGER_SLUG,
    WIDGET_SLUG,
    _legacy_branch,
    _namespaced_branch,
    _spec,
)
from tests.git.worktrees.candidate_host_test_support import (
    CLONE_NAME,
    QUIET,
    _branch_at,
    _CandidateWorld,
    _revision,
)
from tests.workflow.stages.question.question_real_git_test_support import (
    _run_git,
)

ISSUE_NUMBER = 314
# A second issue on the same clone, for the cases about one repository's
# anchors sitting beside each other under one namespace.
OTHER_ISSUE_NUMBER = 315

# The seam a leased deletion asks a second time when git refuses it, for the
# cases about that reading establishing nothing.
_NOTE_READ_SEAM = "_note_at"

# The seam the completeness check locates the ref store through, for the case
# about that check not having run at all.
_REF_STORE_SEAM = "_shared_ref_store"

# A well-formed object id this clone has never had. `update-ref` refuses to
# write a ref at an object it cannot find, which is the ledger declining one
# note without declining every note.
UNKNOWN_COMMIT = "1111111111111111111111111111111111111111"

# The name the unreadable note is planted under, in a spelling both
# namespaces accept.
BROKEN_NOTE_NAME = "issue-999"

BROKEN_REF_CONTENT = "not-a-sha\n"

# What git holds a ref under while it is writing one. A name carrying it sits
# in the namespace beside the notes and is not one of them.
REF_LOCK = ".lock"

# A branch this clone has never held, for the notes aimed at nothing. git
# resolves such a name to the same nothing an empty name resolves to, which is
# the whole reason the undereferenced read exists.
ABSENT_BRANCH = "refs/heads/never-here"

# A path nothing was ever created at, for the notes replaced by a link that
# leads nowhere. Every ref read git has follows the link and comes back with
# the same nothing a name never written to comes back with.
ABSENT_TARGET = Path("/nonexistent/orchestrator-ledger-target")

# What a namespace nothing may look into is left in. Root is not held back by
# it, so a host running these as root would be watching a different store than
# the one the check answers for.
UNREADABLE = 0

READABLE = 0o755

# The namespace a linked room is aimed at: the one place a note landing there
# would be read back by something else as an artifact of its own.
HEADS_ROOM = "refs/heads"

# Where a clone keeps the ref store its notes are files in.
GIT_DIR = ".git"

# What git calls the object every note this owner writes stands at, beside the
# reminder mark -- and, spelled the same, what makes one.
COMMIT = "commit"

# A repository of somebody else's, for the checkouts that are not this issue's.
STRANGER_CLONE = "stranger"

# A file committed into the clone, so a tree that is not the reminder mark
# exists to write a note at.
TRACKED_FILE = "tracked.txt"

# The origin a partial clone keeps as its promisor remote, and the filter that
# leaves objects behind on it.
PROMISOR_ORIGIN = "promisor-origin"

PROMISOR_CLONE = "partial"

BLOB_FILTER = "--filter=blob:none"

ALLOW_FILTER = "uploadpack.allowFilter"

# The seam a pass takes before it deletes, for the case about what may land
# between that reading and the deletion behind it.
_DIRECT_SEAM = "_direct_note"

# How long a racing write is given to land before it is called blocked, and
# how long it is waited on once the pass it raced has let go. The first is the
# one that has to stay short: every run spends it.
RACE_INTERVAL = 0.2

RACE_JOIN = 5.0

# What a checkout's own commit is asked for by, spelled once because the note
# under test is written at exactly this name from inside that checkout.
CHECKOUT_HEAD = "HEAD"


def _break_note(
    root: Path, ref: str, carrying: str = BROKEN_REF_CONTENT,
) -> Path:
    """Leave a note git would not have written under one of the namespaces.

    Written straight into the ref store rather than made with git, because git
    is what has to meet it, and because some of what a ref file can be left
    carrying is what git itself refuses to write: content that is not an
    object id at all, and a well-formed id this repository has no object for.
    """
    planted = root / GIT_DIR / ref
    planted.parent.mkdir(parents=True, exist_ok=True)
    planted.write_text(carrying)
    return planted


def _plant_note(root: Path, ref: str, revision: str) -> None:
    """Put one readable note at `ref`, without going through the owner."""
    _run_git("update-ref", "--no-deref", ref, revision, cwd=root)


def _link_note(root: Path, ref: str, target: Path) -> Path:
    """Put a filesystem link where one note belongs, and name it.

    The second way a name can lead somewhere else, and the one no ref read
    reports on: git opens a note by path, so what it reads is whatever the
    link leads to -- and a link leading nowhere reads to every one of those
    commands as a name nothing is at.
    """
    linked = root / GIT_DIR / ref
    linked.parent.mkdir(parents=True, exist_ok=True)
    linked.symlink_to(target)
    return linked


def _has_object(root: Path, sha: str) -> bool:
    """Whether this clone already holds one object, asked without fetching.

    The probe a promisor case turns on, so it may not be the thing under test:
    a plain `cat-file -e` in a partial clone goes and gets what it is asked
    about, which is exactly what these cases are checking nothing did.
    """
    asked = commands._git_hardened(
        "cat-file", "-e", "--end-of-options", sha,
        cwd=root, env_extra=obligations._NO_LAZY_FETCH,
    )
    return asked.returncode == 0


def _malformed(root: Path) -> tuple[str, ...]:
    """Values a note may be found at that no note is ever written at.

    A well-formed object id this repository has nothing under, a blob, and a
    tree that is not the reminder mark. All three are what a ref file can be
    left carrying, and git writes and resolves a ref at any of them.
    """
    (root / TRACKED_FILE).write_text(TRACKED_FILE)
    _run_git("add", TRACKED_FILE, cwd=root)
    written = _run_git("write-tree", cwd=root)
    hashed = _run_git("hash-object", "-w", TRACKED_FILE, cwd=root)
    return (
        UNKNOWN_COMMIT,
        (hashed.stdout or "").strip(),
        (written.stdout or "").strip(),
    )


def _link_room(root: Path, prefix: str, target: str) -> Path:
    """Put a filesystem link where one repository's room of notes belongs.

    Git walks the path it opens a ref by a room at a time and follows every
    one of them, so a room replaced this way files each note under `target`
    instead -- and reads each thing already there back as a note.
    """
    room = root / GIT_DIR / prefix.rstrip("/")
    room.parent.mkdir(parents=True, exist_ok=True)
    (root / GIT_DIR / target).mkdir(parents=True, exist_ok=True)
    room.symlink_to(root / GIT_DIR / target)
    return room


def _branches(root: Path) -> tuple[str, ...]:
    """Every branch this clone holds, read straight from git."""
    listed = _run_git(
        "for-each-ref", "--format=%(refname)", f"{HEADS_ROOM}/", cwd=root,
    )
    return tuple((listed.stdout or "").split())


class _RacingNote:
    """A ledger write let loose while a pass is between its two steps.

    Installed in place of the reading a pass takes before it writes or deletes
    something, so the write it starts aims at exactly the window that reading
    exists to close: a note that arrives there is one the step behind it was
    never told about, and the lease cannot see the difference.

    What it reports is whether that write could land there at all. Held under
    one lock it cannot, so the pass finishes on the note it read and this
    lands after it.
    """

    def __init__(self, spec, branch: str, sha: str, reading) -> None:
        self.spec = spec
        self.branch = branch
        self.sha = sha
        self.blocked = False
        self.racer = None
        self._reading = reading
        self._running = threading.Event()
        self._landed = threading.Event()

    def __call__(self, *args, **options):
        """Take the reading, then let one write at the window behind it."""
        answer = self._reading(*args, **options)
        if self.racer is None:
            self.racer = threading.Thread(target=self._write, daemon=True)
            self.racer.start()
            self._running.wait(RACE_JOIN)
            self.blocked = not self._landed.wait(RACE_INTERVAL)
        return answer

    def settled(self) -> None:
        """Wait for the racing write, once the pass it raced has let go."""
        self.racer.join(RACE_JOIN)

    def _write(self) -> None:
        self._running.set()
        obligations._record_obligation(self.spec, self.branch, self.sha)
        self._landed.set()


def _is_symbolic(root: Path, ref: str) -> bool:
    """Whether `ref` still holds a symbolic ref, asked without following it."""
    asked = commands._git_hardened(
        "symbolic-ref", "--quiet", "--end-of-options", ref, cwd=root,
    )
    return asked.returncode == 0


def _aim_note(root: Path, ref: str, target: str) -> None:
    """Turn one note into a symbolic ref onto `target`.

    What an agent sharing this ref store can do to a note. `target` is allowed
    not to exist, which is the case worth building: git's own resolution
    follows the name and comes back with nothing, exactly as it does for a
    name nobody ever wrote.
    """
    _run_git("symbolic-ref", ref, target, cwd=root)


class _LedgerTestCase(unittest.TestCase):
    """One clone, the repository whose notes it keeps, and its checkouts."""

    def setUp(self) -> None:
        self.world = _CandidateWorld()
        self.world.prepare(self)
        self.clone = self.world.clone(CLONE_NAME)
        self.spec = _spec(WIDGET_SLUG, self.clone)
        self.branch = _namespaced_branch(WIDGET_SLUG, ISSUE_NUMBER)
        # The two names this issue's notes are filed under. The cases plant,
        # aim, and break them at least as often as they read them, so they are
        # derived here rather than asked for at each site.
        self.record_ref = obligations._obligation_ref(self.spec, self.branch)
        self.anchor_ref = obligations._anchor_ref(
            self.spec, ISSUE_NUMBER,
        )

    def commit(self, branch: str | None = None) -> str:
        """One commit on a branch of this issue's own, and its object id."""
        return self.world.commit_on(self.clone, branch or self.branch)

    def record(self, sha: str, branch: str | None = None) -> bool:
        """Write down that this repository owes `branch` at `sha`."""
        return obligations._record_obligation(
            self.spec, branch or self.branch, sha,
        )

    def owed(self) -> tuple[ProvenTip, ...] | None:
        """What this repository still carries a remote-deletion record of."""
        return obligations._recorded_obligations(self.spec)

    def anchored(self) -> tuple[ProvenTip, ...] | None:
        """What this repository is still holding an anchor over."""
        return obligations._recorded_anchors(self.spec)

    def pinned(self, issue_number: int = ISSUE_NUMBER) -> str:
        """The commit this issue's anchor is holding, as a caller reads it."""
        return obligations._anchored_commit(self.spec, issue_number)

    def checkout(self, issue_number: int = ISSUE_NUMBER) -> Path:
        """This issue's worktree, on the branch its creator leaves it on."""
        branch = _namespaced_branch(WIDGET_SLUG, issue_number)
        self.world.commit_on(self.clone, branch)
        return self.world.attached_checkout(self.spec, issue_number, branch)


class RecordedObligationTest(_LedgerTestCase):
    """What one record says, and how it is written, replaced, and let go."""

    def test_a_record_reads_back_at_its_own_commit(self) -> None:
        tip = self.commit()

        self.assertTrue(self.record(tip))

        self.assertEqual(self.owed(), (ProvenTip(self.branch, tip),))

    def test_a_rewritten_record_carries_the_later_tip(self) -> None:
        # The last pass to write a record is the one that knows what this host
        # owes, so a record is written without a lease and the second write
        # replaces the first rather than sitting beside it: two notes about
        # one branch would have the pass that reads them delete twice.
        self.record(self.commit())
        moved = self.commit(f"{self.branch}-again")

        self.record(moved)

        self.assertEqual(self.owed(), (ProvenTip(self.branch, moved),))

    def test_a_record_is_let_go_under_its_own_value(self) -> None:
        tip = self.commit()
        self.record(tip)

        self.assertTrue(
            obligations._discharge_obligation(self.spec, self.branch, tip),
        )

        self.assertEqual(self.owed(), ())

    def test_a_reminder_stands_where_none_was_cleared(self) -> None:
        # The branch was on neither host when the classification ran, so there
        # is no commit to name -- and the record still has to be written,
        # since nothing local is left to lead a later pass back to it. The
        # value is an object every repository has and no branch is ever at,
        # which is how a reader tells the two kinds of record apart.
        cleared = self.commit(f"{self.branch}-cleared")
        self.record(cleared)
        reminded = _legacy_branch(ISSUE_NUMBER)

        self.assertTrue(obligations._remind(self.spec, reminded))

        self.assertEqual(
            set(self.owed()),
            {
                ProvenTip(self.branch, cleared),
                ProvenTip(reminded, obligations._REMINDER_MARK),
            },
        )

    def test_a_commit_with_no_object_is_refused(self) -> None:
        # A record that could not be written is one whose deletion has to be
        # refused rather than run uncovered, so the answer is whether the note
        # IS there and not whether the attempt was made.
        self.assertFalse(self.record(UNKNOWN_COMMIT))

        self.assertEqual(self.owed(), ())

    def test_a_write_that_never_ran_is_refused(self) -> None:
        # A host that would not run git at all is answered as a note that is
        # not there, because that is what the caller has to act on: an
        # uncovered deletion is the one thing a failed write may not permit.
        with patch.object(
            commands, "_git_hardened", side_effect=OSError("no git here"),
        ):
            self.assertFalse(self.record(self.commit()))

    def test_a_record_made_symbolic_moves_nothing(self) -> None:
        # The ledger lives in the store the per-issue checkouts share, so a
        # record can be pointed at somebody's branch -- and an update-ref that
        # followed it would write this host's note to itself onto that branch,
        # or take it away. Neither half follows one, and the delete refuses
        # outright: what it says it expects is the value this host wrote, and
        # a note standing at somebody else's commit is not it.
        stood_at = _revision(self.clone, BASE_BRANCH)
        elsewhere = self.commit()
        record = self.record_ref
        base = f"refs/heads/{BASE_BRANCH}"
        _aim_note(self.clone, record, base)

        self.record(elsewhere)

        self.assertEqual(_revision(self.clone, BASE_BRANCH), stood_at)
        self.assertEqual(self.owed(), (ProvenTip(self.branch, elsewhere),))

        _aim_note(self.clone, record, base)

        self.assertFalse(
            obligations._discharge_obligation(
                self.spec, self.branch, elsewhere,
            ),
        )
        self.assertEqual(_revision(self.clone, BASE_BRANCH), stood_at)
        self.assertTrue(_is_symbolic(self.clone, record))


class AnchoredCheckoutTest(_LedgerTestCase):
    """What a removal pins before it runs, and when it may let go."""

    def test_an_anchor_pins_its_own_checkouts_head(self) -> None:
        # Written from inside the checkout, so the HEAD git resolves is that
        # checkout's own rather than the clone's -- and resolved and recorded
        # by one command, so nothing lands between the reading and the note.
        worktree = self.checkout()
        standing = _revision(worktree, CHECKOUT_HEAD)

        self.assertTrue(
            obligations._anchor_checkout(self.spec, worktree, ISSUE_NUMBER),
        )

        self.assertNotEqual(standing, _revision(self.clone, CHECKOUT_HEAD))
        self.assertEqual(self.pinned(), standing)

    def test_an_anchor_outlives_its_own_checkout(self) -> None:
        # The whole reason the note is a ref in the clone rather than anything
        # the worktree keeps: a `worktree remove` takes that tree's HEAD and
        # reflog with it, and once the branch beside it is gone the scan
        # reports nothing at all -- so the ledger is the only place the commit
        # is still named.
        worktree = self.checkout()
        standing = _revision(worktree, CHECKOUT_HEAD)
        obligations._anchor_checkout(self.spec, worktree, ISSUE_NUMBER)

        _run_git("worktree", "remove", str(worktree), cwd=self.clone)
        _branch_at(self.clone, self.branch)

        self.assertEqual(
            inventory._local_issue_inventory((self.spec,)).issues, (),
        )
        self.assertEqual(
            self.anchored(),
            (ProvenTip(f"issue-{ISSUE_NUMBER}", standing),),
        )
    def test_an_issue_with_no_anchor_reads_as_none(self) -> None:
        # A removal that has not started yet and a read nobody could take
        # arrive at this caller as one answer, because it spends them the same
        # way: neither establishes that what came down was what was cleared.
        self.assertEqual(self.pinned(), "")

        with patch.object(obligations, _NOTE_READ_SEAM, return_value=None):
            self.assertEqual(self.pinned(), "")

    def test_each_issue_has_an_anchor_name_of_its_own(self) -> None:
        # The anchors of one repository share a namespace, so what tells them
        # apart is the issue segment -- the same spelling a reader of that
        # namespace parses the number back out of.
        for issue_number in (ISSUE_NUMBER, OTHER_ISSUE_NUMBER):
            obligations._anchor_checkout(
                self.spec, self.checkout(issue_number), issue_number,
            )

        self.assertEqual(
            sorted(anchor.subject for anchor in self.anchored()),
            [f"issue-{ISSUE_NUMBER}", f"issue-{OTHER_ISSUE_NUMBER}"],
        )


class AnchorRefusalTest(_LedgerTestCase):
    """What stands at an anchor's name and refuses the write over it."""

    def test_an_anchor_already_there_is_kept(self) -> None:
        # One already at this name is holding a commit an earlier pass could
        # not account for, so a write that replaced it would take the only
        # reference that commit has -- and the pass after would discharge what
        # it found. The lease says the ref must not exist, so this fails and
        # the caller leaves the checkout where it is.
        worktree = self.checkout()
        obligations._anchor_checkout(self.spec, worktree, ISSUE_NUMBER)
        pinned = self.pinned()
        _run_git("commit", QUIET, "--allow-empty", "-m", "later", cwd=worktree)

        self.assertFalse(
            obligations._anchor_checkout(self.spec, worktree, ISSUE_NUMBER),
        )

        self.assertNotEqual(_revision(worktree, CHECKOUT_HEAD), pinned)
        self.assertEqual(self.pinned(), pinned)

    def test_an_anchor_aimed_anywhere_blocks_it(self) -> None:
        # The lease compares against what the name RESOLVES to, and a symbolic
        # ref onto a ref that does not exist resolves to nothing -- which is
        # what the lease accepts. So the name is asked about undereferenced
        # first: whatever is standing there is a note nobody could read, and
        # replacing it is the one loss this whole note exists to prevent.
        worktree = self.checkout()
        anchor = self.anchor_ref

        for target in (ABSENT_BRANCH, f"refs/heads/{BASE_BRANCH}"):
            with self.subTest(target=target):
                _aim_note(self.clone, anchor, target)

                self.assertFalse(
                    obligations._anchor_checkout(
                        self.spec, worktree, ISSUE_NUMBER,
                    ),
                )
                self.assertTrue(_is_symbolic(self.clone, anchor))

    def test_an_anchor_that_is_a_link_blocks_it(self) -> None:
        # The same name read as absence gets the lease through as well, and
        # what the write lands on is the note that was standing there.
        worktree = self.checkout()
        linked = _link_note(self.clone, self.anchor_ref, ABSENT_TARGET)

        self.assertFalse(
            obligations._anchor_checkout(self.spec, worktree, ISSUE_NUMBER),
        )

        self.assertTrue(linked.is_symlink())

    def test_an_unreadable_anchor_blocks_it(self) -> None:
        # The third shape the name can be in that is not absence: a ref git
        # will not read at all. Nothing establishes that this issue has no
        # anchor yet, so the checkout stays and what is there stays with it.
        worktree = self.checkout()
        planted = _break_note(
            self.clone, self.anchor_ref,
        )

        self.assertFalse(
            obligations._anchor_checkout(self.spec, worktree, ISSUE_NUMBER),
        )

        self.assertEqual(planted.read_text(), BROKEN_REF_CONTENT)


class LeasedNoteTest(_LedgerTestCase):
    """What a deletion may take when something wrote in the window before it."""

    def test_a_record_rewritten_since_is_not_taken(self) -> None:
        # The ledger is a store the per-issue checkouts share, so a record can
        # be written again between the pass that read it and the deletion that
        # would take it away -- by a pass owed a commit of its own, or by a
        # reminder saying the branch has to be asked about again. The delete
        # states what it read, so the note that arrived after it stays; stated
        # correctly, the same delete takes it.
        tip = self.commit()
        self.record(tip)
        rewritten = self.commit(f"{self.branch}-again")
        self.record(rewritten)

        self.assertFalse(
            obligations._discharge_obligation(self.spec, self.branch, tip),
        )
        self.assertEqual(self.owed(), (ProvenTip(self.branch, rewritten),))

        self.assertTrue(
            obligations._discharge_obligation(
                self.spec, self.branch, rewritten,
            ),
        )
        self.assertEqual(self.owed(), ())

    def test_an_anchor_repointed_since_is_not_let_go(self) -> None:
        # The sharper half of the same rule: an anchor moved between the
        # reading that cleared it and this is holding a commit nothing else
        # names, and a delete that took whatever it found would drop it.
        worktree = self.checkout()
        obligations._anchor_checkout(self.spec, worktree, ISSUE_NUMBER)
        cleared = self.pinned()
        moved = self.commit(f"{self.branch}-moved")
        _plant_note(
            self.clone, self.anchor_ref, moved,
        )

        self.assertFalse(
            obligations._discard_anchor(self.spec, ISSUE_NUMBER, cleared),
        )
        self.assertEqual(self.pinned(), moved)

        self.assertTrue(
            obligations._discard_anchor(self.spec, ISSUE_NUMBER, moved),
        )
        self.assertEqual(self.anchored(), ())

    def test_a_note_that_has_already_gone_is_success(self) -> None:
        # A leased delete is refused for a note that moved and for one that is
        # no longer there alike, and the second of those is this deletion
        # having happened. So a refusal is asked about once more, and a name
        # nothing resolves is the success it looks like from every other angle.
        tip = self.commit()
        self.record(tip)
        obligations._discharge_obligation(self.spec, self.branch, tip)

        self.assertTrue(
            obligations._discharge_obligation(self.spec, self.branch, tip),
        )
        self.assertTrue(
            obligations._discard_anchor(self.spec, ISSUE_NUMBER, tip),
        )
    def test_a_note_nobody_could_reread_is_kept(self) -> None:
        # That second reading can fail as readily as the first, and spent as
        # an absence it would report a note still standing as one this host
        # took away -- for an anchor, a commit nothing else names reported as
        # a surface that came back clean.
        tip = self.commit()
        self.record(tip)
        rewritten = self.commit(f"{self.branch}-again")
        self.record(rewritten)

        with patch.object(obligations, _NOTE_READ_SEAM, return_value=None):
            taken = obligations._discharge_obligation(
                self.spec, self.branch, tip,
            )

        self.assertFalse(taken)
        self.assertEqual(self.owed(), (ProvenTip(self.branch, rewritten),))


class UnreadNoteTest(_LedgerTestCase):
    """A name that is not a note this host wrote is never one it took away."""

    def test_a_note_aimed_at_nothing_is_not_taken(self) -> None:
        # The sharpest shape of the same window, because git's own resolution
        # cannot see it: a note somebody points at a ref that does not exist
        # resolves to exactly what an empty name resolves to. Read that way it
        # is a deletion this pass already ran, so the record would be reported
        # gone while it is still standing -- and for an anchor, a commit
        # nothing else names reported as a surface that came back clean.
        tip = self.commit()
        self.record(tip)
        record = self.record_ref
        anchor = self.anchor_ref
        _plant_note(self.clone, anchor, tip)
        for aimed in (record, anchor):
            _aim_note(self.clone, aimed, ABSENT_BRANCH)

        self.assertIsNone(obligations._note_at(self.spec, record))
        self.assertFalse(
            obligations._discharge_obligation(self.spec, self.branch, tip),
        )
        self.assertFalse(
            obligations._discard_anchor(self.spec, ISSUE_NUMBER, tip),
        )
        self.assertEqual(self.pinned(), "")

        for aimed in (record, anchor):
            with self.subTest(note=aimed):
                self.assertTrue(_is_symbolic(self.clone, aimed))

    def test_a_note_aimed_at_the_same_commit_is_kept(self) -> None:
        # The lease is not the whole of the check, because git compares the
        # stated value against what the name RESOLVES to even undereferenced:
        # a note aimed at anything standing at that same value passes. What
        # the delete would take is a ref this pass never read, and the note it
        # replaced would be reported as one this pass discharged -- so the
        # name is established undereferenced first, and the decoy the aim went
        # through is left exactly where it was.
        tip = self.commit()
        self.record(tip)
        record = self.record_ref
        decoy = f"refs/heads/{self.branch}"
        _aim_note(self.clone, record, decoy)

        self.assertFalse(
            obligations._discharge_obligation(self.spec, self.branch, tip),
        )

        self.assertTrue(_is_symbolic(self.clone, record))
        self.assertEqual(_revision(self.clone, decoy), tip)

    def test_a_note_that_is_a_link_is_not_an_absence(self) -> None:
        # Git follows a filesystem link the way it follows a symbolic ref, and
        # reports nothing for one leading nowhere -- but no ref read it has
        # says which of the two it was looking at. Read as absence, the note
        # still standing there is a deletion this pass reports as done.
        linked = _link_note(self.clone, self.record_ref, ABSENT_TARGET)

        self.assertIsNone(obligations._note_at(self.spec, self.record_ref))
        self.assertFalse(
            obligations._discharge_obligation(
                self.spec, self.branch, self.commit(),
            ),
        )

        self.assertTrue(linked.is_symlink())

    def test_an_unreadable_note_is_not_an_absence(self) -> None:

        # The other name a resolution answers "not there" for: a ref whose
        # content git cannot parse. Nothing was taken away there either.
        _break_note(self.clone, self.record_ref)

        self.assertIsNone(
            obligations._note_at(self.spec, self.record_ref),
        )
        self.assertFalse(
            obligations._discharge_obligation(
                self.spec, self.branch, self.commit(),
            ),
        )


class LinkedRoomTest(_LedgerTestCase):
    """What a namespace replaced by a link to somewhere else may do.

    The rooms above a note, rather than the note itself. `--no-deref` is about
    a ref's own value and says nothing about the path it is filed under, and
    git walks that path a room at a time -- so the room aimed at `refs/heads`
    is the one that turns a note this host keeps for itself into a branch the
    artifact scan reads back as a candidate.
    """

    def test_a_linked_room_takes_no_record(self) -> None:
        standing = _branches(self.clone)
        _link_room(
            self.clone, obligations._records_prefix(self.spec), HEADS_ROOM,
        )

        self.assertFalse(self.record(_revision(self.clone, BASE_BRANCH)))

        self.assertEqual(_branches(self.clone), standing)

    def test_a_linked_room_reads_no_record(self) -> None:
        # Every branch the clone holds is under that room now, so a listing
        # that walked into it would report somebody else's branches as notes
        # this host wrote -- and a name read through it answers for whatever
        # is standing at the far end.
        _link_room(
            self.clone, obligations._records_prefix(self.spec), HEADS_ROOM,
        )

        self.assertIsNone(self.owed())
        self.assertIsNone(obligations._note_at(self.spec, self.record_ref))
        self.assertFalse(
            obligations._discharge_obligation(
                self.spec, self.branch, _revision(self.clone, BASE_BRANCH),
            ),
        )

    def test_a_linked_room_takes_no_anchor(self) -> None:
        worktree = self.checkout()
        standing = _branches(self.clone)
        _link_room(
            self.clone, obligations._anchors_prefix(self.spec), HEADS_ROOM,
        )

        self.assertFalse(
            obligations._anchor_checkout(self.spec, worktree, ISSUE_NUMBER),
        )

        self.assertEqual(_branches(self.clone), standing)


class MalformedNoteTest(_LedgerTestCase):
    """What a note may be found standing at, and what it may never be.

    A ref file carries an object id and nothing else. Git writes and resolves
    one for an object this repository does not have, and `rev-parse --verify`
    answers for the name being well formed rather than for anything behind it
    -- so a note left at a stray id or at the wrong kind of object reads back
    exactly like a commit somebody adjudicated.
    """

    def test_a_note_at_no_commit_is_no_note(self) -> None:
        for stood in _malformed(self.clone):
            with self.subTest(value=stood):
                planted = _break_note(
                    self.clone, self.record_ref, f"{stood}\n",
                )

                self.assertIsNone(self.owed())
                self.assertIsNone(
                    obligations._note_at(self.spec, self.record_ref),
                )
                self.assertEqual(planted.read_text().strip(), stood)

    def test_an_anchor_at_no_commit_is_no_anchor(self) -> None:
        worktree = self.checkout()
        for stood in _malformed(self.clone):
            with self.subTest(value=stood):
                _break_note(self.clone, self.anchor_ref, f"{stood}\n")

                self.assertIsNone(self.anchored())
                self.assertEqual(self.pinned(), "")
                self.assertFalse(
                    obligations._anchor_checkout(
                        self.spec, worktree, ISSUE_NUMBER,
                    ),
                )

    def test_a_write_at_no_commit_is_refused(self) -> None:
        # git files a ref at any object it has, so nothing but the write's own
        # reading stops a record being kept at a value every reader after it
        # refuses -- and the caller that went on because its record was kept
        # went on over a ledger the pass after has to throw away whole.
        for stood in _malformed(self.clone):
            with self.subTest(value=stood):
                self.assertFalse(self.record(stood))
                self.assertEqual(self.owed(), ())

    def test_an_anchor_at_the_mark_is_no_anchor(self) -> None:
        # The one value a record may carry that is not a commit is the one
        # thing an anchor has nothing to say with. What an anchor is FOR is
        # the commit a checkout was standing on while it came down, so a
        # marker-valued one names no work at all -- and read back as a commit
        # to account for it would settle a removal against nothing.
        worktree = self.checkout()
        _plant_note(self.clone, self.anchor_ref, obligations._REMINDER_MARK)

        self.assertIsNone(self.anchored())
        self.assertEqual(self.pinned(), "")
        self.assertFalse(
            obligations._anchor_checkout(self.spec, worktree, ISSUE_NUMBER),
        )

    def test_the_reminder_mark_is_still_a_note(self) -> None:
        # The one value a note carries that is not a commit, so the rule that
        # refuses the rest may not refuse this one: a branch nothing cleared
        # is recorded at git's empty tree.
        reminded = _legacy_branch(ISSUE_NUMBER)

        self.assertTrue(obligations._remind(self.spec, reminded))

        self.assertEqual(
            self.owed(),
            (ProvenTip(reminded, obligations._REMINDER_MARK),),
        )
        self.assertTrue(
            obligations._discharge_obligation(
                self.spec, reminded, obligations._REMINDER_MARK,
            ),
        )


class PromisorCloneTest(_LedgerTestCase):
    """What a clone that can go and get an object may do about a note.

    A clone made with a filter keeps a promisor remote, and git answers an
    object it is missing by fetching it rather than by failing. Every reading
    here that touches an object would reach that remote on its own -- and a
    note left at something nothing on this host has would come back as one
    somebody adjudicated, which is the leftover that exists to be found never
    being found.
    """

    def partial(self) -> tuple[Path, str]:
        """A clone with a promisor remote, and a commit only that remote has."""
        origin = self.world.path(PROMISOR_ORIGIN)
        origin.mkdir()
        _run_git("init", QUIET, "-b", BASE_BRANCH, cwd=origin)
        _run_git("config", ALLOW_FILTER, "true", cwd=origin)
        (origin / TRACKED_FILE).write_text(TRACKED_FILE)
        _run_git("add", TRACKED_FILE, cwd=origin)
        _run_git(COMMIT, QUIET, "-m", "first", cwd=origin)
        clone = self.world.path(PROMISOR_CLONE)
        _run_git(
            "clone", QUIET, BLOB_FILTER, f"file://{origin}", str(clone),
            cwd=self.world.path(""),
        )
        _run_git(COMMIT, QUIET, "--allow-empty", "-m", "later", cwd=origin)
        return clone, _revision(origin, "HEAD")

    def test_a_note_no_object_backs_is_not_fetched(self) -> None:
        # The reading the ledger is finished by: a record standing at a commit
        # this host has never had comes back as one this host wrote, and the
        # remote is asked for it to find that out.
        clone, unfetched = self.partial()
        spec = _spec(WIDGET_SLUG, clone)
        _break_note(
            clone,
            obligations._obligation_ref(spec, self.branch),
            f"{unfetched}\n",
        )

        self.assertIsNone(obligations._recorded_obligations(spec))

        self.assertFalse(_has_object(clone, unfetched))

    def test_a_note_no_object_backs_is_not_written(self) -> None:
        # And the write in front of it: git files a ref at an object it can go
        # and get, so the record would be kept, the remote reached, and the
        # value nothing on this host proved written down as one it did.
        clone, unfetched = self.partial()
        spec = _spec(WIDGET_SLUG, clone)

        self.assertFalse(
            obligations._record_obligation(spec, self.branch, unfetched),
        )

        self.assertFalse(_has_object(clone, unfetched))
        self.assertEqual(obligations._recorded_obligations(spec), ())


class ForeignCheckoutTest(_LedgerTestCase):
    """Where an anchor lands when the checkout is not this repository's.

    The tree a write runs in decides which ref store it reaches, and an
    anchor's write runs inside the checkout because only from in there does
    `HEAD` mean that checkout's own. A checkout of somebody else's repository
    keeps a store of its own, so the note would be filed where nothing on this
    repository's side ever looks.
    """

    def test_an_anchor_is_refused_a_foreign_checkout(self) -> None:
        stranger = self.world.clone(STRANGER_CLONE)
        stranger_spec = _spec(STRANGER_SLUG, stranger)

        self.assertFalse(
            obligations._anchor_checkout(self.spec, stranger, ISSUE_NUMBER),
        )

        self.assertEqual(self.pinned(), "")
        self.assertEqual(self.anchored(), ())
        self.assertEqual(obligations._recorded_anchors(stranger_spec), ())


class RacingNoteTest(_LedgerTestCase):
    """What may land while a pass is between the reading and the step on it.

    Git has no write here that states what a name may BE as well as what it
    stands at, so what makes a reading and the step behind it one is that
    nothing else in this process runs between them. These cases let a write at
    exactly that window.
    """

    def test_no_write_lands_while_a_delete_runs(self) -> None:
        tip = self.commit()
        self.record(tip)
        rewritten = self.commit(f"{self.branch}-again")
        racing = _RacingNote(
            self.spec, self.branch, rewritten, obligations._direct_note,
        )

        with patch.object(obligations, _DIRECT_SEAM, racing):
            taken = obligations._discharge_obligation(
                self.spec, self.branch, tip,
            )
        racing.settled()

        self.assertTrue(racing.blocked)
        self.assertTrue(taken)
        self.assertEqual(self.owed(), (ProvenTip(self.branch, rewritten),))

    def test_no_write_lands_while_an_anchor_is_taken(self) -> None:
        worktree = self.checkout()
        owed = self.commit(f"{self.branch}-owed")
        racing = _RacingNote(
            self.spec, self.branch, owed, obligations._note_at,
        )

        with patch.object(obligations, _NOTE_READ_SEAM, racing):
            taken = obligations._anchor_checkout(
                self.spec, worktree, ISSUE_NUMBER,
            )
        racing.settled()

        self.assertTrue(racing.blocked)
        self.assertTrue(taken)
        self.assertNotEqual(self.pinned(), "")
        self.assertEqual(self.owed(), (ProvenTip(self.branch, owed),))


class LedgerOwnershipTest(_LedgerTestCase):
    """Which notes a repository may read, and which it never sees at all."""

    def test_a_clone_mate_reads_none_of_these_notes(self) -> None:
        # Two repositories on one clone derive the same legacy branch name,
        # which is why the attribution behind the scan refuses to charge that
        # name to either of them. Their notes are told apart by the repository
        # they were written under instead, so a deletion one of them runs goes
        # to the remote that actually carries the branch -- and the entry
        # beside it never sees the record at all.
        legacy = _legacy_branch(ISSUE_NUMBER)
        self.record(self.commit(legacy), branch=legacy)
        obligations._anchor_checkout(
            self.spec, self.checkout(), ISSUE_NUMBER,
        )
        clone_mate = _spec(GADGET_SLUG, self.clone)

        self.assertEqual(obligations._recorded_obligations(clone_mate), ())
        self.assertEqual(obligations._recorded_anchors(clone_mate), ())
        self.assertEqual(
            tuple(record.subject for record in self.owed()), (legacy,),
        )

    def test_two_colliding_slugs_get_two_rooms(self) -> None:
        # The two slugs the ref-safe sanitizer cannot tell apart, which is the
        # pair the attribution behind the scan refuses to attribute anything
        # to. Their branches are one name, so a ledger keyed the way the
        # branch namespace is would be one room -- and either entry would read
        # the other's note, classify it against its own GitHub, and delete on
        # its own remote. The digest of the untransformed slug keeps them
        # apart.
        one, other = (_spec(slug, self.clone) for slug in COLLIDING_SLUGS)
        obligations._record_obligation(one, self.branch, self.commit())

        namespaces = (obligations._records_prefix, obligations._anchors_prefix)
        for prefix in namespaces:
            with self.subTest(namespace=prefix.__name__):
                self.assertNotEqual(prefix(one), prefix(other))

        self.assertEqual(obligations._recorded_obligations(other), ())
        self.assertEqual(
            tuple(
                record.subject
                for record in obligations._recorded_obligations(one)
            ),
            (self.branch,),
        )

    def test_a_note_is_no_candidate_the_scan_reads(self) -> None:
        # Why the namespaces are siblings of `refs/heads/` rather than names
        # under it: a note filed there would be read back by the scan as an
        # artifact of its own, and the teardown would be handed its own
        # bookkeeping to take down.
        base = _revision(self.clone, BASE_BRANCH)
        self.record(base)
        _plant_note(
            self.clone, self.anchor_ref, base,
        )

        self.assertEqual(
            inventory._local_issue_inventory((self.spec,)).issues, (),
        )


class LedgerReadTest(_LedgerTestCase):
    """A ledger nobody could read fully, told apart from one with nothing in it."""

    def test_an_empty_ledger_is_not_an_unread_one(self) -> None:
        self.assertEqual(self.owed(), ())
        self.assertEqual(self.anchored(), ())

    def test_a_listing_short_by_a_note_is_refused(self) -> None:
        # git skips a ref it cannot parse and still exits zero, so the answer
        # comes back short by exactly the note something is wrong with -- and
        # short is the one thing a caller spending it on "everything this host
        # began has finished" cannot see.
        tip = self.commit()
        namespaces = (
            (obligations._records_prefix(self.spec), self.branch, self.owed),
            (
                obligations._anchors_prefix(self.spec),
                f"{obligations._ISSUE_SEGMENT}{ISSUE_NUMBER}",
                self.anchored,
            ),
        )

        for prefix, readable, read_back in namespaces:
            with self.subTest(prefix=prefix):
                _plant_note(self.clone, f"{prefix}{readable}", tip)
                _break_note(self.clone, f"{prefix}{BROKEN_NOTE_NAME}")

                self.assertIsNone(read_back())

    def test_a_note_aimed_elsewhere_is_refused(self) -> None:
        # A live symbolic note IS reported by the listing, standing at
        # whatever it was aimed at -- so without the symref field beside it
        # somebody else's commit would come back as a note this host wrote.
        tip = self.commit()
        self.record(tip)
        _aim_note(self.clone, self.record_ref, f"refs/heads/{BASE_BRANCH}")

        self.assertIsNone(self.owed())
    def test_a_listing_that_never_ran_is_refused(self) -> None:
        with patch.object(
            commands, "_git_hardened", side_effect=OSError("no git here"),
        ):
            self.assertIsNone(self.owed())
            self.assertIsNone(self.anchored())

    def test_one_unreadable_line_refuses_the_listing(self) -> None:
        # One unreadable line refuses the listing rather than the line, for
        # the reason a short listing does: a caller cannot tell a ledger
        # missing one entry from a complete one.
        prefix = obligations._records_prefix(self.spec)
        tip = self.commit()
        stands = f"{prefix}{self.branch} {tip} {COMMIT} "
        unreadable = (
            stands.rstrip(),
            f"{stands} ",
            f"{stands}refs/heads/{BASE_BRANCH}",
            f"{prefix}{self.branch} {tip} blob ",
            f"refs/heads/{self.branch} {tip} {COMMIT} ",
            f"{obligations.RECLAIM_NAMESPACE}/{self.branch} {tip} {COMMIT} ",
        )

        self.assertEqual(
            obligations._parsed_records(f"{stands}\n", prefix),
            (ProvenTip(self.branch, tip),),
        )

        for line in unreadable:
            with self.subTest(line=line):
                self.assertIsNone(
                    obligations._parsed_records(
                        f"{stands}\n{line}\n", prefix,
                    ),
                )


class LedgerCompletenessTest(_LedgerTestCase):
    """Whether the listing named every note the ref store is holding."""

    def test_a_note_aimed_at_nothing_is_unlisted(self) -> None:
        # git drops a note aimed at a ref that does not exist out of the
        # listing with no warning and a zero status -- in every mode it has --
        # so the answer comes back short by exactly that note and a caller
        # would read a leftover this host is the last name for as nothing
        # owed. What the store is holding is asked of the store instead.
        tip = self.commit()
        namespaces = (
            (self.record_ref, self.owed),
            (
                self.anchor_ref,
                self.anchored,
            ),
        )

        for note, read_back in namespaces:
            with self.subTest(note=note):
                _plant_note(self.clone, note, tip)
                self.assertNotEqual(read_back(), ())

                _aim_note(self.clone, note, ABSENT_BRANCH)

                self.assertIsNone(read_back())

    @unittest.skipIf(
        os.geteuid() == 0, "root reads a namespace nothing else may look into",
    )
    def test_a_room_nobody_may_look_into_is_refused(self) -> None:
        # A namespace this host cannot read holds notes the listing beside it
        # could not read either, and git reports that as no notes at all --
        # exit zero, stdout empty, stderr empty. So the walk has to be the one
        # that says so, and a glob would answer a room it was refused exactly
        # as it answers an empty one.
        self.record(self.commit())
        room = self.clone / GIT_DIR / obligations._records_prefix(self.spec)
        os.chmod(room, UNREADABLE)
        self.addCleanup(os.chmod, room, READABLE)

        self.assertIsNone(self.owed())

    def test_a_note_that_is_a_link_is_no_note(self) -> None:
        # The walk answers for what is standing under the namespace, so a name
        # leading somewhere else is not one it may pass over: a listing that
        # left it out is short by a name this store is holding.
        _link_note(self.clone, self.record_ref, ABSENT_TARGET)

        self.assertIsNone(self.owed())

    def test_a_packed_note_still_reads_back(self) -> None:
        # The completeness check runs one way only, because git moves a loose
        # ref into `packed-refs` whenever it tidies up: a note the listing
        # names and the namespace no longer holds a file for is an ordinary
        # packed note, not a listing that lost one.
        tip = self.commit()
        self.record(tip)
        _plant_note(
            self.clone, self.anchor_ref, tip,
        )

        _run_git("pack-refs", "--all", cwd=self.clone)

        self.assertEqual(self.owed(), (ProvenTip(self.branch, tip),))
        self.assertEqual(
            self.anchored(),
            (ProvenTip(f"{obligations._ISSUE_SEGMENT}{ISSUE_NUMBER}", tip),),
        )

    def test_a_write_in_flight_is_no_missing_note(self) -> None:
        # git holds a ref under a name of its own while it writes one, and
        # that name sits in the namespace beside the notes. It is a write
        # nobody has finished rather than a note the listing lost, so the
        # answer stands.
        tip = self.commit()
        self.record(tip)
        _break_note(self.clone, f"{self.record_ref}{REF_LOCK}")

        self.assertEqual(self.owed(), (ProvenTip(self.branch, tip),))

    def test_a_ref_store_nobody_located_is_refused(self) -> None:
        # The check that answers for a short listing has to have run: a store
        # this could not be read out of is the failure, since the listing it
        # would have been compared against is the one thing nothing else sees.
        with patch.object(obligations, _REF_STORE_SEAM, return_value=None):
            self.assertIsNone(self.owed())
            self.assertIsNone(self.anchored())


if __name__ == "__main__":
    unittest.main()
