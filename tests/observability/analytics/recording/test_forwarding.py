# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What the flat analytics package still answers for on the append side."""

import sys
import unittest


from importlib import import_module
from pathlib import Path

from tests.analytics_reload_helpers import reload_analytics as _reload

_ANALYTICS_PACKAGE = "orchestrator.analytics"


_RECORDING_PACKAGE = "orchestrator.observability.analytics.recording"


_EVENTS_OWNER = f"{_RECORDING_PACKAGE}.events"


_RECORDERS = (
    "append_record",
    "build_record",
    "record_agent_exit",
    "record_repo_skill_catalog",
    "record_stage_enter",
    "record_stage_evaluation",
)


def _owners_on_disk(package) -> tuple[str, ...]:
    """Every owner beside the initializer, read off disk rather than declared.

    Discovered so a new owner is covered the day it lands rather than the day
    somebody remembers to add it to a list.
    """
    return tuple(sorted(
        module_path.stem
        for module_path in Path(package.__file__).parent.glob("*.py")
        if module_path.stem != "__init__"
    ))


class ForwardedRecorderTest(unittest.TestCase):
    """The recorders resolve off the analytics package to the owner's own
    objects. What the same package forwards for the by-age prune and for the
    opt-in trajectory sink is covered beside each of those owners, under
    `tests/observability/analytics/`.
    """

    def test_recorders_forward_to_the_owner(self) -> None:
        # Resolved through `sys.modules` in this order because initializing
        # the analytics package is what reloads the recording owners: naming
        # the package first is what makes the pair the same generation.
        package = import_module(_ANALYTICS_PACKAGE)
        recording = import_module(_RECORDING_PACKAGE)
        for name in _RECORDERS:
            with self.subTest(name=name):
                member = getattr(package, name)
                self.assertIs(member, getattr(recording, name))
                self.assertEqual(member.__module__, _EVENTS_OWNER)

    def test_reloaded_instance_binds_own_recorders(self) -> None:
        _, analytics = _reload()
        for name in _RECORDERS:
            with self.subTest(name=name):
                self.assertEqual(
                    getattr(analytics, name).__module__, _EVENTS_OWNER,
                )

    def test_reload_leaves_one_generation_of_owners(self) -> None:
        # A reload rebuilds `events` and nothing else beneath the package, so
        # every owner has to come out of it as one object under both names it
        # is reachable by: the attribute `from <package> import <owner>`
        # answers with, and the `sys.modules` entry an absolute import does.
        # A second generation of `io` would mint a second sink lock for the
        # append and the prune to take one each of, and which one a caller got
        # would depend on how it happened to spell the import.
        _reload()
        package = import_module(_RECORDING_PACKAGE)
        for owner in _owners_on_disk(package):
            with self.subTest(owner=owner):
                self.assertIs(
                    getattr(package, owner),
                    sys.modules[f"{_RECORDING_PACKAGE}.{owner}"],
                )
        self.assertIs(
            import_module(_ANALYTICS_PACKAGE)._FILE_LOCK,
            package.io.ANALYTICS_FILE_LOCK,
        )


if __name__ == "__main__":
    unittest.main()
