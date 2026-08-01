# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Inventory, surface, and layering checks for the trajectory-viewer owners."""
from __future__ import annotations

import unittest
from importlib import import_module
from pathlib import Path
from types import MappingProxyType

from orchestrator.observability import trajectory_viewer as _package
from tests.observability.observability_test_support import (
    _imported_orchestrator_modules,
)


_PACKAGE = "orchestrator.observability.trajectory_viewer"

_COERCION_OWNER = "coercion"

_CONSTANTS_OWNER = "constants"

_CSS_OWNER = "css"

_FILTER_MODELS_OWNER = "filter_models"

_FILTER_VALUES_OWNER = "filter_values"

_FILTERING_OWNER = "filtering"

_LOG_PATHS_OWNER = "log_paths"

_MODELS_OWNER = "models"

_PARSING_OWNER = "parsing"

_READING_OWNER = "reading"

_RUN_HTML_OWNER = "run_html"

_RUNS_OWNER = "runs"

_SUMMARIES_OWNER = "summaries"

_SUMMARY_HTML_OWNER = "summary_html"

_TIMELINE_HTML_OWNER = "timeline_html"

_TIMELINE_OWNER = "timeline_views"

_USAGE_HTML_OWNER = "usage_html"

_USAGE_OWNER = "usage_views"

# The declared inventory. A new owner is a deliberate edit here and a paragraph
# in the module map, which is what the inventory check compares the directory
# against.
_OWNERS = (
    _COERCION_OWNER,
    _CONSTANTS_OWNER,
    _CSS_OWNER,
    _FILTER_MODELS_OWNER,
    _FILTER_VALUES_OWNER,
    _FILTERING_OWNER,
    _LOG_PATHS_OWNER,
    _MODELS_OWNER,
    _PARSING_OWNER,
    _READING_OWNER,
    _RUN_HTML_OWNER,
    _RUNS_OWNER,
    _SUMMARIES_OWNER,
    _SUMMARY_HTML_OWNER,
    _TIMELINE_HTML_OWNER,
    _TIMELINE_OWNER,
    _USAGE_HTML_OWNER,
    _USAGE_OWNER,
)

# What each owner answers for, declared rather than discovered so a new public
# name is a deliberate edit: a second way to narrow a field, assemble a
# timeline, or total a run's tokens is a second answer a page and a filter
# could disagree over. Some owners report less than they hold because the check
# reads `__module__`, which only a class or a function carries -- `constants` is
# seven strings, `css` one, `usage_html`'s separator another, and
# `timeline_html`'s badge vocabulary a mapping proxy beside a type alias -- and
# because a shape published under a historical import site is stamped with it:
# the record on `runs`, the four frozen views on `models`, the two request
# shapes a caller holds on `filter_models`, the summary on `summaries`, and the
# KPI tile on `summary_html`. That stamp is the identity `test_forwarding` and
# the reader surface check pin; what is left visible here is everything else.
_SURFACES = MappingProxyType({
    _COERCION_OWNER: (
        "as_list",
        "coerce_float",
        "coerce_int",
        "coerce_str",
        "coerce_str_tuple",
    ),
    _CONSTANTS_OWNER: (),
    _CSS_OWNER: (),
    _FILTER_MODELS_OWNER: (
        "RunFilterOptionFields",
        "RunFilters",
    ),
    _FILTER_VALUES_OWNER: (
        "distinct_sorted",
        "filter_options",
        "matches_query",
        "normalize_filter_query",
        "normalize_filter_values",
    ),
    _FILTERING_OWNER: (
        "filter_runs",
        "matches_dimension_filters",
        "matches_run_filters",
        "matches_scalar_filters",
        "normalize_run_filters",
        "resolve_run_filter_options",
    ),
    _LOG_PATHS_OWNER: (
        "configured_path",
        "resolve_path",
        "unconfigured_message",
    ),
    _MODELS_OWNER: (
        "public_entry_content",
        "public_step_content",
    ),
    _PARSING_OWNER: (
        "parse_record",
        "parse_run_usage",
        "parse_step",
        "parse_turn",
    ),
    _READING_OWNER: (
        "parse_trajectory_line",
        "read_trajectories",
        "read_trajectory_file",
        "run_sort_key",
    ),
    _RUN_HTML_OWNER: (
        "labeled_chips_html",
        "meta_html",
        "run_picker_label",
        "run_table_row_html",
        "runs_table_html",
    ),
    _RUNS_OWNER: (),
    _SUMMARIES_OWNER: ("summarize",),
    _SUMMARY_HTML_OWNER: (
        "card_header_html",
        "fmt_cost_usd",
        "kpi_strip_html",
        "topbar_html",
        "trajectory_kpi_html",
        "trajectory_kpis",
    ),
    _TIMELINE_HTML_OWNER: (
        "timeline_entry_html",
        "timeline_with_usage",
    ),
    _TIMELINE_OWNER: (
        "detail_label",
        "is_fixture",
        "label",
        "timeline",
        "turn_map",
    ),
    _USAGE_HTML_OWNER: (
        "run_usage_chips",
        "run_usage_html",
        "run_usage_note",
        "turn_usage_html",
        "usage_chip",
    ),
    _USAGE_OWNER: (
        "cost_source",
        "cost_usd",
        "model",
        "step_count",
        "tool_calls",
        "total_tokens",
        "usage_for_turn",
    ),
})

