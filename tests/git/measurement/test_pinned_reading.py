# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a count is pinned to: two frozen ids, and the candidate's own tree.

Both halves are checked by planting what an agent can really plant. The base
moves under the adjudication and the branch takes it in, so a reading that
consulted `<remote>/<base>` instead of the recorded id would report a different
number for a candidate whose commits never changed. And what decides "binary"
-- an uncommitted attributes file, a size threshold in the shared config, a
diff driver, an `info/attributes` -- is written where the work is done, since
whether an override on the command line reaches one of those is not a thing a
mock can answer.
"""
from __future__ import annotations

import os
import threading
import unittest
from unittest.mock import patch

from orchestrator.git.measurement import additions, commits
from orchestrator.git.measurement.models import MeasurementFailure
from tests.git.measurement import measurement_test_support as _support

_FEATURE_PATH = "feature.py"
_ATTRIBUTES_PATH = ".gitattributes"

# The two lines of work each case commits, so the count that must survive
# whatever was planted is the same one throughout.
_TWO_LINES = "one\ntwo\n"

# What the base gains while an adjudication is in flight, sized so the two
# readings of the same candidate cannot be confused for each other.
_THREE_LINES = "one\ntwo\nthree\n"

# What the candidate itself adds, and what a reading from the frozen base
# covers once the branch has taken the advanced base in.
_TWO_LINE_COUNT = 2
_WITH_THE_BASE_TAKEN_IN = 5

# What an agent can write beside its work to have every path in the candidate
# report as binary: attributes it never commits, a threshold below the size of
# any real file, and a driver the repository's own config declares binary.
_HIDE_EVERYTHING = "* -diff\n"
_BIG_FILE_THRESHOLD = ("config", "core.bigFileThreshold", "1")
_BINARY_DRIVER = ("config", "diff.sneaky.binary", "true")
_HISTOGRAM_ALGORITHM = ("config", "diff.algorithm", "histogram")

# One path's content before and after a change git's algorithms disagree
# about: the repeated lines can be paired up more than one way, and which
# pairing is chosen decides how many lines count as added. `myers` -- the
# default, and what this reading names -- makes it four; `histogram` makes it
# seven, for the same two commits.
_AMBIGUOUS_PATH = "ambiguous.txt"
_AMBIGUOUS_BEFORE = "d\nd\nb\nb\nd\nb\na\nd\nc\nb\na\na\nd\n"
_AMBIGUOUS_AFTER = "b\na\nd\nb\nb\nb\na\nd\na\nc\nb\na\nb\nd\n"
_MYERS_ADDITIONS = 4

# The attribute source git reads from the environment, which outranks every
# pin a command line can carry.
_ATTR_SOURCE_ENV = "GIT_ATTR_SOURCE"

# How long a reading that must not open what it inspects is given before the
# test calls it blocked. A FIFO nobody writes to holds an `open` forever, so
# the failure this bounds is a hung tick rather than a wrong number.
_UNBLOCKED_SECONDS = 20


class FrozenBaseTest(unittest.TestCase):
    """The id frozen for the attempt decides the count, not the live base."""

    def setUp(self) -> None:
        self._repo = _support.CandidateRepo()
        self._repo.prepare(self)

    def test_the_frozen_base_decides_the_count(self) -> None:
        # The base moves under a long adjudication, and a branch that takes the
        # new commits in makes the two readings differ: measured from the
        # frozen id, everything between it and the candidate counts; measured
        # from whatever `<remote>/<base>` names now, only the candidate's own
        # work does. The remote-tracking ref really advances here, so a reading
        # that consulted it instead of the record would report the smaller
        # number for a candidate whose commits never changed.
        frozen = commits._freeze_base_commit(
            self._repo.spec, self._repo.worktree,
        )
        advanced = self._repo.advance_base_from_elsewhere(_THREE_LINES)
        self._repo.take_in_advanced_base()
        candidate = self._repo.commit({_FEATURE_PATH: _TWO_LINES})

        self.assertNotEqual(frozen.sha, advanced)
        self.assertEqual(self._local_base_ref(), advanced)
        self.assertEqual(
            self._count_from(frozen.sha, candidate), _WITH_THE_BASE_TAKEN_IN,
        )
        self.assertEqual(
            self._count_from(advanced, candidate), _TWO_LINE_COUNT,
        )

    def _local_base_ref(self) -> str:
        """What `refs/remotes/<remote>/<base>` names in the shared store."""
        return _support.run_git(
            "rev-parse",
            f"refs/remotes/{_support.ORIGIN_REMOTE}/{_support.BASE_BRANCH}",
            cwd=self._repo.clone,
        ).strip()

    def _count_from(self, base: str, candidate: str) -> int:
        """What the candidate adds when measured from the given base id."""
        return additions._count_added_lines(
            self._repo.worktree, base, candidate,
        ).additions


class PinnedDiffInputTest(unittest.TestCase):
    """What decides the count comes from the commit, or the count is refused."""

    def setUp(self) -> None:
        self._repo = _support.CandidateRepo()
        self._repo.prepare(self)
        self._base = _support.head_of(self._repo.clone)
        self._candidate = self._repo.commit({_FEATURE_PATH: _TWO_LINES})

    def test_uncommitted_attributes_decide_nothing(self) -> None:
        # Left to itself git reads `.gitattributes` out of the WORKING TREE, so
        # an uncommitted `* -diff` beside the work would have this candidate
        # measure as zero while the pull request a human reads shows the text.
        (self._repo.worktree / _ATTRIBUTES_PATH).write_text(_HIDE_EVERYTHING)

        measured = additions._count_added_lines(
            self._repo.worktree, self._base, self._candidate,
        )

        self.assertEqual(measured.additions, _TWO_LINE_COUNT)

    def test_a_planted_size_threshold_decides_nothing(self) -> None:
        # `core.bigFileThreshold` lives in the config the agent's worktree
        # shares, and below the size of any real file it makes every path in
        # the candidate binary.
        _support.run_git(*_BIG_FILE_THRESHOLD, cwd=self._repo.worktree)

        measured = additions._count_added_lines(
            self._repo.worktree, self._base, self._candidate,
        )

        self.assertEqual(measured.additions, _TWO_LINE_COUNT)

    def test_an_inherited_attr_source_decides_nothing(self) -> None:
        # `GIT_ATTR_SOURCE` names the tree attributes are read from and beats
        # the `attr.tree` config, so a value this process inherited would
        # decide the reading over any pin on the command line. Pointed at a
        # tree that hides everything, it would report this candidate as a
        # successful zero.
        hostile = self._repo.commit({_ATTRIBUTES_PATH: _HIDE_EVERYTHING})

        with patch.dict(os.environ, {_ATTR_SOURCE_ENV: hostile}):
            measured = additions._count_added_lines(
                self._repo.worktree, self._base, self._candidate,
            )

        self.assertEqual(measured.additions, _TWO_LINE_COUNT)

    def test_a_configured_algorithm_decides_nothing(self) -> None:
        # The algorithms pair a change with repeated lines in it differently,
        # and they differ by whole lines. Left to `diff.algorithm`, the same
        # two commits measure differently on two hosts -- and a `git config`
        # beside the work retunes the ceiling from below it.
        opening = self._repo.commit({_AMBIGUOUS_PATH: _AMBIGUOUS_BEFORE})
        candidate = self._repo.commit({_AMBIGUOUS_PATH: _AMBIGUOUS_AFTER})
        _support.run_git(*_HISTOGRAM_ALGORITHM, cwd=self._repo.worktree)

        measured = additions._count_added_lines(
            self._repo.worktree, opening, candidate,
        )

        self.assertTrue(measured.is_measured)
        self.assertEqual(measured.additions, _MYERS_ADDITIONS)

    def test_a_repository_binary_driver_refuses(self) -> None:
        # A driver the repository's own config declares binary turns a path
        # binary the moment any attribute assigns it -- including one the
        # candidate committed, which the pinned tree honours by design.
        _support.run_git(*_BINARY_DRIVER, cwd=self._repo.worktree)

        measured = additions._count_added_lines(
            self._repo.worktree, self._base, self._candidate,
        )

        self.assertEqual(measured.failure, MeasurementFailure.DIFF_UNPINNABLE)
        self.assertEqual(
            (measured.base_sha, measured.candidate_sha),
            (self._base, self._candidate),
        )


class PlantedAttributesFileTest(unittest.TestCase):
    """`info/attributes` is inspected, never opened, and never followed."""

    def setUp(self) -> None:
        self._repo = _support.CandidateRepo()
        self._repo.prepare(self)
        self._base = _support.head_of(self._repo.clone)
        self._candidate = self._repo.commit({_FEATURE_PATH: _TWO_LINES})
        self._planted = self._repo.clone / ".git" / "info" / "attributes"
        self._planted.parent.mkdir(parents=True, exist_ok=True)

    def test_a_file_with_attributes_in_it_refuses(self) -> None:
        # Not config, so nothing on the command line overrides it, and it
        # outranks the pinned tree. A reading nobody can pin refuses rather
        # than reporting a zero.
        self._planted.write_text(_HIDE_EVERYTHING)

        measured = self._measure()

        self.assertEqual(measured.failure, MeasurementFailure.DIFF_UNPINNABLE)
        self.assertIsNone(measured.additions)

    def test_a_symlink_is_refused_not_followed(self) -> None:
        # The path is one the agent can create, so what sits there need not be
        # a file at all. Followed, this link answers for an empty file and the
        # measurement proceeds on a repository whose attributes it never saw --
        # and a link to `/dev/zero` would answer forever.
        empty = self._repo.clone / "empty-attributes"
        empty.write_text("")
        os.symlink(empty, self._planted)

        measured = self._measure()

        self.assertEqual(measured.failure, MeasurementFailure.DIFF_UNPINNABLE)

    def test_a_fifo_is_refused_without_blocking(self) -> None:
        # A FIFO nobody writes to holds an `open` forever, which would take the
        # tick with it. Nothing here opens the path: the entry is stat-ed, and
        # what is not a regular file is refused on the spot.
        os.mkfifo(self._planted)
        measured = []

        reader = threading.Thread(
            target=lambda: measured.append(self._measure()), daemon=True,
        )
        reader.start()
        reader.join(timeout=_UNBLOCKED_SECONDS)

        self.assertTrue(measured, "the measurement blocked on a FIFO")
        self.assertEqual(
            measured[0].failure, MeasurementFailure.DIFF_UNPINNABLE,
        )

    def _measure(self):
        """What the count makes of this world's planted entry."""
        return additions._count_added_lines(
            self._repo.worktree, self._base, self._candidate,
        )


if __name__ == "__main__":
    unittest.main()
