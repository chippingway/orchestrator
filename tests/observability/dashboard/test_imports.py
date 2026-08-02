# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Inventory, surface, and layering checks for the dashboard owners."""
from __future__ import annotations

import unittest
from importlib import import_module
from pathlib import Path
from types import MappingProxyType

from orchestrator.observability import dashboard as _package
from tests.observability.observability_test_support import (
    _imported_orchestrator_modules,
    _run_import_probe,
)

_PACKAGE = "orchestrator.observability.dashboard"

_BREAKDOWNS_OWNER = "breakdowns"

_CSS_OWNER = "css"

_FANOUT_OWNER = "fanout"

_FILTER_BINDING_OWNER = "filter_binding"

_FILTERS_OWNER = "filters"

_FORMATTING_OWNER = "formatting"

_INSIGHTS_OWNER = "insights"

_LAYOUT_OWNER = "layout"

_PALETTE_OWNER = "palette"

_READ_MODE_OWNER = "read_mode"

_SCOPED_READS_OWNER = "scoped_reads"

_SKILLS_OWNER = "skills"

_STATIC_METADATA_OWNER = "static_metadata"

_TOKENS_OWNER = "tokens"

_WINDOWS_OWNER = "windows"

# The declared inventory. A new owner is a deliberate edit here and a paragraph
# in the module map, which is what the inventory check compares the directory
# against.
_OWNERS = (
    _BREAKDOWNS_OWNER,
    _CSS_OWNER,
    _FANOUT_OWNER,
    _FILTER_BINDING_OWNER,
    _FILTERS_OWNER,
    _FORMATTING_OWNER,
    _INSIGHTS_OWNER,
    _LAYOUT_OWNER,
    _PALETTE_OWNER,
    _READ_MODE_OWNER,
    _SCOPED_READS_OWNER,
    _SKILLS_OWNER,
    _STATIC_METADATA_OWNER,
    _TOKENS_OWNER,
    _WINDOWS_OWNER,
)

# What each owner answers for, declared rather than discovered so a second way
# to resolve a color, lay a chart out, shorten a number, spell a window,
# normalize a selection, key a cached read, read that key back as a read's
# filters, decide which way a load's reads are issued, run one wave of them
# that way, check out the connection one of them runs on, draw a comparison
# panel from one of the six reads behind it or a skill panel from one of the
# three, open a page on the extent behind its filter bar, or interrupt one with
# a banner is a deliberate
# edit rather than a place two panels -- or the reads' `ts < end` bound and the
# cache's tri-state -- could
# disagree. Two owners report nothing because the check reads `__module__`,
# which only a class or a function carries: the geometry owner's whole surface
# is its measurements and the two font stacks, and the stylesheet owner's is
# one string. The palette's chrome colors and seven dimension maps, the preset
# vocabulary the window owner decides, the read-mode owner's knob name, truthy
# spellings, worker cap, refusal message, and the flag its import binds, the
# alias the fan-out owner names a reader by, the two bands the insight owner
# raises a banner at and the spellings an unpriced run reaches it under, and
# the TTL the metadata owner caches under are all invisible here for the same
# reason.
_SURFACES = MappingProxyType({
    _BREAKDOWNS_OWNER: (
        "read_backend_daily_tokens",
        "read_backend_efficiency",
        "read_cost_coverage",
        "read_hourly_heatmap",
        "read_repo_breakdown",
        "read_throughput",
    ),
    _CSS_OWNER: (),
    _FANOUT_OWNER: ("fan_out_reads",),
    _FILTER_BINDING_OWNER: (
        "filter_list",
        "read_filter_kwargs",
        "read_filtered",
    ),
    _FILTERS_OWNER: (
        "DashboardCacheKey",
        "cache_key",
        "format_tz_offset",
        "parse_issue_number",
        "resolve_stage_filter",
        "shift_ts",
    ),
    _FORMATTING_OWNER: (
        "fmt_money",
        "fmt_money_exact",
        "fmt_num",
        "fmt_tokens",
    ),
    _INSIGHTS_OWNER: ("InsightBanner", "compute_insights"),
    _LAYOUT_OWNER: ("base_layout",),
    _PALETTE_OWNER: ("color_for",),
    _READ_MODE_OWNER: (
        "dashboard_parallel_reads_enabled",
        "db_unconfigured_message",
        "parse_parallel_reads_flag",
    ),
    _SCOPED_READS_OWNER: ("scoped_read",),
    _SKILLS_OWNER: (
        "read_skill_adoption",
        "read_skill_trigger_matrix",
        "read_skill_trigger_rates",
    ),
    _STATIC_METADATA_OWNER: (
        "read_data_extent",
        "read_filter_options",
        "read_static_metadata",
    ),
    _TOKENS_OWNER: (),
    _WINDOWS_OWNER: (
        "DateWindow",
        "default_date_range",
        "extent_dates",
        "preset_window",
        "previous_window",
        "to_window",
    ),
})

