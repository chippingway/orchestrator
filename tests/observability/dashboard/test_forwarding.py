# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What the flat dashboard modules still answer for once the owners hold it."""
from __future__ import annotations

import unittest
from importlib import import_module
from types import MappingProxyType

_THEME_FACADE = "orchestrator.dashboard_theme"

_STATE_HUB = "orchestrator.dashboard_state"

_READ_MODE_LEAF = "orchestrator._dashboard_read_mode"

# `from __future__ import annotations` opens every module in the repository and
# binds the compiler directive under a public name. It is a compilation
# instruction rather than something the theme answers for, so the surface check
# looks past it.
_FUTURE_DIRECTIVE = "annotations"

_PACKAGE = "orchestrator.observability.dashboard"

_CSS = f"{_PACKAGE}.css"

_FANOUT = f"{_PACKAGE}.fanout"

_FILTERS = f"{_PACKAGE}.filters"

_FORMATTING = f"{_PACKAGE}.formatting"

_LAYOUT = f"{_PACKAGE}.layout"

_PALETTE = f"{_PACKAGE}.palette"

_READ_MODE = f"{_PACKAGE}.read_mode"

_TOKENS = f"{_PACKAGE}.tokens"

_WINDOWS = f"{_PACKAGE}.windows"

# Every name a page reaches through `dashboard_theme`, and the owner it now
# resolves to. A color read here and the same color read off its owner have to
# be one object rather than two equal ones: the CSS variable the chrome is
# drawn from and the Plotly attribute a trace is drawn from are the same value
# seen twice, and a copy is where the two would start to disagree.
_FORWARDED = MappingProxyType({
    _PALETTE: (
        "ACCENT",
        "AGENT_ROLE_COLORS",
        "BACKEND_COLORS",
        "BACKGROUND",
        "BORDER",
        "CARD_BG",
        "CATEGORICAL_PALETTE",
        "COST_SOURCE_COLORS",
        "DANGER",
        "EVENT_COLORS",
        "GRID",
        "INK",
        "MUTED_TEXT",
        "MUTED_TEXT_SOFT",
        "NEUTRAL",
        "PRIMARY",
        "REVIEW_ROUND_COLORS",
        "SECONDARY",
        "STAGE_COLORS",
        "SUCCESS",
        "SURFACE",
        "TEXT",
        "TOKEN_TYPE_COLORS",
        "WARNING",
        "color_for",
    ),
    _TOKENS: (
        "CARD_PADDING",
        "CONTENT_MAX_WIDTH",
        "FONT_FAMILY",
        "FONT_SIZE",
        "GRID_GAP",
        "MONO_FONT_FAMILY",
        "RADIUS",
        "TITLE_FONT_SIZE",
        "TOPBAR_STICKY_HEIGHT",
    ),
    _LAYOUT: ("base_layout",),
    _CSS: ("PAGE_CSS",),
    _FORMATTING: (
        "fmt_money",
        "fmt_money_exact",
        "fmt_num",
        "fmt_tokens",
    ),
})

# The preset vocabulary, named once and read by both state checks below: the
# label a caller renders and the day count the window owner clamps by have to
# come off the same object, or the filter bar could offer a preset the
# arithmetic does not know.
_PRESET_NAMES = (
    ("DEFAULT_PRESET", _WINDOWS, "DEFAULT_PRESET"),
    ("DEFAULT_WINDOW_DAYS", _WINDOWS, "DEFAULT_WINDOW_DAYS"),
    ("PRESET_ALL", _WINDOWS, "PRESET_ALL"),
    ("PRESET_CUSTOM", _WINDOWS, "PRESET_CUSTOM"),
    ("PRESET_DAYS", _WINDOWS, "PRESET_DAYS"),
    ("PRESET_INLINE_LABELS", _WINDOWS, "PRESET_INLINE_LABELS"),
    ("PRESET_LABELS", _WINDOWS, "PRESET_LABELS"),
    ("PRESET_OPTIONS", _WINDOWS, "PRESET_OPTIONS"),
    ("PRESET_RECENT_THREE_DAYS", _WINDOWS, "PRESET_RECENT_THREE_DAYS"),
    ("PRESET_RECENT_WEEK", _WINDOWS, "PRESET_RECENT_WEEK"),
)

# The offset range the sidebar selector is drawn from, and beneath it the two
# bounds the range is built out of -- those only ever reached the leaf, so the
# hub is not asked for them.
_OFFSET_NAMES = (
    ("DEFAULT_TZ_OFFSET_HOURS", _FILTERS, "DEFAULT_TZ_OFFSET_HOURS"),
    ("TZ_OFFSET_OPTIONS", _FILTERS, "TZ_OFFSET_OPTIONS"),
)

