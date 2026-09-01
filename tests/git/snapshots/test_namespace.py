# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The one ref namespace a snapshot may occupy, and what may not enter it."""

from __future__ import annotations

import re
import unittest

from orchestrator.git.snapshots import namespace

ISSUE = 41
CYCLE = 3
GENERATION = 1

EXPECTED_REF = "refs/orchestrator/late-split/issue-41/cycle-3/gen-1"

# The ref-safe segment a slug is sanitized into before it may qualify a local
# ref, and an identity wide enough to push the built name at its bound.
REPOSITORY = "owner__repo"

_BIG = 1000000000000

# Every identity a pinned comment could hand the builder that is not one. Each
# is a value `int(...)` would happily convert, which is the whole reason the
# builder refuses rather than converts.
NOT_IDENTITIES = (True, 0, -1, 2.9, "41", None)

# The same for the generation, which is a counter rather than an identity and
# so floors one lower: zero is a real generation, and only the shapes that are
# not whole numbers at all -- plus a negative one -- are refused.
NOT_COUNTERS = (True, -1, 2.9, "1", None)

# The three fields a whole ref is built from, spelled as the builder is called
# with them so a test can damage exactly one of them.
WHOLE_IDENTITY = (
    ("issue_number", ISSUE), ("cycle_id", CYCLE), ("generation", GENERATION),
)


class SnapshotRefTest(unittest.TestCase):
    """A ref is built from three identities and from nothing else."""

    def test_it_names_the_issue_cycle_and_generation(self) -> None:
        built = namespace.snapshot_ref(
            issue_number=ISSUE, cycle_id=CYCLE, generation=GENERATION,
        )

        self.assertEqual(built, EXPECTED_REF)

    def test_the_same_identity_builds_the_same_ref(self) -> None:
        # What makes the create idempotent: a tick that pushed the ref and
        # died re-derives the same name from the same frozen record.
        self.assertEqual(
            namespace.snapshot_ref(
                issue_number=ISSUE, cycle_id=CYCLE, generation=GENERATION,
            ),
            namespace.snapshot_ref(
                issue_number=ISSUE, cycle_id=CYCLE, generation=GENERATION,
            ),
        )

    def test_the_floor_of_each_component_is_a_ref(self) -> None:
        # Where the two numeric policies part. An identity floors at 1, and
        # the generation floors at 0 -- a cycle that froze a candidate before
        # adjudicating it is a counter rather than an identity, so zero is a
        # real value there and not one an issue or a cycle may take.
        self.assertEqual(
            namespace.snapshot_ref(
                issue_number=1, cycle_id=1, generation=0,
            ),
            "refs/orchestrator/late-split/issue-1/cycle-1/gen-0",
        )

    def test_a_damaged_identity_builds_no_ref(self) -> None:
        # The fields come out of a pinned comment a human can edit, and every
        # one of these would otherwise be interpolated into a ref this
        # orchestrator pushed and could not recognize again. The refusal names
        # the field it was handed, so a log says which one arrived damaged.
        for field in ("issue_number", "cycle_id"):
            for damaged in NOT_IDENTITIES:
                with self.subTest(field=field, given=damaged):
                    self._assert_refused(
                        f"{field} is not an identity", **{field: damaged},
                    )

    def test_a_damaged_generation_builds_no_ref(self) -> None:
        for damaged in NOT_COUNTERS:
            with self.subTest(given=damaged):
                self._assert_refused(
                    "generation is not a counter", generation=damaged,
                )

    def _assert_refused(self, message: str, **damaged: object) -> None:
        """One damaged field refuses the whole ref, and says which it was."""
        fields = dict(WHOLE_IDENTITY)
        fields.update(damaged)
        whole = rf"\A{re.escape(message)}\Z"

        with self.assertRaisesRegex(namespace.InvalidSnapshotRef, whole):
            namespace.snapshot_ref(**fields)


