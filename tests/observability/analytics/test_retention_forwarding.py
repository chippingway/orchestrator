# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What the flat analytics package still answers for on the prune side."""

import unittest


from importlib import import_module

_ANALYTICS_PACKAGE = "orchestrator.analytics"


_RETENTION_OWNER = "orchestrator.observability.analytics.retention"


# Where both sink locks are minted: the shared write owner above the recording
# and trajectory packages, so a prune and the append racing it hold one object.
_SINK_OWNER = "orchestrator.observability.analytics.sink"


# The three entry points the compatibility package forwards: the per-tick
# wrapper `main._run_tick` reaches, and the two by-age prunes an operator
# drives, one per sink.
_ENTRY_POINTS = (
    "prune_old_records",
    "prune_trajectory_records",
    "prune_with_retention_logging",
)


# The locks the two prunes take. They stay separate objects so neither file's
# rewrite blocks on the other's append.
_SINK_LOCKS = ("ANALYTICS_FILE_LOCK", "TRAJECTORY_FILE_LOCK")


class ForwardedRetentionTest(unittest.TestCase):
    """The three prune entry points resolve off the analytics package to the
    retention owner's own objects, and both prunes run under the one pair of
    minted sink locks.
    """

    def test_entry_points_are_published(self) -> None:
        package = import_module(_ANALYTICS_PACKAGE)
        for name in _ENTRY_POINTS:
            with self.subTest(name=name):
                self.assertIn(name, package.__all__)

    def test_entry_points_forward_to_the_owner(self) -> None:
        package = import_module(_ANALYTICS_PACKAGE)
        retention = import_module(_RETENTION_OWNER)
        for name in _ENTRY_POINTS:
            with self.subTest(name=name):
                member = getattr(package, name)
                self.assertIs(member, getattr(retention, name))
                self.assertEqual(member.__module__, _RETENTION_OWNER)

    def test_the_prunes_take_the_minted_sink_locks(self) -> None:
        # A sink's append and its by-age prune are safe only while they hold
        # one object, which is why both locks are minted on the shared owner
        # rather than beside either writer.
        retention = import_module(_RETENTION_OWNER)
        sink = import_module(_SINK_OWNER)
        for lock in _SINK_LOCKS:
            with self.subTest(lock=lock):
                self.assertIs(getattr(retention, lock), getattr(sink, lock))


if __name__ == "__main__":
    unittest.main()
