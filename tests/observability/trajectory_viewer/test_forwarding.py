# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What the flat trajectory modules still answer for on the record side."""
from __future__ import annotations

import unittest
from importlib import import_module
from types import MappingProxyType


_PACKAGE = "orchestrator.observability.trajectory_viewer"

_COERCION = f"{_PACKAGE}.coercion"

_CONSTANTS = f"{_PACKAGE}.constants"

_MODELS = f"{_PACKAGE}.models"

_PARSING = f"{_PACKAGE}.parsing"

_READING = f"{_PACKAGE}.reading"

_RUNS = f"{_PACKAGE}.runs"

_TIMELINE = f"{_PACKAGE}.timeline_views"

_USAGE = f"{_PACKAGE}.usage_views"

# The historical import site the four frozen views and the record report as
# their module. It is the site their API is documented at, so a repr, a pickle,
# and a reader following `__module__` all still land there.
_ORIGIN_MODULE = "orchestrator._trajectory_records"

_CONSTANT_NAMES = (
    "FIXTURE_PROMPT",
    "FIXTURE_SESSION_PREFIX",
    "FIXTURE_SKILL_TOOL",
    "TIMELINE_OUTPUT",
    "TIMELINE_PROMPT",
    "TRAJECTORY_EVENT",
    "UNCONFIGURED_LOG_MESSAGE",
)

_COERCION_NAMES = (
    "as_list",
    "coerce_float",
    "coerce_int",
    "coerce_str",
    "coerce_str_tuple",
)

# The field names and the two body accessors travel with the views: the
# signatures are declared in terms of the former, and the `content` property
# each bodied view answers through is installed from the latter.
_MODEL_NAMES = (
    "CONTENT_FIELD",
    "KIND_FIELD",
    "NAME_FIELD",
    "ORIGIN_MODULE",
    "RunUsageView",
    "STEP_VIEW_SIGNATURE",
    "TIMELINE_ENTRY_SIGNATURE",
    "TOOL_ID_FIELD",
    "TURN_FIELD",
    "TimelineEntry",
    "TrajectoryStepView",
    "TurnUsageView",
    "public_entry_content",
    "public_step_content",
)

_USAGE_NAMES = (
    "cost_source",
    "cost_usd",
    "model",
    "step_count",
    "tool_calls",
    "total_tokens",
    "usage_for_turn",
)

_TIMELINE_NAMES = (
    "detail_label",
    "is_fixture",
    "label",
    "timeline",
    "turn_map",
)

_PARSE_NAMES = (
    "parse_record",
    "parse_run_usage",
    "parse_step",
    "parse_turn",
)

_READ_NAMES = (
    "parse_trajectory_line",
    "read_trajectories",
    "read_trajectory_file",
    "run_sort_key",
)

# The flat modules a historical caller reaches the record side through, and the
# owner each one's names resolve to. A name reached through one of these is
# still a name it reached, so it has to keep answering -- with the owner's own
# object, not a copy the leaf kept, because the views the record binds its
# properties to are these very functions.
_FORWARDED_MODULES = MappingProxyType({
    "orchestrator._trajectory_constants": (_CONSTANTS, _CONSTANT_NAMES),
    "orchestrator._trajectory_record_values": (_COERCION, _COERCION_NAMES),
    "orchestrator._trajectory_view_models": (_MODELS, _MODEL_NAMES),
    "orchestrator._trajectory_run_model": (_RUNS, ("TrajectoryRun",)),
    "orchestrator._trajectory_run_views": (_USAGE, _USAGE_NAMES),
    "orchestrator._trajectory_run_timeline": (_TIMELINE, _TIMELINE_NAMES),
    "orchestrator._trajectory_record_parse": (_PARSING, _PARSE_NAMES),
    "orchestrator._trajectory_file_read": (_READING, _READ_NAMES),
})

# What the record facade publishes off these owners. It is the module the
# reader re-exports from and the one the views name as their own, so this pins
# the far end of the chain: whichever site a caller imported a record name
# through, the object it holds is the one the page renders. Its `parse_record`
# is absent on purpose: the facade binds the parse against the historical
# `obj` / `seq` call shape rather than republishing the owner's function.
_FORWARDED_FACADE = (
    ("RunUsageView", _MODELS),
    ("TimelineEntry", _MODELS),
    ("TIMELINE_OUTPUT", _CONSTANTS),
    ("TIMELINE_PROMPT", _CONSTANTS),
    ("TRAJECTORY_EVENT", _CONSTANTS),
    ("TrajectoryRun", _RUNS),
    ("TrajectoryStepView", _MODELS),
    ("TurnUsageView", _MODELS),
    ("UNCONFIGURED_LOG_MESSAGE", _CONSTANTS),
)

# Each frozen view, and the record composed from them, reached on its owner.
_STAMPED_TYPES = (
    (_MODELS, "RunUsageView"),
    (_MODELS, "TimelineEntry"),
    (_MODELS, "TrajectoryStepView"),
    (_MODELS, "TurnUsageView"),
    (_RUNS, "TrajectoryRun"),
)


class ForwardedFlatModuleTest(unittest.TestCase):
    """Every name the flat trajectory modules publish is the owner's own."""

    def test_each_name_resolves_to_the_owner(self) -> None:
        for module_name, forwarded in _FORWARDED_MODULES.items():
            owner_name, names = forwarded
            for name in names:
                with self.subTest(module=module_name, name=name):
                    self.assertIs(
                        getattr(import_module(module_name), name),
                        getattr(import_module(owner_name), name),
                    )

    def test_no_flat_module_defines_one_itself(self) -> None:
        # What keeps the forwarding thin: a module that defined a name of its
        # own would be a second implementation the check above cannot see,
        # because it only compares the names the module was asked for.
        for module_name in _FORWARDED_MODULES:
            defined = tuple(
                name
                for name, member in import_module(module_name).__dict__.items()
                if getattr(member, "__module__", None) == module_name
            )
            with self.subTest(module=module_name):
                self.assertEqual(defined, ())


class ForwardedRecordFacadeTest(unittest.TestCase):
    """The record facade binds the owners' objects, not copies of them."""

    def test_each_name_resolves_to_the_owner(self) -> None:
        facade = import_module(_ORIGIN_MODULE)
        for name, owner_name in _FORWARDED_FACADE:
            with self.subTest(name=name):
                self.assertIs(
                    getattr(facade, name), getattr(import_module(owner_name), name),
                )


class HistoricalIdentityTest(unittest.TestCase):
    """The moved types keep reporting the site they were published from."""

    def test_each_type_reports_the_record_module(self) -> None:
        for owner_name, name in _STAMPED_TYPES:
            with self.subTest(name=name):
                stamped = getattr(import_module(owner_name), name)
                self.assertEqual(stamped.__module__, _ORIGIN_MODULE)


if __name__ == "__main__":
    unittest.main()
