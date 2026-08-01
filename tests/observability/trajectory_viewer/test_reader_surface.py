# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What the reader facade publishes, and the call shapes it answers on.

`orchestrator.trajectory_reader` is the one import site the page and every
historical caller reach the whole file-backed read model through. It defines
none of it: the record half comes off the private `_trajectory_records` leaf,
where a caller's analytics world is bound, and the filter and summary half off
the owners under `orchestrator/observability/trajectory_viewer/`. So what is
pinned here is that every name it publishes is the object its owner defines,
that the shapes a caller holds still report the site they were published from,
and that each of them still reads back the same way to `inspect` and to
`typing.get_type_hints` -- which is the half a move can break silently, because
an annotation is resolved in the globals of whichever module the object names
and every one of them is text under `from __future__ import annotations`.
"""
from __future__ import annotations

import inspect
import unittest
from importlib import import_module
from types import MappingProxyType
from typing import get_args, get_type_hints

from orchestrator import trajectory_reader as reader
from orchestrator.observability.trajectory_viewer import (
    filter_models,
    filter_values,
    filtering,
    summaries,
)
from tests.observability.trajectory_viewer.trajectory_viewer_test_support import (
    ISSUE,
    record,
)


# Resolved after the reader rather than imported above it: importing the reader
# rebuilds the record facade against the current analytics world, so a module
# object bound before it would be a discarded one every check below compares
# against.
_records = import_module("orchestrator._trajectory_records")

_READER_MODULE = "orchestrator.trajectory_reader"

_RECORD_MODULE = "orchestrator._trajectory_records"

# The whole record API, reached on the facade and answered by the leaf.
_RECORD_SURFACE = (
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
)

_FILTER_OPTIONS = "FilterOptions"

_RUN_FILTER_OPTIONS = "RunFilterOptions"

_TRAJECTORY_SUMMARY = "TrajectorySummary"

_RETURN = "return"

# The filter and summary API, and the owner each name is defined on.
_FILTER_SURFACE = (
    (_FILTER_OPTIONS, filter_models),
    (_RUN_FILTER_OPTIONS, filter_models),
    (_TRAJECTORY_SUMMARY, summaries),
    ("filter_options", filter_values),
    ("filter_runs", filtering),
    ("summarize", summaries),
)

# The shapes a caller holds, which report this module however far the owner
# defining them has moved -- the site a repr, a pickle, and a reader following
# `__module__` all still land on.
_STAMPED_FILTER_MODELS = (
    _FILTER_OPTIONS,
    _RUN_FILTER_OPTIONS,
    _TRAJECTORY_SUMMARY,
)

_SEQUENCE = 3

# The call shape each published name answers on, spelled out rather than
# derived: `inspect.signature` reports an annotation verbatim, so this is the
# text a caller reads off the reader and a type checker resolves against, and
# nothing about which module now defines the object may change a character of
# it.
_SIGNATURES = MappingProxyType({
    "filter_options": "(runs: 'Sequence[TrajectoryRun]') -> 'FilterOptions'",
    "filter_runs": (
        "(runs: 'Sequence[TrajectoryRun]', "
        "options: 'Optional[RunFilterOptions]' = None, "
        "**option_fields: 'Unpack[filter_models.RunFilterOptionFields]')"
        " -> 'list[TrajectoryRun]'"
    ),
    "summarize": "(runs: 'Sequence[TrajectoryRun]') -> 'TrajectorySummary'",
    _FILTER_OPTIONS: (
        "(repos: 'tuple[str, ...]' = (), "
        "backends: 'tuple[str, ...]' = (), "
        "agent_roles: 'tuple[str, ...]' = (), "
        "stages: 'tuple[str, ...]' = ()) -> None"
    ),
    _RUN_FILTER_OPTIONS: (
        "(repo: 'Optional[str]' = None, "
        "backends: 'Optional[Sequence[str]]' = None, "
        "agent_roles: 'Optional[Sequence[str]]' = None, "
        "stages: 'Optional[Sequence[str]]' = None, "
        "issue: 'Optional[int]' = None, "
        "query: 'Optional[str]' = None, "
        "exclude_fixtures: 'bool' = False) -> None"
    ),
    _TRAJECTORY_SUMMARY: (
        "(total_runs: 'int' = 0, "
        "distinct_issues: 'int' = 0, "
        "distinct_repos: 'int' = 0, "
        "total_tool_calls: 'int' = 0, "
        "truncated_runs: 'int' = 0, "
        "total_cost_usd: 'float' = <factory>) -> None"
    ),
})

# What each of those annotations resolves to, named so the check fails on the
# annotation that stopped resolving rather than on a bare exception.
_RESOLVED_HINTS = MappingProxyType({
    "filter_options": ("runs", _RETURN),
    "filter_runs": ("runs", "options", "option_fields", _RETURN),
    "summarize": ("runs", _RETURN),
    _FILTER_OPTIONS: ("repos", "backends", "agent_roles", "stages"),
    _RUN_FILTER_OPTIONS: (
        "repo",
        "backends",
        "agent_roles",
        "stages",
        "issue",
        "query",
        "exclude_fixtures",
    ),
    _TRAJECTORY_SUMMARY: (
        "total_runs",
        "distinct_issues",
        "distinct_repos",
        "total_tool_calls",
        "truncated_runs",
        "total_cost_usd",
    ),
})


class RecordSurfaceTest(unittest.TestCase):
    """The record half is the leaf's own objects, under the leaf's own name."""

    def test_each_name_resolves_to_the_leaf(self) -> None:
        for name in _RECORD_SURFACE:
            with self.subTest(name=name):
                self.assertIs(getattr(reader, name), getattr(_records, name))

    def test_read_symbols_report_the_record_module(self) -> None:
        # One module name for the whole record API, whether the leaf defines
        # the symbol itself or a viewer owner does and stamps it with the site
        # it is published from -- which is where a repr or a reader following
        # `__module__` has always landed.
        for symbol in (
            reader.TrajectoryRun,
            reader.TrajectoryStepView,
            reader.parse_record,
            reader.read_trajectories,
            reader.resolve_log_path,
        ):
            with self.subTest(symbol=symbol.__name__):
                self.assertEqual(symbol.__module__, _RECORD_MODULE)


class FilterSurfaceTest(unittest.TestCase):
    """The filter and summary half is the owners' own objects."""

    def test_each_name_resolves_to_its_owner(self) -> None:
        for name, owner in _FILTER_SURFACE:
            with self.subTest(name=name):
                self.assertIs(getattr(reader, name), getattr(owner, name))

    def test_held_shapes_report_this_module(self) -> None:
        for name in _STAMPED_FILTER_MODELS:
            with self.subTest(name=name):
                self.assertEqual(getattr(reader, name).__module__, _READER_MODULE)