# The whole chain an import of each owner plants, declared per owner because
# the direction is the point: the two leaves reach nothing, the models name the
# vocabulary a kind is compared against, the two view owners name the models
# they build and return, and only the record names those views. Reaching the
# other way -- a view importing the record its functions are bound onto -- is
# the cycle this rejects, and is why the views name the record at type-check
# time, where no import happens at all: the record is absent from every chain
# but its own and the parse that builds it. The parse sits above the whole
# package for that reason, and nothing here names it back; the read that drives
# it sits above the parse for the same one. `log_paths` is off to the side of
# both: naming the file a read opens costs the vocabulary its banner is spelled
# in and nothing else here. The three filter and summary owners that answer over
# runs name the record at import rather than only at type-check time: their
# annotations are a published surface, so `typing.get_type_hints` on the reads a
# page calls has to resolve them, and a name bound only for a checker resolves
# to nothing at runtime. `filter_models` is the one that names no run at all,
# and it stays the shortest chain here. The rendering owners sit at the far end
# of the same direction: each names what it draws -- the record for `run_html`,
# `timeline_html`, and `usage_html`, the summary for `summary_html` -- and
# nothing names them back, while `css` names nothing in the package at all.
# `usage_html` is the one that also names a sibling renderer: the money on a run
# row and on a turn strip is the exact-cents format the KPI tile is drawn with,
# so it reaches `summary_html` for it rather than spelling a second one.
_PLANTED = MappingProxyType({
    _COERCION_OWNER: (),
    _CONSTANTS_OWNER: (),
    _CSS_OWNER: (),
    _FILTER_MODELS_OWNER: (),
    _FILTER_VALUES_OWNER: (
        _CONSTANTS_OWNER,
        _FILTER_MODELS_OWNER,
        _MODELS_OWNER,
        _RUNS_OWNER,
        _TIMELINE_OWNER,
        _USAGE_OWNER,
    ),
    _FILTERING_OWNER: (
        _CONSTANTS_OWNER,
        _FILTER_MODELS_OWNER,
        _FILTER_VALUES_OWNER,
        _MODELS_OWNER,
        _RUNS_OWNER,
        _TIMELINE_OWNER,
        _USAGE_OWNER,
    ),
    _LOG_PATHS_OWNER: (_CONSTANTS_OWNER,),
    _MODELS_OWNER: (_CONSTANTS_OWNER,),
    _PARSING_OWNER: (
        _COERCION_OWNER,
        _CONSTANTS_OWNER,
        _MODELS_OWNER,
        _RUNS_OWNER,
        _TIMELINE_OWNER,
        _USAGE_OWNER,
    ),
    _READING_OWNER: (
        _COERCION_OWNER,
        _CONSTANTS_OWNER,
        _MODELS_OWNER,
        _PARSING_OWNER,
        _RUNS_OWNER,
        _TIMELINE_OWNER,
        _USAGE_OWNER,
    ),
    _RUN_HTML_OWNER: (
        _CONSTANTS_OWNER,
        _MODELS_OWNER,
        _RUNS_OWNER,
        _TIMELINE_OWNER,
        _USAGE_OWNER,
    ),
    _RUNS_OWNER: (
        _CONSTANTS_OWNER,
        _MODELS_OWNER,
        _TIMELINE_OWNER,
        _USAGE_OWNER,
    ),
    _SUMMARIES_OWNER: (
        _CONSTANTS_OWNER,
        _MODELS_OWNER,
        _RUNS_OWNER,
        _TIMELINE_OWNER,
        _USAGE_OWNER,
    ),
    _SUMMARY_HTML_OWNER: (
        _CONSTANTS_OWNER,
        _MODELS_OWNER,
        _RUNS_OWNER,
        _SUMMARIES_OWNER,
        _TIMELINE_OWNER,
        _USAGE_OWNER,
    ),
    _TIMELINE_HTML_OWNER: (
        _CONSTANTS_OWNER,
        _MODELS_OWNER,
        _RUNS_OWNER,
        _TIMELINE_OWNER,
        _USAGE_OWNER,
    ),
    _TIMELINE_OWNER: (_CONSTANTS_OWNER, _MODELS_OWNER),
    _USAGE_HTML_OWNER: (
        _CONSTANTS_OWNER,
        _MODELS_OWNER,
        _RUNS_OWNER,
        _SUMMARIES_OWNER,
        _SUMMARY_HTML_OWNER,
        _TIMELINE_OWNER,
        _USAGE_OWNER,
    ),
    _USAGE_OWNER: (_CONSTANTS_OWNER, _MODELS_OWNER),
})

# What an import of any owner here costs before it names anything: the root
# package and the chain down to this one.
_ALWAYS_PLANTED = frozenset((
    "orchestrator",
    "orchestrator._package_exports",
    "orchestrator.observability",
    _PACKAGE,
))

