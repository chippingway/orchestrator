# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What one candidate is measured to add, and what an unread diff answers.

The counting cases run against real commits because the questions are git's
own: what `--numstat` says about a path it calls binary, what a moved file
looks like with rename detection off, and what a record naming a path with a
tab in it comes back as. The failure cases drive the reading itself off the
rails, since neither a git that will not run nor a record this build cannot
account for can be arranged with a commit. What the reading is pinned against
is a question of its own, and lives beside this one in
`test_pinned_reading.py`.
"""
from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from orchestrator.git import commands
from orchestrator.git.measurement import additions, commits
from orchestrator.git.measurement.models import FrozenCommit, MeasurementFailure
from tests.git.measurement import measurement_test_support as _support

_WORKTREE = Path("/tmp/orchestrator-test-measurement-additions")
_BASE_SHA = "1111111111111111111111111111111111111111"
_CANDIDATE_SHA = "2222222222222222222222222222222222222222"
_GIT_FAILURE = 128
_HARDENED_GIT = "_git_hardened"
_FEATURE_PATH = "feature.py"
_MOVED_PATH = "moved/legacy.py"

# A path with a tab in it, which is a legal filename and arrives from `-z`
# unquoted -- so the record naming it carries a separator inside its last
# field.
_TABBED_PATH = "tab\tname.txt"

# One line of a transport's own stderr, the way a failing end hands it up.
_TRANSPORT_DETAIL = (
    "fatal: could not read Username for 'https://github.com': "
    "terminal prompts disabled"
)

# The two ends a measurement can stop at, each with the reason it stops for.
_STOPPING_ENDS = (
    ("_freeze_base_commit", MeasurementFailure.BASE_UNREADABLE),
    ("_prove_candidate_commit", MeasurementFailure.CANDIDATE_ABSENT),
)

# The two lines of work a case commits when what it is checking is not the
# content itself.
_TWO_LINES = "one\ntwo\n"

# Content git has to call binary: a NUL byte inside the first block is what
# decides it, and nothing about the path name does.
_BINARY_PAYLOAD = b"\x00\x01\x02not text at all\x00\xff"

# Four paths a size gate might be tempted to forgive, with what each adds. It
# forgives none of them: an exemption is a bypass anybody can move work into,
# and the number has to be reproducible from the diff a reviewer opens.
_UNFORGIVEN_PATHS = (
    ("package-lock.json", '{\n  "lockfileVersion": 3\n}\n', 3),
    ("dist/bundle.js", "var a=1;\nvar b=2;\n", 2),
    ("data/rows.csv", "id,name\n1,one\n2,two\n3,three\n", 4),
    ("vendor/library.js", "function vendored() {}\n", 1),
)

# Reports no total can be taken from: a record with a field missing, a count
# that is not a number, a negative one, and a record that is nothing but
# separators.
_UNREADABLE_REPORTS = (
    ("4\tsrc/app.py",),
    ("4\t2\tsrc/app.py", "many\t0\tsrc/other.py"),
    ("4\t2\tsrc/app.py", "-2\t0\tsrc/other.py"),
    ("4\t2\tsrc/app.py", "\t\t\tsrc/other.py"),
)


def _completed(returncode: int, stdout: str) -> subprocess.CompletedProcess:
    """Return a git result carrying the given exit status and stdout."""
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout)


def _numstat(*records: str) -> str:
    """A NUL-delimited numstat report over the given records."""
    return "".join(f"{record}\0" for record in records)


def _count(repo, base: str, candidate: str):
    """The measurement of one candidate against a world's frozen base."""
    return additions._count_added_lines(repo.worktree, base, candidate)


class _StubbedGit:
    """Every hardened call the count makes, with the diff's answer supplied.

    The count asks three things of git -- what diff config the repository
    carries, where `info/attributes` lives, and the diff itself -- so a stub
    that answered all three the same way would have the reading refuse before
    it ever ran. This one answers the two probes as a clean checkout does and
    hands the caller's own result to the diff, which is the call under test.
    """

    def __init__(self, diff_result: subprocess.CompletedProcess) -> None:
        self._diff_result = diff_result

    def __call__(self, *args: str, cwd: Path, **pins) -> subprocess.CompletedProcess:
        if args[0] == "config":
            return _completed(1, "")
        if args[0] == "rev-parse":
            return _completed(0, str(cwd / ".git" / "info" / "attributes"))
        return self._diff_result