class IntrospectionTest(unittest.TestCase):
    """Every published name still reads back to `inspect` and to `typing`."""

    def test_each_signature_reads_back_verbatim(self) -> None:
        for name, signature in _SIGNATURES.items():
            with self.subTest(name=name):
                published = str(inspect.signature(getattr(reader, name)))
                self.assertEqual(published, signature)

    def test_every_annotation_resolves(self) -> None:
        # A name an owner binds only for a type checker resolves to nothing
        # here, so this is what catches an annotation the reader publishes but
        # no module the caller can reach spells out.
        for name, hinted in _RESOLVED_HINTS.items():
            with self.subTest(name=name):
                resolved = get_type_hints(getattr(reader, name))
                self.assertEqual(tuple(resolved), hinted)

    def test_resolved_types_are_the_published_objects(self) -> None:
        # Resolving is not enough: what an annotation resolves to has to be
        # the very class a caller holds off this module, not a second one
        # under the same name.
        filter_hints = get_type_hints(reader.filter_runs)
        self.assertEqual(get_args(filter_hints[_RETURN]), (reader.TrajectoryRun,))
        self.assertIn(reader.RunFilterOptions, get_args(filter_hints["options"]))
        self.assertEqual(
            get_args(filter_hints["option_fields"]),
            (filter_models.RunFilterOptionFields,),
        )
        self.assertIs(
            get_type_hints(reader.summarize)[_RETURN], reader.TrajectorySummary,
        )


class ParseCallShapeTest(unittest.TestCase):
    """`parse_record` binds the record as `obj` and the line count as `seq`.

    The owner under `observability/trajectory_viewer/` narrows a record
    through its own `sequence` keyword; this is the site the historical
    spelling is bound at, and every caller parsing a line of its own drives it
    by name, so both halves have to stay bindable rather than positional-only.
    """

    def test_the_record_may_be_passed_by_name(self) -> None:
        run = reader.parse_record(obj=record(), seq=_SEQUENCE)
        assert run is not None
        self.assertEqual((run.issue, run.seq), (ISSUE, _SEQUENCE))


if __name__ == "__main__":
    unittest.main()
