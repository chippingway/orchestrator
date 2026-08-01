# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Trajectory reader facade surface tests."""

import unittest


from orchestrator import trajectory_reader as tr


from orchestrator import _trajectory_records as records


_READER_MODULE = "orchestrator.trajectory_reader"


class ModuleLayoutTest(unittest.TestCase):
    """Pin the facade / read-leaf split so callers keep one import site.

    The private `orchestrator._trajectory_records` leaf is the record API: it
    is where the log path, the parse call shape, and the JSONL read are
    entered, and it answers for the record and view dataclasses that live
    under `orchestrator/observability/trajectory_viewer/`.
    `orchestrator.trajectory_reader` re-exports that whole surface under the
    same names and owns the filtering and summary aggregation. The dashboard
    and the tests reach everything through `trajectory_reader`, so the
    re-exported names must stay the same objects the leaf answers with and the
    filter surface must stay defined on the facade.
    """

    def test_read_surface_reexported_from_leaf(self) -> None:
        for name in (
            "TrajectoryStepView",
            "TimelineEntry",
            "TurnUsageView",
            "RunUsageView",
            "TrajectoryRun",
            "resolve_log_path",
            "log_unconfigured_message",
            "read_trajectories",
            "parse_record",
            "TRAJECTORY_EVENT",
            "TIMELINE_PROMPT",
            "TIMELINE_OUTPUT",
            "UNCONFIGURED_LOG_MESSAGE",
        ):
            with self.subTest(name=name):
                self.assertIs(getattr(tr, name), getattr(records, name))

    def test_read_symbols_have_leaf_module_of_record(self) -> None:
        # One module name for the whole record API, whether the leaf defines
        # the symbol itself or a viewer owner does and stamps it with the site
        # it is published from -- which is where a repr or a reader following
        # `__module__` has always landed.
        for symbol in (
            tr.TrajectoryRun,
            tr.TrajectoryStepView,
            tr.parse_record,
            tr.read_trajectories,
            tr.resolve_log_path,
        ):
            with self.subTest(symbol=symbol.__name__):
                self.assertEqual(symbol.__module__, "orchestrator._trajectory_records")

    def test_filter_surface_defined_on_facade(self) -> None:
        for symbol in (
            tr.FilterOptions,
            tr.RunFilterOptions,
            tr.TrajectorySummary,
            tr.filter_options,
            tr.filter_runs,
            tr.summarize,
        ):
            with self.subTest(symbol=symbol.__name__):
                self.assertEqual(symbol.__module__, _READER_MODULE)