class AddedLineCountTest(unittest.TestCase):
    """Every path counts, and only lines do."""

    def setUp(self) -> None:
        self._repo = _support.CandidateRepo()
        self._repo.prepare(self)
        self._base = self._repo.base()

    def test_only_added_lines_are_counted(self) -> None:
        # A deletion is not a negative addition: the ceiling bounds what a
        # reviewer has to read, and removing a line is not reading one.
        self._repo.commit({_FEATURE_PATH: "one\ntwo\nthree\n"})
        candidate = self._repo.commit({_FEATURE_PATH: "one\nthree\nfour\n"})

        measured = _count(self._repo, self._base, candidate)

        self.assertTrue(measured.is_measured)
        self.assertEqual(measured.additions, 3)

    def test_binary_content_contributes_nothing(self) -> None:
        # git reports `-` for a path with no lines in it, and that is the
        # honest count: the path is in the diff, nothing was ruled out, there
        # is simply nothing textual to have added.
        candidate = self._repo.commit({
            "logo.png": _BINARY_PAYLOAD,
            _FEATURE_PATH: "one\ntwo\n",
        })

        self.assertEqual(_count(self._repo, self._base, candidate).additions, 2)

    def test_generated_and_vendored_paths_count(self) -> None:
        candidate = self._repo.commit({
            path: text for path, text, _ in _UNFORGIVEN_PATHS
        })

        self.assertEqual(
            _count(self._repo, self._base, candidate).additions,
            sum(lines for _, _, lines in _UNFORGIVEN_PATHS),
        )

    def test_a_moved_file_counts_where_it_lands(self) -> None:
        # The file being moved is one the BASE carries, so the diff really is a
        # rename: with detection on it reports no additions at all, and the
        # count would be zero for work that has to be reviewed at its new path.
        # A candidate could otherwise be made to measure small by moving into
        # place what it was going to write anyway.
        candidate = self._repo.move(_support.BASE_FILE, _MOVED_PATH)

        self.assertEqual(
            _count(self._repo, self._base, candidate).additions,
            _support.BASE_FILE_LINES,
        )

    def test_a_path_with_a_tab_still_counts(self) -> None:
        # A tab is a legal byte in a filename and `-z` leaves it unquoted, so
        # the record naming it carries a separator in its path. Read as another
        # field, a perfectly ordinary file would refuse the whole count.
        candidate = self._repo.commit({_TABBED_PATH: _TWO_LINES})

        measured = _count(self._repo, self._base, candidate)

        self.assertTrue(measured.is_measured)
        self.assertEqual(measured.additions, 2)

    def test_the_named_candidate_is_measured(self) -> None:
        # The record names a commit, and the retry after a crash has to measure
        # that one: a reading of HEAD would grow with every commit the branch
        # collected while the adjudication was in flight.
        first = self._repo.commit({_FEATURE_PATH: "one\ntwo\n"})
        self._repo.commit({"later.py": "three\nfour\nfive\n"})

        measured = _count(self._repo, self._base, first)

        self.assertEqual(measured.candidate_sha, first)
        self.assertEqual(measured.additions, 2)


class CountFailureTest(unittest.TestCase):
    """A reading that could not be taken is never a count of zero."""

    def test_the_prospective_range_is_asked_for(self) -> None:
        # Three-dot, so a base that moved on since the branch forked is not
        # read as work this branch did; `--no-renames` so a move counts; `-z`
        # and `--numstat` so each path is one countable record. The rest is
        # what decides which paths have lines and how many, none of which may
        # be left to the checkout: submodules, the user attributes file, the
        # threshold above which git stops looking for lines, the algorithm that
        # pairs a change up, and the directory the diff is held to.
        with patch.object(
            commands, _HARDENED_GIT,
            side_effect=_StubbedGit(_completed(0, "")),
        ) as git:
            additions._count_added_lines(_WORKTREE, _BASE_SHA, _CANDIDATE_SHA)

            self.assertEqual(
                git.call_args.args,
                (
                    "-c", f"core.attributesFile={os.devnull}",
                    "-c", "core.bigFileThreshold=512m",
                    "diff", "--numstat", "--no-renames", "-z",
                    "--ignore-submodules=none", "--diff-algorithm=myers",
                    "--no-relative",
                    f"{_BASE_SHA}...{_CANDIDATE_SHA}",
                ),
            )
            self.assertEqual(git.call_args.kwargs["cwd"], _WORKTREE)

    def test_the_attribute_source_is_pinned(self) -> None:
        # The two settings a `-c` cannot win: `GIT_ATTR_SOURCE` outranks the
        # `attr.tree` config, so an inherited one would name the tree the
        # attributes come from, and the system-wide attributes answer to no
        # config key at all. Both are stated for the call itself.
        with patch.object(
            commands, _HARDENED_GIT,
            side_effect=_StubbedGit(_completed(0, "")),
        ) as git:
            additions._count_added_lines(_WORKTREE, _BASE_SHA, _CANDIDATE_SHA)

            self.assertEqual(
                dict(git.call_args.kwargs["env_extra"]),
                {
                    "GIT_ATTR_SOURCE": _CANDIDATE_SHA,
                    "GIT_ATTR_NOSYSTEM": "1",
                },
            )

    def test_a_failed_diff_carries_both_commits(self) -> None:
        with patch.object(
            commands, _HARDENED_GIT,
            side_effect=_StubbedGit(
                _completed(_GIT_FAILURE, "fatal: bad object"),
            ),
        ):
            measured = additions._count_added_lines(
                _WORKTREE, _BASE_SHA, _CANDIDATE_SHA,
            )

        self.assertEqual(measured.failure, MeasurementFailure.DIFF_FAILED)
        self.assertIsNone(measured.additions)
        self.assertFalse(measured.is_measured)
        self.assertEqual(
            (measured.base_sha, measured.candidate_sha),
            (_BASE_SHA, _CANDIDATE_SHA),
        )

    def test_an_unread_record_refuses_the_count(self) -> None:
        # A partial total looks exactly like a whole one, and would be
        # adjudicated as though a reviewer had seen the paths it skipped.
        for records in _UNREADABLE_REPORTS:
            with self.subTest(records=records):
                with patch.object(
                    commands, _HARDENED_GIT,
                    side_effect=_StubbedGit(
                        _completed(0, _numstat(*records)),
                    ),
                ):
                    measured = additions._count_added_lines(
                        _WORKTREE, _BASE_SHA, _CANDIDATE_SHA,
                    )

                self.assertEqual(
                    measured.failure, MeasurementFailure.DIFF_UNREADABLE,
                )
                self.assertIsNone(measured.additions)

    def test_an_empty_diff_is_a_measured_zero(self) -> None:
        # The one reading that legitimately totals nothing: a candidate whose
        # commits change nothing against the base. It is a measurement, not a
        # failure, and the record says so.
        with patch.object(
            commands, _HARDENED_GIT,
            side_effect=_StubbedGit(_completed(0, "")),
        ):
            measured = additions._count_added_lines(
                _WORKTREE, _BASE_SHA, _CANDIDATE_SHA,
            )

        self.assertTrue(measured.is_measured)
        self.assertEqual(measured.additions, 0)


