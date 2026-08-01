# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What the flat trajectory modules still answer for, and with whose objects."""
from __future__ import annotations

import pickle
import unittest
from importlib import import_module
from types import MappingProxyType


_PACKAGE = "orchestrator.observability.trajectory_viewer"

_COERCION = f"{_PACKAGE}.coercion"

_CONSTANTS = f"{_PACKAGE}.constants"

_CSS = f"{_PACKAGE}.css"

_FILTER_MODELS = f"{_PACKAGE}.filter_models"

_FILTER_VALUES = f"{_PACKAGE}.filter_values"

_FILTERING = f"{_PACKAGE}.filtering"

_MODELS = f"{_PACKAGE}.models"

_PARSING = f"{_PACKAGE}.parsing"

_READING = f"{_PACKAGE}.reading"

_RUN_HTML = f"{_PACKAGE}.run_html"

_RUNS = f"{_PACKAGE}.runs"

_SUMMARY_HTML = f"{_PACKAGE}.summary_html"

_TIMELINE = f"{_PACKAGE}.timeline_views"

_USAGE = f"{_PACKAGE}.usage_views"

# The historical import site the four frozen views and the record report as
# their module. It is the site their API is documented at, so a repr, a pickle,
# and a reader following `__module__` all still land there.
_ORIGIN_MODULE = "orchestrator._trajectory_records"

# The same for the KPI tile: the page reaches every builder through this one
# HTML surface, so that is where the shape is published from.
_HTML_ORIGIN_MODULE = "orchestrator._trajectory_dashboard_html"

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

# The two shapes the filter leaf published are the internal pair: the keywords
# a call may be driven by and the normalized form a match reads. The two a
# caller holds were published from the reader facade instead, so they are
# pinned there rather than here.
_FILTER_MODEL_NAMES = (
    "RunFilterOptionFields",
    "RunFilters",
)

_FILTER_VALUE_NAMES = (
    "distinct_sorted",
    "matches_query",
    "normalize_filter_query",
    "normalize_filter_values",
)

_FILTER_MATCH_NAMES = (
    "matches_dimension_filters",
    "matches_run_filters",
    "matches_scalar_filters",
    "normalize_run_filters",
    "resolve_run_filter_options",
)

# The flat modules a historical caller reaches the record and filter sides
# through, and the owner each one's names resolve to. A name reached through one
# of these is still a name it reached, so it has to keep answering -- with the
# owner's own object, not a copy the leaf kept, because the views the record
# binds its properties to are these very functions.
_FORWARDED_MODULES = MappingProxyType({
    "orchestrator._trajectory_constants": (_CONSTANTS, _CONSTANT_NAMES),
    "orchestrator._trajectory_record_values": (_COERCION, _COERCION_NAMES),
    "orchestrator._trajectory_view_models": (_MODELS, _MODEL_NAMES),
    "orchestrator._trajectory_run_model": (_RUNS, ("TrajectoryRun",)),
    "orchestrator._trajectory_run_views": (_USAGE, _USAGE_NAMES),
    "orchestrator._trajectory_run_timeline": (_TIMELINE, _TIMELINE_NAMES),
    "orchestrator._trajectory_record_parse": (_PARSING, _PARSE_NAMES),
    "orchestrator._trajectory_file_read": (_READING, _READ_NAMES),
    "orchestrator._trajectory_filter_models": (_FILTER_MODELS, _FILTER_MODEL_NAMES),
    "orchestrator._trajectory_filter_values": (_FILTER_VALUES, _FILTER_VALUE_NAMES),
    "orchestrator._trajectory_filter_match": (_FILTERING, _FILTER_MATCH_NAMES),
})