_OFFSET_BOUND_NAMES = (
    ("MAX_UTC_OFFSET", _FILTERS, "MAX_UTC_OFFSET"),
    ("MIN_UTC_OFFSET", _FILTERS, "MIN_UTC_OFFSET"),
)

# The read-mode constants the page still names directly. These are the names
# that have to keep pointing at one knob and one refusal message rather than a
# copy each. The truthy set is listed apart because the two sites spell it
# differently: bare on the leaf, and under a leading underscore on the hub.
_READ_MODE_NAMES = (
    ("PARALLEL_READS_ENV", _READ_MODE, "PARALLEL_READS_ENV"),
    ("PARALLEL_READS_MAX_WORKERS", _READ_MODE, "PARALLEL_READS_MAX_WORKERS"),
    ("UNCONFIGURED_DB_MESSAGE", _READ_MODE, "UNCONFIGURED_DB_MESSAGE"),
)

_LEAF_TRUTHY_NAME = ("TRUTHY", _READ_MODE, "TRUTHY")

_HUB_TRUTHY_NAME = ("_TRUTHY", _READ_MODE, "TRUTHY")

# The read-mode helpers both flat sites publish. Each has to be the owner's own
# object rather than a wrapper around it: the switch a page load is issued
# under and the refusal it is stopped by are single decisions, and a copy on
# either site is where a page and the owner would start to answer differently.
_READ_MODE_HELPERS = (
    (
        "dashboard_parallel_reads_enabled",
        _READ_MODE,
        "dashboard_parallel_reads_enabled",
    ),
    ("db_unconfigured_message", _READ_MODE, "db_unconfigured_message"),
)

# The parse is the third helper, listed apart because the two sites spell it
# differently: bare on the leaf, and under a leading underscore on the hub --
# which also publishes the flag that parse bound while the owner imported, so
# what a page reads cannot become a second parse of the same knob.
_HUB_READ_MODE_HELPERS = (
    *_READ_MODE_HELPERS,
    ("DASHBOARD_PARALLEL_READS", _READ_MODE, "DASHBOARD_PARALLEL_READS"),
    ("_parse_parallel_reads_flag", _READ_MODE, "parse_parallel_reads_flag"),
)

_LEAF_READ_MODE_HELPERS = (
    *_READ_MODE_HELPERS,
    ("parse_parallel_reads_flag", _READ_MODE, "parse_parallel_reads_flag"),
)

# The dispatch a page's read waves are run through, and the alias one reader
# in a wave is spelled by. Both sites have to reach the one fan-out: a wave
# submitted through a copy would key its results the same way while running
# them under whatever cap that copy was written with.
_LEAF_FAN_OUT_NAMES = (
    ("NamedReader", _FANOUT, "NamedReader"),
    ("fan_out_reads", _FANOUT, "fan_out_reads"),
)

_HUB_FAN_OUT_NAME = ("_fan_out_reads", _FANOUT, "fan_out_reads")

_WINDOW_NAMES = (
    ("DateWindow", _WINDOWS, "DateWindow"),
    ("default_date_range", _WINDOWS, "default_date_range"),
    ("preset_window", _WINDOWS, "preset_window"),
    ("previous_window", _WINDOWS, "previous_window"),
    ("to_window", _WINDOWS, "to_window"),
)

# The bounding-day read is the other name the two sites spell differently.
_LEAF_EXTENT_NAME = ("extent_dates", _WINDOWS, "extent_dates")

_HUB_EXTENT_NAME = ("_extent_dates", _WINDOWS, "extent_dates")

_FILTER_NAMES = (
    ("DashboardCacheKey", _FILTERS, "DashboardCacheKey"),
    ("cache_key", _FILTERS, "cache_key"),
    ("format_tz_offset", _FILTERS, "format_tz_offset"),
    ("parse_issue_number", _FILTERS, "parse_issue_number"),
    ("resolve_stage_filter", _FILTERS, "resolve_stage_filter"),
    ("shift_ts", _FILTERS, "shift_ts"),
)