# The chains an owner here may reach for, declared per owner. `log_paths` names
# the analytics configuration owner, which is where the knob naming the file
# this page reads is parsed, so the viewer answers with the sink's own setting
# rather than a second parse of the same variable -- and what it names is the
# settings *view*, not the analytics package the parsed values are bound on,
# which is the distinction the check below turns on. Three rendering owners
# name the theme both Streamlit pages are drawn in: the geometry owner for the
# font stacks a stylesheet cannot read out of a CSS variable, and the
# formatting owner for the thousands separators a count is rendered with. Both
# are plain data, so neither costs the optional dashboard dependency group.
_EXTERNAL_CHAINS = MappingProxyType({
    _CSS_OWNER: (
        "orchestrator.observability.dashboard",
        "orchestrator.observability.dashboard.tokens",
    ),
    _LOG_PATHS_OWNER: (
        "orchestrator.observability.analytics",
        "orchestrator.observability.analytics.config",
    ),
    _SUMMARY_HTML_OWNER: (
        "orchestrator.observability.dashboard",
        "orchestrator.observability.dashboard.formatting",
    ),
    _USAGE_HTML_OWNER: (
        "orchestrator.observability.dashboard",
        "orchestrator.observability.dashboard.formatting",
    ),
})

# The flat modules a historical caller still reaches this viewer through. The
# record facade among them plants the analytics package to resolve the log
# path, so an owner reaching back would put the sink's configuration -- and the
# dotenv read under it -- behind a caller that only wanted to build a step. It
# would also close a loop: those modules import these owners.
_FLAT_PREFIX = "orchestrator._trajectory"

_ANALYTICS_PACKAGE = "orchestrator.analytics"


def _qualified(owner: str) -> str:
    return f"{_PACKAGE}.{owner}"


def _defined_here(owner: str) -> tuple[str, ...]:
    """Public names the owner defines, as opposed to ones it imported."""
    module = import_module(_qualified(owner))
    return tuple(sorted(
        name
        for name, member in module.__dict__.items()
        if not name.startswith("_")
        and getattr(member, "__module__", None) == module.__name__
    ))


def _planted_siblings(owner: str) -> tuple[str, ...]:
    """Owners in this package that importing `owner` plants besides itself."""
    own_name = _qualified(owner)
    return tuple(sorted(
        planted.rpartition(".")[2]
        for planted in _imported_orchestrator_modules(own_name)
        if planted.startswith(f"{_PACKAGE}.") and planted != own_name
    ))


class OwnerInventoryTest(unittest.TestCase):
    """The declared owners are the ones on disk."""

    def test_declared_owners_are_the_ones_on_disk(self) -> None:
        directory = Path(_package.__file__).parent
        found = tuple(sorted(
            module_path.stem
            for module_path in directory.glob("*.py")
            if module_path.stem != "__init__"
        ))
        self.assertEqual(found, tuple(sorted(_OWNERS)))


class PublicSurfaceTest(unittest.TestCase):
    """Each owner answers for a narrow, declared surface."""

    def test_public_names_are_the_declared_ones(self) -> None:
        for owner, surface in _SURFACES.items():
            with self.subTest(owner=owner):
                self.assertEqual(_defined_here(owner), surface)

    def test_no_surface_is_declared_twice(self) -> None:
        # The package initializer is a marker, so a name is reached on the
        # owner that defines it rather than published a second time above it.
        self.assertNotIn("__all__", _package.__dict__)
        for owner in _OWNERS:
            with self.subTest(owner=owner):
                self.assertNotIn(
                    "__all__", import_module(_qualified(owner)).__dict__,
                )


class LayeringTest(unittest.TestCase):
    """The owners reach only what they compose, and never back to the page."""

    def test_each_owner_plants_only_its_own_chain(self) -> None:
        for owner, planted in _PLANTED.items():
            with self.subTest(owner=owner):
                self.assertEqual(_planted_siblings(owner), tuple(sorted(planted)))

    def test_owner_reaches_only_its_declared_chain(self) -> None:
        for owner in _OWNERS:
            planted = _imported_orchestrator_modules(_qualified(owner))
            outside = planted - _ALWAYS_PLANTED - {
                _qualified(sibling) for sibling in _OWNERS
            }
            with self.subTest(owner=owner):
                self.assertEqual(
                    tuple(sorted(outside)), _EXTERNAL_CHAINS.get(owner, ()),
                )

    def test_no_owner_plants_the_flat_leaves(self) -> None:
        # The sharpest case the check above rejects, named on its own: those
        # leaves forward *to* these owners, and the record facade among them
        # dials the analytics settings to resolve the log path. The
        # configuration owner one of these may name is not that package: it
        # parses a knob, while the package binds the parsed values, reads the
        # dotenv behind them, and imports these owners back.
        for owner in _OWNERS:
            planted = _imported_orchestrator_modules(_qualified(owner))
            reached = tuple(sorted(
                name for name in planted
                if name.startswith(_FLAT_PREFIX) or name == _ANALYTICS_PACKAGE
            ))
            with self.subTest(owner=owner):
                self.assertEqual(reached, ())


if __name__ == "__main__":
    unittest.main()