class MeasurementCompositionTest(unittest.TestCase):
    """The measurement stops at the first end it could not establish."""

    def setUp(self) -> None:
        self._repo = _support.CandidateRepo()
        self._repo.prepare(self)

    def test_a_frozen_pair_is_counted_and_reported(self) -> None:
        base = self._repo.base()
        candidate = self._repo.commit({_FEATURE_PATH: "one\ntwo\nthree\n"})

        measured = additions._measure_candidate(
            self._repo.spec, self._repo.worktree, candidate,
        )

        self.assertTrue(measured.is_measured)
        self.assertEqual(measured.additions, 3)
        self.assertEqual(
            (measured.base_sha, measured.candidate_sha), (base, candidate),
        )

    def test_an_unproved_candidate_keeps_the_base(self) -> None:
        # What the retry needs: the base this attempt was going to measure
        # against, rather than one re-derived from a branch that has moved.
        base = self._repo.base()

        measured = additions._measure_candidate(
            self._repo.spec, self._repo.worktree, _support.ABSENT_SHA,
        )

        self.assertEqual(measured.failure, MeasurementFailure.CANDIDATE_ABSENT)
        self.assertEqual(measured.base_sha, base)
        self.assertIsNone(measured.additions)

    def test_an_unfrozen_base_stops_the_reading(self) -> None:
        candidate = self._repo.commit({_FEATURE_PATH: "one\n"})
        unreadable = FrozenCommit(failure=MeasurementFailure.BASE_UNREADABLE)
        with patch.object(
            commits, "_freeze_base_commit", return_value=unreadable,
        ), patch.object(commits, "_prove_candidate_commit") as prove:
            measured = additions._measure_candidate(
                self._repo.spec, self._repo.worktree, candidate,
            )

            prove.assert_not_called()

        self.assertEqual(measured.failure, MeasurementFailure.BASE_UNREADABLE)
        self.assertEqual(measured.base_sha, "")

    def test_the_stopping_end_hands_up_its_own_line(self) -> None:
        # The reading is taken here and reported far from here: the record
        # written for the retry, the failure both sinks carry, and the park a
        # human answers are all produced after the stderr that explains them is
        # gone. Whichever end stopped, its line rides out on the measurement.
        candidate = self._repo.commit({_FEATURE_PATH: "one\n"})
        for end, failure in _STOPPING_ENDS:
            with self.subTest(end=end):
                with patch.object(commits, end, return_value=FrozenCommit(
                    failure=failure, detail=_TRANSPORT_DETAIL,
                )):
                    measured = additions._measure_candidate(
                        self._repo.spec, self._repo.worktree, candidate,
                    )

                self.assertEqual(measured.failure, failure)
                self.assertEqual(measured.detail, _TRANSPORT_DETAIL)


if __name__ == "__main__":
    unittest.main()
