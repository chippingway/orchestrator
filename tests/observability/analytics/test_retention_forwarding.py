# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What the flat analytics package still answers for on the prune side."""

import unittest


from importlib import import_module


from tests.analytics_reload_helpers import reload_analytics as _reload

_ANALYTICS_PACKAGE = "orchestrator.analytics"


_RETENTION_OWNER = "orchestrator.observability.analytics.retention"


# Where both sink locks are minted: the shared JSONL write owner, which no
# reload rebuilds -- unlike the prune that takes them.
_IO_OWNER = "orchestrator.observability.analytics.recording.io"


# The three entry points the compatibility package forwards: the per-tick
# wrapper `main._run_tick` reaches, and the two by-age prunes an operator
# drives, one per sink.
_ENTRY_POINTS = (
    "prune_old_records",
    "prune_trajectory_records",
    "prune_with_retention_logging",
)


# The lock each prune takes, paired with the name the `io` owner minted it as.
# They stay separate objects so neither file's rewrite blocks on the other's
# append.
_SINK_LOCKS = (
    ("_FILE_LOCK", "ANALYTICS_FILE_LOCK"),
    ("_TRAJECTORY_FILE_LOCK", "TRAJECTORY_FILE_LOCK"),
)


def _owner_namespace(analytics):
    """The namespace of the retention owner one package instance forwards to.

    Reached through the forwarded function rather than `sys.modules`, because
    a reloaded instance's owner is installed under its name only for as long
    as that reload's import world is.
    """
    return analytics.prune_old_records.__globals__


class ForwardedRetentionTest(unittest.TestCase):
    """The three prune entry points resolve off the analytics package to the
    retention owner's own objects, an instance reloaded against a patched
    environment answers with its own, and every instance prunes under the one
    pair of sink locks.
    """

    def test_entry_points_are_published(self) -> None:
        _, analytics = _reload()
        for name in _ENTRY_POINTS:
            with self.subTest(name=name):
                self.assertIn(name, analytics.__all__)

    def test_entry_points_forward_to_the_owner(self) -> None:
        # Resolved through `sys.modules` in this order because initializing
        # the analytics package is what rebuilds the retention owner: naming
        # the package first is what makes the pair the same generation.
        package = import_module(_ANALYTICS_PACKAGE)
        retention = import_module(_RETENTION_OWNER)
        for name in _ENTRY_POINTS:
            with self.subTest(name=name):
                member = getattr(package, name)
                self.assertIs(member, getattr(retention, name))
                self.assertEqual(member.__module__, _RETENTION_OWNER)

    def test_reload_binds_its_own_prune(self) -> None:
        # The prune is rebuilt for each package instance because it resolves
        # both sink paths off the settings holder captured at its own import,
        # so an instance reloaded against a patched environment prunes what
        # that environment says rather than the process-wide files.
        _, analytics = _reload()
        for name in _ENTRY_POINTS:
            with self.subTest(name=name):
                self.assertEqual(
                    getattr(analytics, name).__module__, _RETENTION_OWNER,
                )

    def test_sink_locks_outlive_the_rebuild(self) -> None:
        # The locks are deliberately *not* minted beside the prune the rebuild
        # replaces. A sink's append and its by-age prune are safe only while
        # they hold one object, and a caller is free to hold an append it
        # imported before any rebuild. A lock re-minted per instance would
        # leave that reference serializing against nothing, so every instance
        # has to answer with the one the `io` owner minted once.
        io_owner = import_module(_IO_OWNER)
        for analytics in (_reload()[1], _reload()[1]):
            namespace = _owner_namespace(analytics)
            for published, minted in _SINK_LOCKS:
                with self.subTest(instance=id(analytics), lock=published):
                    self.assertIs(
                        getattr(analytics, published),
                        getattr(io_owner, minted),
                    )
                    self.assertIs(namespace[minted], getattr(io_owner, minted))


if __name__ == "__main__":
    unittest.main()
