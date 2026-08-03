# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Dashboard KPI-strip extraction tests."""

import sys


import unittest


from types import MappingProxyType


from tests.dashboard_reload_helpers import (
    reload_dashboard as _reload,
)


DASHBOARD_KPI_STRIP_MODULE = "orchestrator.dashboard_kpi_strip"


DASHBOARD_WIDGETS_MODULE = "orchestrator.dashboard_widgets"


ANALYTICS_DB_URL_ENV = "ANALYTICS_DB_URL"


CONFIGURED_DB_URL = "postgresql://h/db"


CONFIGURED_DB_ENV = MappingProxyType({ANALYTICS_DB_URL_ENV: CONFIGURED_DB_URL})


_DASHBOARD_OWNERS = "orchestrator.observability.dashboard"


_KPI_SERIES_OWNER = "kpi_series"


_KPI_STRIP_OWNER = "kpi_strip"


# The per-day lines a sparkline is drawn from and the tiles they are drawn
# under are the dashboard owners' own objects, published on this hub under the
# spellings a caller reached them by. They report their owner rather than the
# hub, so the guard on them is where each resolves to.
_OWNED_KPI_MEMBERS = MappingProxyType({
    "_DailyKpiSeries": _KPI_SERIES_OWNER,
    "_daily_kpi_series": _KPI_SERIES_OWNER,
    "_daily_point_totals": _KPI_SERIES_OWNER,
    "_summary_total_tokens": _KPI_SERIES_OWNER,
    "_throughput_totals": _KPI_SERIES_OWNER,
    "_time_series_total_tokens": _KPI_SERIES_OWNER,
    "_KpiInputs": _KPI_STRIP_OWNER,
    "_KpiTotals": _KPI_STRIP_OWNER,
    "_build_kpi_strip_data": _KPI_STRIP_OWNER,
    "_cost_per_resolved": _KPI_STRIP_OWNER,
    "_kpi_strip_entries": _KPI_STRIP_OWNER,
    "_kpi_totals": _KPI_STRIP_OWNER,
})


# The two the page pipeline reaches through the lazy `dashboard.<name>`
# surface: what one strip is built from, and the build that returns it.
_FACADE_KPI_MEMBERS = (
    "_KpiInputs",
    "_build_kpi_strip_data",
)


class KpiStripExtractionTest(unittest.TestCase):
    """`orchestrator.dashboard_kpi_strip` republishes the KPI-strip shaping --
    the token, throughput, and per-day series helpers plus the totals and
    display entries that turn a `Summary` aggregate and the first-wave read
    rows into the four tiles and the resolved / rejected pair beside them --
    which the dashboard owners hold. `orchestrator.dashboard` re-exports the
    two members the page pipeline reaches (`_KpiInputs` /
    `_build_kpi_strip_data`) under the same names, and `dashboard_widgets`
    imports `_KpiInputs` back from the hub. That is a resolution contract
    rather than a call path: what a page reaches, and what a test therefore
    patches, is the owner itself.
    """

    def test_owned_kpi_members_report_their_owner(self) -> None:
        _reload(CONFIGURED_DB_ENV)
        kpi_strip = sys.modules[DASHBOARD_KPI_STRIP_MODULE]
        for name, owner in _OWNED_KPI_MEMBERS.items():
            with self.subTest(name=name):
                self.assertEqual(
                    getattr(kpi_strip, name).__module__,
                    f"{_DASHBOARD_OWNERS}.{owner}",
                )

    def test_facade_reexports_kpi_strip_objects(self) -> None:
        _, dashboard = _reload(CONFIGURED_DB_ENV)
        kpi_strip = sys.modules[DASHBOARD_KPI_STRIP_MODULE]
        for name in _FACADE_KPI_MEMBERS:
            with self.subTest(name=name):
                self.assertTrue(
                    hasattr(dashboard, name),
                    f"dashboard dropped the historical {name!r} alias",
                )
                self.assertIs(getattr(dashboard, name), getattr(kpi_strip, name))

    def test_widgets_imports_kpi_inputs_from_the_hub(self) -> None:
        _reload(CONFIGURED_DB_ENV)
        widgets = sys.modules[DASHBOARD_WIDGETS_MODULE]
        kpi_strip = sys.modules[DASHBOARD_KPI_STRIP_MODULE]
        self.assertIs(widgets._KpiInputs, kpi_strip._KpiInputs)
