# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What the flat analytics package still answers for on the trajectory side."""

import unittest


from importlib import import_module


from tests.analytics_reload_helpers import reload_analytics as _reload

_ANALYTICS_PACKAGE = "orchestrator.analytics"


_TRAJECTORY_PACKAGE = "orchestrator.observability.analytics.trajectories"


_API_OWNER = f"{_TRAJECTORY_PACKAGE}.api"


_MODELS_OWNER = f"{_TRAJECTORY_PACKAGE}.models"


# Where the sink lock is minted: the shared JSONL write owner, which no reload
# rebuilds -- unlike the append that takes it.
_IO_OWNER = "orchestrator.observability.analytics.recording.io"


_APPEND = "append_trajectory_record"


_SINK_LOCK = "_TRAJECTORY_FILE_LOCK"


# The published pair the sink is driven by, both of which stay part of what the
# package publishes rather than private leaves a caller reaches past it for.
_ENTRY_POINTS = (_APPEND, "prune_trajectory_records")


# The private caps a caller shrinks to bound a record, paired with the name the
# owner declares each as. They are the live patch surface, so the values the
# package binds have to be the owner's own.
_FORWARDED_CAPS = (
    ("_TRAJECTORY_FIELD_HEAD", "TRAJECTORY_FIELD_HEAD"),
    ("_TRAJECTORY_FIELD_TAIL", "TRAJECTORY_FIELD_TAIL"),
    ("_TRAJECTORY_RECORD_BUDGET", "TRAJECTORY_RECORD_BUDGET"),
)


class ForwardedTrajectorySinkTest(unittest.TestCase):
    """The append and the caps resolve off the analytics package to the
    trajectory owners' own objects, an instance reloaded against a patched
    environment answers with its own append, and every instance answers with
    the one sink lock.
    """

    def test_sink_entry_points_are_published(self) -> None:
        _, analytics = _reload()
        for name in _ENTRY_POINTS:
            with self.subTest(name=name):
                self.assertIn(name, analytics.__all__)

    def test_append_forwards_to_the_owner(self) -> None:
        # Resolved through `sys.modules` in this order because initializing
        # the analytics package is what rebuilds the append owner: naming the
        # package first is what makes the pair the same generation.
        package = import_module(_ANALYTICS_PACKAGE)
        api = import_module(_API_OWNER)
        member = getattr(package, _APPEND)
        self.assertIs(member, getattr(api, _APPEND))
        self.assertEqual(member.__module__, _API_OWNER)

    def test_caps_forward_to_their_owner(self) -> None:
        package = import_module(_ANALYTICS_PACKAGE)
        models = import_module(_MODELS_OWNER)
        for published, declared in _FORWARDED_CAPS:
            with self.subTest(published=published):
                self.assertEqual(
                    getattr(package, published),
                    getattr(models, declared),
                )

    def test_reload_binds_its_own_append(self) -> None:
        # The append is rebuilt for each package instance because it resolves
        # the trajectory path off the settings holder captured at its own
        # import, so an instance reloaded against a patched environment writes
        # where that environment says rather than where the process-wide one
        # does.
        _, analytics = _reload()
        self.assertEqual(getattr(analytics, _APPEND).__module__, _API_OWNER)

    def test_sink_lock_outlives_the_rebuild(self) -> None:
        # The lock is deliberately *not* minted beside the append the rebuild
        # replaces. The two writers of the trajectory file -- that append and
        # the by-age prune -- are safe only while they hold one object, and a
        # caller is free to hold an append imported before any rebuild. A lock
        # re-minted per instance would leave that reference serializing
        # against nothing, so every instance has to answer with the one the
        # `io` owner minted once.
        minted = getattr(import_module(_IO_OWNER), "TRAJECTORY_FILE_LOCK")
        first = _reload()[1]
        second = _reload()[1]
        for analytics in (first, second):
            with self.subTest(instance=id(analytics)):
                self.assertIs(getattr(analytics, _SINK_LOCK), minted)
                self.assertIs(
                    analytics._retention._TRAJECTORY_FILE_LOCK, minted,
                )


if __name__ == "__main__":
    unittest.main()