class SnapshotRefRecognitionTest(unittest.TestCase):
    """Only a ref this domain writes is one it may create, prove, or delete."""

    def test_a_built_ref_is_recognized(self) -> None:
        self.assertTrue(namespace.is_snapshot_ref(EXPECTED_REF))

    def test_a_ref_outside_the_namespace_is_not_one(self) -> None:
        # Each of these is somebody else's ref, and deleting one would destroy
        # an artifact this domain never created.
        for foreign in (
            "refs/heads/main",
            "refs/tags/v1",
            "refs/pull/7/head",
            "refs/orchestrator/other/issue-41/cycle-3/gen-1",
            "refs/orchestrator/late-split/issue-41/cycle-3",
            "refs/orchestrator/late-split/issue-41/cycle-3/gen-1/extra",
            "refs/orchestrator/late-split/issue-0/cycle-3/gen-1",
            "refs/orchestrator/late-split/issue-41/cycle-03/gen-1",
            f"{EXPECTED_REF} ",
            "",
            None,
            41,
        ):
            with self.subTest(ref=foreign):
                self.assertFalse(namespace.is_snapshot_ref(foreign))

    def test_an_unbounded_ref_is_not_one(self) -> None:
        # A number nobody wrote must not become a ref nobody can delete.
        overlong = (
            "refs/orchestrator/late-split/issue-"
            + "1" * namespace.MAX_SNAPSHOT_REF
            + "/cycle-3/gen-1"
        )

        self.assertFalse(namespace.is_snapshot_ref(overlong))


class LocalSnapshotRefTest(unittest.TestCase):
    """A local ref names the repository, and is bounded whatever its slug."""

    def test_it_splices_the_repository_in(self) -> None:
        self.assertEqual(
            namespace.local_snapshot_ref(
                ref=EXPECTED_REF, repository=REPOSITORY,
            ),
            f"refs/orchestrator/late-split-local/{REPOSITORY}"
            "/issue-41/cycle-3/gen-1",
        )

    def test_a_built_local_ref_is_recognized(self) -> None:
        self.assertTrue(namespace.is_local_snapshot_ref(
            namespace.local_snapshot_ref(
                ref=EXPECTED_REF, repository=REPOSITORY,
            ),
        ))

    def test_a_remote_ref_is_not_a_local_one(self) -> None:
        # The two namespaces are separate so a reclamation can say which of
        # them it is deleting.
        self.assertFalse(namespace.is_local_snapshot_ref(EXPECTED_REF))
        self.assertFalse(namespace.is_snapshot_ref(
            namespace.local_snapshot_ref(
                ref=EXPECTED_REF, repository=REPOSITORY,
            ),
        ))

    def test_an_unbounded_repository_builds_no_ref(self) -> None:
        # Configuration bounds a slug at nothing, so a segment that would
        # overflow the local name is refused here rather than producing a ref
        # the recognizer would then reject.
        with self.assertRaises(namespace.InvalidSnapshotRef):
            namespace.local_snapshot_ref(
                ref=EXPECTED_REF,
                repository="r" * (namespace.MAX_REPOSITORY_SEGMENT + 1),
            )

    def test_the_longest_shapes_still_fit(self) -> None:
        # The bound is derived from its inputs rather than restated, so the
        # widest ref either can produce is one the recognizer still accepts.
        widest = namespace.local_snapshot_ref(
            ref=namespace.snapshot_ref(
                issue_number=_BIG, cycle_id=_BIG, generation=_BIG,
            ),
            repository="r" * namespace.MAX_REPOSITORY_SEGMENT,
        )

        self.assertLessEqual(len(widest), namespace.MAX_LOCAL_SNAPSHOT_REF)
        self.assertTrue(namespace.is_local_snapshot_ref(widest))

    def test_a_foreign_ref_builds_no_local_one(self) -> None:
        with self.assertRaises(namespace.InvalidSnapshotRef):
            namespace.local_snapshot_ref(
                ref="refs/heads/main", repository=REPOSITORY,
            )


if __name__ == "__main__":
    unittest.main()
