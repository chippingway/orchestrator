# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Dashboard read-orchestration extraction tests."""

import sys


import unittest


from types import MappingProxyType


from tests.dashboard_reload_helpers import (
    reload_dashboard as _reload,
)


DASHBOARD_READS_MODULE = "orchestrator.dashboard_reads"


ANALYTICS_DB_URL_ENV = "ANALYTICS_DB_URL"


CONFIGURED_DB_URL = "postgresql://h/db"


CONFIGURED_DB_ENV = MappingProxyType({ANALYTICS_DB_URL_ENV: CONFIGURED_DB_URL})


STAMPED_READER_WRAPPER_NAMES = (
    "_read_summary",
    "_read_prev_kpi",
    "_read_time_series",
    "_read_stage_breakdown",
    "_read_recent_agent_exits",
    "_read_top_cost_issues",
    "_read_review_round",
)


_MOVED_READ_MEMBERS = (
    *STAMPED_READER_WRAPPER_NAMES,
    "_widget_task",
    "_first_wave_readers",
    "_second_wave_readers",
    "_widget_readers",
    "_build_read_keys",
    "_dispatch_reads",
    "_log_dashboard_load",
    "_run_read_waves",
    "_DashboardReadPlan",
)


_BREAKDOWNS_OWNER = "breakdowns"


_SKILLS_OWNER = "skills"


# The six comparison-panel reads, the three skill-panel ones, the connection
# scope, the filter binding, and the static-metadata reads are the dashboard
# owners' own objects, published here under the spellings a caller reached them
# by. They report their owner rather than this hub, so the guard on them is
# where each resolves to.
_OWNED_READ_MEMBERS = MappingProxyType({
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


class ReadOrchestrationExtractionTest(unittest.TestCase):
    """The dashboard read orchestration -- cached reader wrappers, reader
    registries, the staged parallel dispatch + two-wave data load, and the
    load-timing log -- lives in `orchestrator.dashboard_reads`, which also
    republishes the comparison-panel, skill-panel, connection, filter-binding,
    and static-metadata reads the dashboard owners hold. `orchestrator.dashboard`
    re-exports every member under the same name so the `dashboard.<name>`
    surface and its test patch points keep resolving to the same object.
    """

    def test_read_members_defined_in_reads_module(self) -> None:
        _reload(CONFIGURED_DB_ENV)
        reads = sys.modules[DASHBOARD_READS_MODULE]
        for name in _MOVED_READ_MEMBERS:
            with self.subTest(name=name):
                self.assertEqual(
                    getattr(reads, name).__module__,
                    DASHBOARD_READS_MODULE,
                )

    def test_owned_read_members_report_their_owner(self) -> None:
        _reload(CONFIGURED_DB_ENV)
        reads = sys.modules[DASHBOARD_READS_MODULE]
        for name, owner in _OWNED_READ_MEMBERS.items():
            with self.subTest(name=name):
                self.assertEqual(
                    getattr(reads, name).__module__,
                    f"{_DASHBOARD_OWNERS}.{owner}",
                )

    def test_facade_reexports_reads_objects(self) -> None:
        _, dashboard = _reload(CONFIGURED_DB_ENV)
        reads = sys.modules[DASHBOARD_READS_MODULE]
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
