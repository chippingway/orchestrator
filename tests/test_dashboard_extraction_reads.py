# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Dashboard read-orchestration extraction tests."""

import unittest


from importlib import import_module


from types import MappingProxyType


from tests.dashboard_reload_helpers import (
    reload_dashboard as _reload,
)


DASHBOARD_READS_MODULE = "orchestrator.dashboard_reads"


ANALYTICS_DB_URL_ENV = "ANALYTICS_DB_URL"


CONFIGURED_DB_URL = "postgresql://h/db"


CONFIGURED_DB_ENV = MappingProxyType({ANALYTICS_DB_URL_ENV: CONFIGURED_DB_URL})


_MOVED_READ_MEMBERS = (
    "_dispatch_reads",
    "_log_dashboard_load",
    "_run_read_waves",
)


_BREAKDOWNS_OWNER = "breakdowns"


_READ_PLAN_OWNER = "read_plan"


_ROLLUPS_OWNER = "rollups"


_SKILLS_OWNER = "skills"


# The staged read plan and its two wave registries, the seven headline and
# lifecycle reads, the six comparison-panel ones, the three skill-panel ones,
# the connection scope, the filter binding, and the static-metadata reads are
# the dashboard owners' own objects, published here under the spellings a
# caller reached them by. They report their owner rather than this hub, so the
# guard on them is where each resolves to.
_OWNED_READ_MEMBERS = MappingProxyType({
    "_DashboardReadPlan": _READ_PLAN_OWNER,
    "_widget_task": _READ_PLAN_OWNER,
    "_first_wave_readers": _READ_PLAN_OWNER,
    "_second_wave_readers": _READ_PLAN_OWNER,
    "_widget_readers": _READ_PLAN_OWNER,
    "_build_read_keys": _READ_PLAN_OWNER,
    "_read_summary": _ROLLUPS_OWNER,
    "_read_prev_kpi": _ROLLUPS_OWNER,
    "_read_time_series": _ROLLUPS_OWNER,
    "_read_stage_breakdown": _ROLLUPS_OWNER,
    "_read_recent_agent_exits": _ROLLUPS_OWNER,
    "_read_top_cost_issues": _ROLLUPS_OWNER,
    "_read_review_round": _ROLLUPS_OWNER,
    "_read_backend_efficiency": _BREAKDOWNS_OWNER,
    "_read_repo_breakdown": _BREAKDOWNS_OWNER,
    "_read_cost_coverage": _BREAKDOWNS_OWNER,
    "_read_hourly_heatmap": _BREAKDOWNS_OWNER,
    "_read_throughput": _BREAKDOWNS_OWNER,
    "_read_backend_daily_tokens": _BREAKDOWNS_OWNER,
    "_read_skill_adoption": _SKILLS_OWNER,
    "_read_skill_trigger_matrix": _SKILLS_OWNER,
    "_read_skill_trigger_rates": _SKILLS_OWNER,
    "_filter_list": "filter_binding",
    "_read_filter_kwargs": "filter_binding",
    "_read_filtered": "filter_binding",
    "_scoped_read": "scoped_reads",
    "_read_data_extent": "static_metadata",
    "_read_filter_options": "static_metadata",
    "_read_static_metadata": "static_metadata",
})


_DASHBOARD_OWNERS = "orchestrator.observability.dashboard"


_READS_FACADE_CONSTANTS = (
    "DEFAULT_RECENT_AGENT_EXITS",
    "STATIC_METADATA_TTL_SECONDS",
    "LOADING_INDICATOR_MESSAGE",
)


def _reloaded_reads():
    """Reload the page world and name the hub the lazy facade resolves to.

    The hub is a compatibility site rather than something a page load imports,
    so a reload leaves it unbound and it is named here on demand -- which is
    exactly when a `dashboard.<name>` access resolves it.
    """
    _reload(CONFIGURED_DB_ENV)
    return import_module(DASHBOARD_READS_MODULE)


class ReadOrchestrationExtractionTest(unittest.TestCase):
    """The staged parallel dispatch, the two-wave data load, and the
    load-timing log live in `orchestrator.dashboard_reads`, which also
    republishes the read plan and reader registries staging that load plus the
    headline, lifecycle, comparison-panel, skill-panel, connection,
    filter-binding, and static-metadata reads the dashboard owners hold.
    `orchestrator.dashboard` re-exports every member under the same name so the
    `dashboard.<name>` surface and its test patch points keep resolving to the
    same object.
    """

    def test_read_members_defined_in_reads_module(self) -> None:
        reads = _reloaded_reads()
        for name in _MOVED_READ_MEMBERS:
            with self.subTest(name=name):
                self.assertEqual(
                    getattr(reads, name).__module__,
                    DASHBOARD_READS_MODULE,
                )

    def test_owned_read_members_report_their_owner(self) -> None:
        reads = _reloaded_reads()
        for name, owner in _OWNED_READ_MEMBERS.items():
            with self.subTest(name=name):
                self.assertEqual(
                    getattr(reads, name).__module__,
                    f"{_DASHBOARD_OWNERS}.{owner}",
                )

    def test_facade_reexports_reads_objects(self) -> None:
        _, dashboard = _reload(CONFIGURED_DB_ENV)
        reads = import_module(DASHBOARD_READS_MODULE)
        published = (
            *_MOVED_READ_MEMBERS,
            *_OWNED_READ_MEMBERS,
            *_READS_FACADE_CONSTANTS,
        )
        for name in published:
            with self.subTest(name=name):
                self.assertTrue(
                    hasattr(dashboard, name),
                    f"dashboard dropped the historical {name!r} alias",
                )
                self.assertIs(getattr(dashboard, name), getattr(reads, name))
