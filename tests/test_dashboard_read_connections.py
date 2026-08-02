# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Dashboard cached-read connection scoping and forwarding tests."""

import inspect


import unittest


from types import MappingProxyType


from tests.dashboard_reload_helpers import (
    reload_dashboard as _reload,
)

ANALYTICS_DB_URL_ENV = "ANALYTICS_DB_URL"


CONFIGURED_DB_URL = "postgresql://h/db"


CONFIGURED_DB_ENV = MappingProxyType({ANALYTICS_DB_URL_ENV: CONFIGURED_DB_URL})


SCOPED_READ_CALL_FRAGMENT = "scoped_reads.scoped_read("


ENTRYPOINT_ATTR = "main"


class _MainSourceTest(unittest.TestCase):
    """Base for source checks over the lazy entrypoint and page helpers.

    Streamlit / Plotly are opt-in (not installed for the default
    `uv sync --locked`), so these read the rendered function source
    rather than driving the page under Streamlit. The entrypoint loads
    optional modules lazily and the page pipeline delegates controls,
    read waves, empty states, and widget sections to named helpers, so
    `_source_of` fetches the boundary each assertion protects.
    """

    def _main_source(self) -> str:
        return self._source_of(ENTRYPOINT_ATTR)

    def _source_of(self, name: str) -> str:
        _, dashboard = _reload(CONFIGURED_DB_ENV)
        return inspect.getsource(getattr(dashboard, name))


class CachedReadConnectionScopeTest(_MainSourceTest):
    """The read path reuses a thread-local analytics connection across
    the dashboard's reads instead of opening a socket per call (issue
    #376). The Streamlit cache keys must therefore stay
    connection-free -- a raw `psycopg.Connection` is not a hashable
    cache key and every reload would otherwise look like a cache miss.

    The windowed wrappers a page issues are the dashboard owners', and
    what each of them routes through -- and which wave it is staged into
    -- is pinned beside those owners. What is left here is the one page
    read issued outside them.
    """

    def test_the_drilldown_uses_the_shared_scope(self) -> None:
        # The per-issue trace is narrowed by more than a cache key carries, so
        # it is the one page read issued outside the filtered wrapper -- and
        # still through the scope owner, sharing the socket the widgets opened.
        self.assertIn(
            SCOPED_READ_CALL_FRAGMENT,
            self._source_of("_render_drilldown_view"),
        )


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