# The flat modules a caller reaches a state owner through, and what each name
# they publish resolves to: a window built here has to be the one the reads are
# bounded by, and a key hashed here the one the cached reads are stored under,
# or a fix under the owners would reach only half of the callers.
_FORWARDED_MODULES = MappingProxyType({
    "orchestrator._dashboard_state_constants": (
        *_PRESET_NAMES,
        *_OFFSET_NAMES,
        *_OFFSET_BOUND_NAMES,
        *_READ_MODE_NAMES,
        _LEAF_TRUTHY_NAME,
    ),
    "orchestrator._dashboard_windows": (*_WINDOW_NAMES, _LEAF_EXTENT_NAME),
    "orchestrator._dashboard_filter_state": _FILTER_NAMES,
    _READ_MODE_LEAF: (*_LEAF_READ_MODE_HELPERS, *_LEAF_FAN_OUT_NAMES),
})

# The hub the page and the compatibility facade in front of it read the state
# off. It keeps the two historical aliases for the inline presets and the four
# private spellings a caller reached it for, so those are pinned beside the
# public names.
_FORWARDED_HUB = (
    *_PRESET_NAMES,
    *_OFFSET_NAMES,
    *_READ_MODE_NAMES,
    *_HUB_READ_MODE_HELPERS,
    *_WINDOW_NAMES,
    *_FILTER_NAMES,
    _HUB_TRUTHY_NAME,
    _HUB_EXTENT_NAME,
    _HUB_FAN_OUT_NAME,
    ("PRESET_3D", _WINDOWS, "PRESET_RECENT_THREE_DAYS"),
    ("PRESET_7D", _WINDOWS, "PRESET_RECENT_WEEK"),
)


def _facade_surface() -> frozenset[str]:
    """Public names an importer of the historical site can read off it."""
    facade = import_module(_THEME_FACADE)
    return frozenset(
        name
        for name in facade.__dict__
        if not name.startswith("_") and name != _FUTURE_DIRECTIVE
    )


class ForwardedThemeTest(unittest.TestCase):
    """The historical import site binds the owners' objects, not copies."""

    def test_each_name_resolves_to_the_owner(self) -> None:
        facade = import_module(_THEME_FACADE)
        for owner_name, forwarded in _FORWARDED.items():
            owner = import_module(owner_name)
            for name in forwarded:
                with self.subTest(owner=owner_name, name=name):
                    self.assertIs(getattr(facade, name), getattr(owner, name))

    def test_the_declared_names_are_the_whole_surface(self) -> None:
        # A name the owners grew but the flat module never published would
        # leave a page importing it from two places, and a name published here
        # with no owner behind it is an implementation that came back.
        declared = frozenset(
            name for forwarded in _FORWARDED.values() for name in forwarded
        )
        self.assertEqual(_facade_surface(), declared)

    def test_it_defines_nothing_of_its_own(self) -> None:
        # What keeps the forwarding thin: an implementation here would be a
        # second set of tokens the check above cannot see, because it only
        # compares the names the module was asked for.
        facade = import_module(_THEME_FACADE)
        defined = tuple(
            name
            for name, member in facade.__dict__.items()
            if getattr(member, "__module__", None) == _THEME_FACADE
        )
        self.assertEqual(defined, ())


class ForwardedFlatModuleTest(unittest.TestCase):
    """Every name the flat state modules publish is the owner's own object."""

    def test_each_name_resolves_to_the_owner(self) -> None:
        for module_name, forwarded in _FORWARDED_MODULES.items():
            for name, owner_name, attribute in forwarded:
                with self.subTest(module=module_name, name=name):
                    self.assertIs(
                        getattr(import_module(module_name), name),
                        getattr(import_module(owner_name), attribute),
                    )

    def test_no_flat_module_defines_one_itself(self) -> None:
        # The same rule the theme site is held to, applied to the four leaves
        # beneath the state hub: a module that defined a name of its own would
        # be a second implementation the check above cannot see, because it
        # only compares the names the module was asked for.
        for module_name in _FORWARDED_MODULES:
            defined = tuple(
                name
                for name, member in import_module(module_name).__dict__.items()
                if getattr(member, "__module__", None) == module_name
            )
            with self.subTest(module=module_name):
                self.assertEqual(defined, ())


class ForwardedStateHubTest(unittest.TestCase):
    """The hub the page reads binds the owners' objects, not copies."""

    def test_each_name_resolves_to_the_owner(self) -> None:
        hub = import_module(_STATE_HUB)
        for name, owner_name, attribute in _FORWARDED_HUB:
            with self.subTest(name=name):
                self.assertIs(
                    getattr(hub, name),
                    getattr(import_module(owner_name), attribute),
                )


if __name__ == "__main__":
    unittest.main()
