# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a keyword call binds into, and the projections a family reads back."""
from __future__ import annotations

import unittest
from datetime import UTC, datetime
from types import MappingProxyType

from orchestrator.observability.analytics.query.filters import WindowFilters
from orchestrator.observability.analytics.query.request_models import (
    ReadConnection,
    ReadFilters,
    ReadOptions,
)
from orchestrator.observability.analytics.query.requests import (
    FILTERED_READ_SIGNATURE,
    HEATMAP_SIGNATURE,
    ISSUE_EVENTS_SIGNATURE,
    ISSUES_SIGNATURE,
    LIMITED_READ_SIGNATURE,
    RECENT_EXITS_SIGNATURE,
    SOURCE_READ_SIGNATURE,
)
from orchestrator.observability.analytics.query.requests import (
    RECENT_EXIT_LIMIT,
    bind_read_request,
    resolve_read_query,
    window_filters,
)
from tests.observability.analytics.query.query_fake_driver import (
    FakeConnect,
    FakeConnection,
)
from tests.observability.analytics.query.query_test_support import DB_URL

_AGENT_EXIT = "agent_exit"

_STAGE_IMPLEMENTING = "implementing"

_REPO = "owner/r"

_ISSUE = 42

_YEAR = 2026

_WINDOW_END_DAY = 28

_WINDOW_START = datetime(_YEAR, 5, 1, tzinfo=UTC)

_WINDOW_END = datetime(_YEAR, 5, _WINDOW_END_DAY, tzinfo=UTC)

# The row cap the paged families default to, and the ordering the issue table
# falls back on.
_PAGE_LIMIT = 100

_SORT_BY_LAST_SEEN = "last_seen"

# One dashboard call, spelled the way every public read is called.
_FILTER_CALL = MappingProxyType({
    "start": _WINDOW_START,
    "end": _WINDOW_END,
    "repo": _REPO,
    "events": [_AGENT_EXIT],
    "stages": [_STAGE_IMPLEMENTING],
    "issue": _ISSUE,
})


class KeywordBindingTest(unittest.TestCase):
    """One flat keyword call, sorted into the parts a family asks for."""

    def test_a_call_is_sorted_into_the_three_parts(self) -> None:
        conn = FakeConnection()
        connect = FakeConnect()
        request = bind_read_request(
            RECENT_EXITS_SIGNATURE,
            (),
            {**_FILTER_CALL, "db_url": DB_URL, "connect": connect, "conn": conn},
        )
        self.assertEqual(
            request.filters,
            ReadFilters(
                start=_WINDOW_START,
                end=_WINDOW_END,
                repo=_REPO,
                events=[_AGENT_EXIT],
                stages=[_STAGE_IMPLEMENTING],
                issue=_ISSUE,
            ),
        )
        self.assertEqual(
            request.connection,
            ReadConnection(db_url=DB_URL, connect=connect, conn=conn),
        )
        self.assertEqual(request.options, ReadOptions(limit=RECENT_EXIT_LIMIT))

    def test_each_family_applies_its_own_defaults(self) -> None:
        # The knob a caller omits is answered here rather than by the family,
        # so the recent-runs cap and the issue table's ordering cannot differ
        # between the reader and the signature its call is bound against.
        families = (
            (SOURCE_READ_SIGNATURE, ReadOptions()),
            (FILTERED_READ_SIGNATURE, ReadOptions()),
            (HEATMAP_SIGNATURE, ReadOptions()),
            (RECENT_EXITS_SIGNATURE, ReadOptions(limit=RECENT_EXIT_LIMIT)),
            (LIMITED_READ_SIGNATURE, ReadOptions(limit=_PAGE_LIMIT)),
            (
                ISSUES_SIGNATURE,
                ReadOptions(limit=_PAGE_LIMIT, sort_by=_SORT_BY_LAST_SEEN),
            ),
        )
        for signature, options in families:
            with self.subTest(options=options):
                request = bind_read_request(signature, (), {})
                self.assertEqual(request.options, options)
                self.assertEqual(request.connection, ReadConnection())

    def test_the_drilldown_demands_its_issue(self) -> None:
        # `get_issue_events` is per-issue by definition; a call missing either
        # half would otherwise read the whole window.
        with self.assertRaises(TypeError):
            bind_read_request(ISSUE_EVENTS_SIGNATURE, (), {})
        request = bind_read_request(
            ISSUE_EVENTS_SIGNATURE,
            (),
            {"repo": _REPO, "issue": _ISSUE},
        )
        self.assertEqual(request.filters.repo, _REPO)
        self.assertEqual(request.filters.issue, _ISSUE)

    def test_a_positional_argument_is_refused(self) -> None:
        # Every parameter is keyword-only, so a value passed positionally is
        # rejected rather than landing on whichever field comes first.
        with self.assertRaises(TypeError):
            bind_read_request(FILTERED_READ_SIGNATURE, (_WINDOW_START,), {})


class FilterProjectionTest(unittest.TestCase):
    """The SQL filter model a family builds its predicate from."""

    def test_the_bound_filters_reach_the_sql_model(self) -> None:
        request = bind_read_request(FILTERED_READ_SIGNATURE, (), _FILTER_CALL)
        self.assertEqual(
            window_filters(request),
            WindowFilters(
                start=_WINDOW_START,
                end=_WINDOW_END,
                repo=_REPO,
                events=[_AGENT_EXIT],
                stages=[_STAGE_IMPLEMENTING],
                issue=_ISSUE,
            ),
        )

    def test_a_scoped_projection_drops_identity(self) -> None:
        # What a query grouped by repo asks for: the window and the selections
        # still narrow it, but the repo and issue it groups over must not.
        request = bind_read_request(FILTERED_READ_SIGNATURE, (), _FILTER_CALL)
        self.assertEqual(
            window_filters(request, include_identity=False),
            WindowFilters(
                start=_WINDOW_START,
                end=_WINDOW_END,
                events=[_AGENT_EXIT],
                stages=[_STAGE_IMPLEMENTING],
            ),
        )


class ConnectionProjectionTest(unittest.TestCase):
    """The connection a family runs its SELECT on."""

    def test_the_connection_fields_reach_the_query(self) -> None:
        conn = FakeConnection()
        connect = FakeConnect()
        request = bind_read_request(
            SOURCE_READ_SIGNATURE,
            (),
            {"db_url": DB_URL, "connect": connect, "conn": conn},
        )
        query = resolve_read_query(request)
        self.assertEqual(query.db_url, DB_URL)
        self.assertIs(query.connect_fn, connect)
        self.assertIs(query.conn, conn)


if __name__ == "__main__":
    unittest.main()
