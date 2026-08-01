# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What the flat trajectory modules still answer for, and with whose objects."""
from __future__ import annotations

import pickle
import unittest
from importlib import import_module
from types import MappingProxyType
from typing import Sequence, get_type_hints
from unittest.mock import patch


_PACKAGE = "orchestrator.observability.trajectory_viewer"

_COERCION = f"{_PACKAGE}.coercion"

_CONSTANTS = f"{_PACKAGE}.constants"

_CONTROLS = f"{_PACKAGE}.controls"

_CSS = f"{_PACKAGE}.css"

_FILTER_MODELS = f"{_PACKAGE}.filter_models"

_FILTER_VALUES = f"{_PACKAGE}.filter_values"

_FILTERING = f"{_PACKAGE}.filtering"

_MODELS = f"{_PACKAGE}.models"

_PAGE_MODELS = f"{_PACKAGE}.page_models"

_PAGE_SETUP = f"{_PACKAGE}.page_setup"

_PARSING = f"{_PACKAGE}.parsing"

_PICKER = f"{_PACKAGE}.picker"

_READING = f"{_PACKAGE}.reading"

_RUN_HTML = f"{_PACKAGE}.run_html"

_RUN_RENDER = f"{_PACKAGE}.run_render"

_RUNS = f"{_PACKAGE}.runs"

_SUMMARY_HTML = f"{_PACKAGE}.summary_html"

_TIMELINE = f"{_PACKAGE}.timeline_views"

_TIMELINE_HTML = f"{_PACKAGE}.timeline_html"

_USAGE = f"{_PACKAGE}.usage_views"

_USAGE_HTML = f"{_PACKAGE}.usage_html"

# The historical import site the four frozen views and the record report as
# their module. It is the site their API is documented at, so a repr, a pickle,
# and a reader following `__module__` all still land there.
_ORIGIN_MODULE = "orchestrator._trajectory_records"

# The same for the KPI tile: the page reaches every builder through this one
# HTML surface, so that is where the shape is published from.
_HTML_ORIGIN_MODULE = "orchestrator._trajectory_dashboard_html"

# And for the two page shapes, which the page reaches through this one leaf.
_PAGE_ORIGIN_MODULE = "orchestrator._trajectory_dashboard_models"

# The leaf that hands the page owner a world, rather than forwarding to it,
# and the two entries on it that need one.
_PAGE_LEAF = "orchestrator._trajectory_dashboard_page"

_STOP_ENTRY = "_stop_if_unconfigured"

_LOAD_ENTRY = "_load_trajectory_page"

_ANALYTICS_MODULE = "orchestrator.analytics"

_KPI_TILE = "_TrajectoryKpi"

_PAGE_STATE = "_TrajectoryPage"

_FILTER_STATE = "_TrajectoryFilters"

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
        (_KPI_TILE, _KPI_TILE),
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
    "orchestrator._trajectory_dashboard_usage_html": (_USAGE_HTML, (
        ("USAGE_SEPARATOR", "USAGE_SEPARATOR"),
        ("_run_usage_chips", "run_usage_chips"),
        ("_run_usage_html", "run_usage_html"),
        ("_run_usage_note", "run_usage_note"),
        ("_turn_usage_html", "turn_usage_html"),
        ("_usage_chip", "usage_chip"),
    )),
    "orchestrator._trajectory_dashboard_timeline_html": (_TIMELINE_HTML, (
        ("BADGE_BY_KIND", "BADGE_BY_KIND"),
        ("TimelineUsagePair", "TimelineUsagePair"),
        ("_timeline_entry_html", "timeline_entry_html"),
        ("_timeline_with_usage", "timeline_with_usage"),
    )),
    "orchestrator._trajectory_dashboard_filters": (_CONTROLS, (
        ("_filter_page_runs", "filter_page_runs"),
        ("_render_categorical_filters", "render_categorical_filters"),
        ("_render_text_filters", "render_text_filters"),
        ("_render_trajectory_sidebar", "render_trajectory_sidebar"),
    )),
    "orchestrator._trajectory_dashboard_run_render": (_RUN_RENDER, (
        ("_render_run", "render_run"),
        ("_render_run_card", "render_run_card"),
        ("_render_run_notices", "render_run_notices"),
        ("_render_run_usage_and_chips", "render_run_usage_and_chips"),
        ("_render_system_prompt", "render_system_prompt"),
        ("_render_timeline", "render_timeline"),
        ("_render_timeline_entry", "render_timeline_entry"),
    )),
    "orchestrator._trajectory_dashboard_picker": (_PICKER, (
        ("RUN_TABLE_LIMIT", "RUN_TABLE_LIMIT"),
        ("_fixture_caption", "fixture_caption"),
        ("_pick_issue", "pick_issue"),
        ("_pick_repo", "pick_repo"),
        ("_pick_run", "pick_run"),
        ("_render_no_trajectories", "render_no_trajectories"),
        ("_render_run_list", "render_run_list"),
        ("_render_run_picker", "render_run_picker"),
    )),
})