# The rendering leaves, declared as pairs because most of what they publish is
# respelled: each builder is private to the leaf a caller reached it through,
# while the owner defining it publishes it under this package's own naming.
# What a caller holds is still the owner's one object -- the spelling is all
# that differs, and the pair is what says so.
_RESPELLED_MODULES = MappingProxyType({
    "orchestrator._trajectory_dashboard_style": (
        _CSS, (("EXTRA_CSS", "EXTRA_CSS"),),
    ),
    "orchestrator._trajectory_dashboard_summary_html": (_SUMMARY_HTML, (
        ("_TrajectoryKpi", "_TrajectoryKpi"),
        ("_card_header_html", "card_header_html"),
        ("_fmt_cost_usd", "fmt_cost_usd"),
        ("_kpi_strip_html", "kpi_strip_html"),
        ("_topbar_html", "topbar_html"),
        ("_trajectory_kpi_html", "trajectory_kpi_html"),
        ("_trajectory_kpis", "trajectory_kpis"),
    )),
    "orchestrator._trajectory_dashboard_run_html": (_RUN_HTML, (
        ("FIXTURE_LABEL_PREFIX", "FIXTURE_LABEL_PREFIX"),
        ("REPO_LABEL", "REPO_LABEL"),
        ("_labeled_chips_html", "labeled_chips_html"),
        ("_meta_html", "meta_html"),
        ("_run_picker_label", "run_picker_label"),
        ("_run_table_row_html", "run_table_row_html"),
        ("_runs_table_html", "runs_table_html"),
    )),
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

# Each frozen view, the record composed from them, and the KPI tile: reached on
# the owner that defines it, and paired with the site it is published from.
# Each is named here under the spelling that site answers to, which is the
# spelling its owner defines it as -- the tile keeps the leading underscore the
# HTML surface published it with for that reason.
_STAMPED_TYPES = (
    (_MODELS, "RunUsageView", _ORIGIN_MODULE),
    (_MODELS, "TimelineEntry", _ORIGIN_MODULE),
    (_MODELS, "TrajectoryStepView", _ORIGIN_MODULE),
    (_MODELS, "TurnUsageView", _ORIGIN_MODULE),
    (_RUNS, "TrajectoryRun", _ORIGIN_MODULE),
    (_SUMMARY_HTML, "_TrajectoryKpi", _HTML_ORIGIN_MODULE),
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
        for module_name in (*_FORWARDED_MODULES, *_RESPELLED_MODULES):
            defined = tuple(
                name
                for name, member in import_module(module_name).__dict__.items()
                if getattr(member, "__module__", None) == module_name
            )
            with self.subTest(module=module_name):
                self.assertEqual(defined, ())


class RespelledRenderingLeafTest(unittest.TestCase):
    """Each rendering leaf still answers under its own historical spelling."""

    def test_each_name_resolves_to_the_owner(self) -> None:
        for module_name, (owner_name, pairs) in _RESPELLED_MODULES.items():
            for published, owned in pairs:
                with self.subTest(module=module_name, name=published):
                    self.assertIs(
                        getattr(import_module(module_name), published),
                        getattr(import_module(owner_name), owned),
                    )


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

    def test_each_type_reports_its_published_site(self) -> None:
        for owner_name, name, origin in _STAMPED_TYPES:
            with self.subTest(name=name):
                stamped = getattr(import_module(owner_name), name)
                self.assertEqual(stamped.__module__, origin)

    def test_each_stamp_resolves_the_way_pickle_does(self) -> None:
        # `pickle` resolves a class through `__module__` and `__qualname__`
        # together, so a stamp naming a site that publishes the shape under
        # some other spelling is a `PicklingError` rather than a cosmetic
        # difference. This is that lookup, done the way pickle does it.
        for owner_name, name, _ in _STAMPED_TYPES:
            stamped = getattr(import_module(owner_name), name)
            with self.subTest(name=name):
                self.assertIs(
                    getattr(
                        import_module(stamped.__module__), stamped.__qualname__,
                    ),
                    stamped,
                )

    def test_the_kpi_tile_round_trips_through_pickle(self) -> None:
        tile = import_module(_SUMMARY_HTML)._TrajectoryKpi("Runs", "3")
        self.assertEqual(pickle.loads(pickle.dumps(tile)), tile)


if __name__ == "__main__":
    unittest.main()
