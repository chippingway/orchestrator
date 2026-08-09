# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What the flat analytics package still answers for on the append side."""

import unittest


from importlib import import_module

_ANALYTICS_PACKAGE = "orchestrator.analytics"


_RECORDING_PACKAGE = "orchestrator.observability.analytics.recording"


_EVENTS_OWNER = f"{_RECORDING_PACKAGE}.events"


_AGENT_EXIT_OWNER = f"{_RECORDING_PACKAGE}.agent_exit"


_SINK_OWNER = "orchestrator.observability.analytics.sink"


# Each historical name paired with the module that defines it now: the shared
# envelope, the append that resolves the analytics knob, the three recorders a
# producer calls directly, and the one with a sequence to run before it writes.
_RECORDERS = (
    ("append_record", _EVENTS_OWNER),
    ("build_record", _SINK_OWNER),
    ("record_agent_exit", _AGENT_EXIT_OWNER),
    ("record_repo_skill_catalog", _EVENTS_OWNER),
    ("record_stage_enter", _EVENTS_OWNER),
    ("record_stage_evaluation", _EVENTS_OWNER),
)


class ForwardedRecorderTest(unittest.TestCase):
    """The recorders resolve off the analytics package to the owner's own
    objects. What the same package forwards for the settings, the by-age
    prune, and the opt-in trajectory sink is covered beside each of those
    owners, under `tests/observability/analytics/`.
    """

    def test_recorders_forward_to_the_owner(self) -> None:
        package = import_module(_ANALYTICS_PACKAGE)
        recording = import_module(_RECORDING_PACKAGE)
        for name, owner in _RECORDERS:
            with self.subTest(name=name):
                member = getattr(package, name)
                self.assertIs(member, getattr(recording, name))
                self.assertEqual(member.__module__, owner)

    def test_recorders_are_published(self) -> None:
        published = import_module(_ANALYTICS_PACKAGE).__all__
        for name, _owner in _RECORDERS:
            with self.subTest(name=name):
                self.assertIn(name, published)


if __name__ == "__main__":
    unittest.main()