# The one surface the page composes those owners into. Which builder it binds
# where is pinned beside the page; what belongs here is only that it, too, is
# down to the one shape it is the published site of.
_COMPOSED_SURFACE = "orchestrator._trajectory_dashboard_html"

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

# What the page-setup leaf forwards rather than binds a world for: the two
# empty-state messages, which no read is behind, and the chrome, which reads
# nothing but the two stylesheets.
_PAGE_LEAF_NAMES = (
    ("EMPTY_FILTER_MESSAGE", "EMPTY_FILTER_MESSAGE"),
    ("NO_TRAJECTORIES_MESSAGE", "NO_TRAJECTORIES_MESSAGE"),
    ("_configure_page", "configure_page"),
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
    (_PAGE_MODELS, _FILTER_STATE, _PAGE_ORIGIN_MODULE),
    (_PAGE_MODELS, _PAGE_STATE, _PAGE_ORIGIN_MODULE),
    (_RUNS, "TrajectoryRun", _ORIGIN_MODULE),
    (_SUMMARY_HTML, _KPI_TILE, _HTML_ORIGIN_MODULE),
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


class ComposedSurfaceTest(unittest.TestCase):
    """The surface every builder is reached through defines none of them."""

    def test_only_the_stamped_tile_reports_it(self) -> None:
        # Anything else naming this module would be a builder the owners under
        # this package do not answer for. The KPI tile names it by
        # construction: the owner that defines the shape stamps it with the
        # site it is published from, which is the lookup pinned below.
        surface = import_module(_COMPOSED_SURFACE)
        reported = tuple(
            name
            for name, member in surface.__dict__.items()
            if getattr(member, "__module__", None) == _COMPOSED_SURFACE
        )
        self.assertEqual(reported, (_KPI_TILE,))


class StampedPageStateLeafTest(unittest.TestCase):
    """The page-state site answers for its two shapes and nothing besides."""

    def test_only_the_stamped_shapes_report_it(self) -> None:
        leaf = import_module(_PAGE_ORIGIN_MODULE)
        reported = tuple(sorted(
            name
            for name, member in leaf.__dict__.items()
            if getattr(member, "__module__", None) == _PAGE_ORIGIN_MODULE
        ))
        self.assertEqual(reported, (_FILTER_STATE, _PAGE_STATE))

    def test_each_shape_resolves_its_hints_there(self) -> None:
        # A stamped class resolves its annotations in the stamped module's own
        # globals, which is why that site imports the typing vocabulary and the
        # two record shapes they are spelled in and uses them for nothing else.
        # Dropping one of those imports is a `NameError` here, not a tidy-up --
        # and so is reading the hints back without that site loaded at all,
        # which is why it is imported first rather than assumed present.
        import_module(_PAGE_ORIGIN_MODULE)
        owner = import_module(_PAGE_MODELS)
        resolved = {
            name: get_type_hints(getattr(owner, name))
            for name in (_FILTER_STATE, _PAGE_STATE)
        }
        self.assertIs(resolved[_FILTER_STATE]["hide_fixtures"], bool)
        self.assertEqual(
            resolved[_PAGE_STATE]["runs"],
            Sequence[import_module(_RUNS).TrajectoryRun],
        )
        self.assertIs(
            resolved[_PAGE_STATE]["options"],
            import_module(_FILTER_MODELS).FilterOptions,
        )


class PageWorldLeafTest(unittest.TestCase):
    """The page setup's world is bound at its leaf, not inside the owner."""

    def test_each_entry_hands_over_the_package(self) -> None:
        # The owner answers on the settings holder it is handed, so the leaf is
        # what decides *which* analytics instance a page resolves its file on:
        # the one it captured at its own import, which is what a caller patches.
        analytics = import_module(_ANALYTICS_MODULE)
        streamlit = object()
        for entry, owned, passed in (
            (_STOP_ENTRY, "stop_if_unconfigured", (streamlit,)),
            (_LOAD_ENTRY, "load_trajectory_page", ()),
        ):
            with self.subTest(entry=entry):
                self.assertEqual(
                    self._handed_over(entry, owned, passed),
                    (*passed, analytics),
                )

    def test_the_worldless_names_are_the_owner_s(self) -> None:
        leaf = import_module(_PAGE_LEAF)
        owner = import_module(_PAGE_SETUP)
        for published, owned in _PAGE_LEAF_NAMES:
            with self.subTest(name=published):
                self.assertIs(getattr(leaf, published), getattr(owner, owned))

    def _handed_over(self, entry: str, owned: str, passed: tuple) -> tuple:
        """The arguments the leaf's entry reached its owner with."""
        with patch.object(import_module(_PAGE_SETUP), owned) as bound:
            getattr(import_module(_PAGE_LEAF), entry)(*passed)
            return bound.call_args.args


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
