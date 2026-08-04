# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Dashboard analytics-connection exposure tests.

What each page read routes through, and the scope every one of them is issued
inside, is pinned beside the owners that decide it. What is left here is the
connection surface a caller reaches off the facade.
"""

import unittest


from tests.dashboard_reload_helpers import (
    reload_dashboard as _reload,
)

ANALYTICS_DB_URL_ENV = "ANALYTICS_DB_URL"


class AnalyticsConnectionExposureTest(unittest.TestCase):
    """`analytics_connection` and `close_thread_local_connection` are
    the new public surface from `analytics_read`. The dashboard
    imports the module wholesale (`from orchestrator.analytics import
    read as analytics_read`), so the symbols must be reachable as
    attributes for both `with analytics_read.analytics_connection()`
    and any shutdown hook that wants to drain the thread-local.
    """

    def test_connection_is_a_context_manager(self) -> None:
        _, dashboard = _reload({ANALYTICS_DB_URL_ENV: ""})
        self.assertTrue(hasattr(dashboard.analytics_read, "analytics_connection"))
        self.assertTrue(hasattr(dashboard.analytics_read, "close_thread_local_connection"))
        # Quick smoke: the unset-URL branch yields None without
        # touching any connect factory.
        with dashboard.analytics_read.analytics_connection() as conn:
            self.assertIsNone(conn)