# The two owners that render a surface out of the tokens rather than declaring
# any: the Plotly defaults every figure is merged with, and the stylesheet the
# chrome around those figures is drawn by.
_RENDERED_SURFACES = (_CSS_OWNER, _LAYOUT_OWNER)

# The historical import sites the pages still reach these owners through: the
# flat theme module, the state, read, and KPI hubs, and the seven leaves
# beneath the first two. No owner here may plant one -- that is what keeps the
# forwarding one-directional and the flat modules retirable rather than
# load-bearing.
_COMPATIBILITY_SITES = (
    "orchestrator._dashboard_filter_state",
    "orchestrator._dashboard_read_breakdowns",
    "orchestrator._dashboard_read_core",
    "orchestrator._dashboard_read_mode",
    "orchestrator._dashboard_read_skills",
    "orchestrator._dashboard_state_constants",
    "orchestrator._dashboard_windows",
    "orchestrator.dashboard_kpis",
    "orchestrator.dashboard_reads",
    "orchestrator.dashboard_state",
    "orchestrator.dashboard_theme",
)

# What an owner here may reach: its siblings, plus the analytics owners named
# by the ones that touch a database. Each of those is one answer already
# decided elsewhere, so the owner that needs it names the owner that gives it
# rather than a facade in front of one: the extent a preset anchors at is a
# read's answer, whether there is a database to read at all is one knob's, the
# socket a read runs on is the connection cache's, the exception a failed read
# arrives as is the connection owner's, the two unfiltered reads a page opens
# with are the raw read family's, the six a comparison panel is drawn from are
# the rollup and breakdown families', the three a skill panel is drawn from are
# the skill family's, and the totals and cost-source split a banner is raised
# over are the rows those reads hand back.
_PERMITTED_PREFIXES = ("orchestrator.observability", "orchestrator._package")

# The driver the reads behind these windows are issued over. Nothing here
# dials anything, so a caller that only resolves a preset, hashes a filter set,
# or reads a color must not pay for it -- nor be unable to do any of the three
# on a machine with no Postgres client installed.
_DRIVER_PROBE = """
import sys
import {module}
driver = [name for name in sys.modules if name.split('.')[0] == 'psycopg']
sys.exit(', '.join(driver) if driver else 0)
"""


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
    """The owners reach only siblings, nothing dials, and each rendered
    surface is built from the tokens rather than restating them.
    """

    def test_no_owner_reaches_outside_the_package(self) -> None:
        for owner in _OWNERS:
            planted = _imported_orchestrator_modules(_qualified(owner))
            for imported in planted:
                with self.subTest(owner=owner, imported=imported):
                    self.assertTrue(
                        imported.startswith(_PERMITTED_PREFIXES)
                        or imported == "orchestrator",
                        f"{owner} reaches {imported}",
                    )

    def test_no_owner_plants_a_historical_site(self) -> None:
        # The sharpest case the check above rejects, named on its own: the
        # flat modules a page still imports forward *to* these owners, so an
        # import back would close the loop and put the compatibility layer
        # inside what rendering a chart or resolving a window costs.
        for owner in _OWNERS:
            planted = _imported_orchestrator_modules(_qualified(owner))
            for site in _COMPATIBILITY_SITES:
                with self.subTest(owner=owner, site=site):
                    self.assertNotIn(site, planted)

    def test_no_owner_plants_the_driver(self) -> None:
        for owner in _OWNERS:
            completed = _run_import_probe(
                _DRIVER_PROBE.format(module=_qualified(owner)),
            )
            with self.subTest(owner=owner):
                self.assertEqual(
                    completed.returncode, 0, msg=completed.stderr,
                )

    def test_a_rendered_surface_names_the_tokens(self) -> None:
        # A CSS variable and a figure's gridline are the same value seen twice,
        # so both surfaces have to read it off the owners that hold it: a hue
        # or a radius restated in either place is a page whose chrome and
        # charts drift apart on the next edit.
        for owner in _RENDERED_SURFACES:
            planted = _imported_orchestrator_modules(_qualified(owner))
            for token_owner in (_PALETTE_OWNER, _TOKENS_OWNER):
                with self.subTest(owner=owner, token_owner=token_owner):
                    self.assertIn(_qualified(token_owner), planted)


if __name__ == "__main__":
    unittest.main()
