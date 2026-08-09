# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What the flat analytics package still answers for on the trajectory side."""

import unittest


from importlib import import_module

_ANALYTICS_PACKAGE = "orchestrator.analytics"


_TRAJECTORY_PACKAGE = "orchestrator.observability.analytics.trajectories"


_API_OWNER = f"{_TRAJECTORY_PACKAGE}.api"


# Where the sink lock is minted: the shared write owner above both packages,
# so the append that takes it and the by-age prune that rewrites the file
# under it cannot end up on two objects.
_SINK_OWNER = "orchestrator.observability.analytics.sink"


_APPEND = "append_trajectory_record"


# The published pair the sink is driven by, both of which stay part of what the
# package publishes rather than private leaves a caller reaches past it for.
_ENTRY_POINTS = (_APPEND, "prune_trajectory_records")


class ForwardedTrajectorySinkTest(unittest.TestCase):
    """The bare append resolves off the analytics package to the trajectory
    owner's own object, and that append takes the one minted sink lock.
    """

    def test_sink_entry_points_are_published(self) -> None:
        package = import_module(_ANALYTICS_PACKAGE)
        for name in _ENTRY_POINTS:
            with self.subTest(name=name):
                self.assertIn(name, package.__all__)

    def test_append_forwards_to_the_owner(self) -> None:
        package = import_module(_ANALYTICS_PACKAGE)
        api = import_module(_API_OWNER)
        member = getattr(package, _APPEND)
        self.assertIs(member, getattr(api, _APPEND))
        self.assertEqual(member.__module__, _API_OWNER)

    def test_the_append_takes_the_minted_sink_lock(self) -> None:
        # The two writers of the trajectory file -- this append and the by-age
        # prune -- are safe only while they hold one object, which is why the
        # lock is minted on the shared owner rather than beside either of them.
        api = import_module(_API_OWNER)
        self.assertIs(
            api.TRAJECTORY_FILE_LOCK,
            import_module(_SINK_OWNER).TRAJECTORY_FILE_LOCK,
        )


if __name__ == "__main__":
    unittest.main()
