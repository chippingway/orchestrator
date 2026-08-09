# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""How many sessions that could have used a skill actually did."""
from __future__ import annotations

import unittest
from datetime import datetime, timezone

from orchestrator.observability.analytics.query.skill_reads import get_skill_adoption
from tests.observability.analytics.analytics_assertions import assert_column_values, assert_row_fields
from tests.observability.analytics.query.query_fake_driver import (
    FakeConnect,
    FakeConnection,
)
from tests.observability.analytics.query.query_test_support import configured_db_url

_STAGE_ENTER = "stage_enter"

_BASE_SCAN = "FROM analytics_events"

_ROLLUP_SCAN = "FROM analytics_daily_rollup"

_VIEW_SCAN = "FROM analytics_agent_runs"

_EXIT_SCAN = "event = 'agent_exit'"

# The fragment unique to each of the two scans: only the window one reads the
# incidental references, only the history one reads the offered set.
_WINDOW_SCAN = "skills_incidental"

_HISTORY_SCAN = "skills_available"

_UNKNOWN = "unknown"

_CLAUDE = "claude"

_DEVELOPER = "developer"

_REPO = "owner/repo"

_DEVELOP = "develop"

_REVIEW = "review"

_DEVELOP_ONLY = (_DEVELOP,)

_ANCHOR = "anchor"

_SESSION_ONE = "s1"

_YEAR = 2026

_WINDOW_START = datetime(_YEAR, 6, 1, tzinfo=timezone.utc)

_WINDOW_END = datetime(_YEAR, 6, 24, tzinfo=timezone.utc)

# The two selections that leave a scan pinned to `agent_exit` nothing to match.
_EXIT_FREE_SELECTIONS = ([_STAGE_ENTER], [])

# Four resume-anchored sessions as `(anchor, runs, loads)`, chosen so the
# counters a cell carries come out different from one another: a chain of runs
# adopts once, and only the runs that loaded the skill leave a load row.
_SESSION_CHAINS = (
    ("one-load", 3, 1),
    ("two-loads", 3, 2),
    ("quiet-long", 3, 0),
    ("quiet-short", 2, 0),
)

# One entry per run those chains describe: the anchor it belongs to, and
# whether that run loaded the skill.
_CHAIN_RUNS = tuple(
    (anchor, run < loads)
    for anchor, runs, loads in _SESSION_CHAINS
    for run in range(runs)
)

# What the chains add up to on the window side: 3 + 3 + 3 + 2 invocations.
_CHAIN_INVOCATIONS = 11


def _window_row(**row_fields: object) -> tuple:
    """A reporting-window `agent_exit` scan row (identity + skill names)."""
    row = [
        row_fields.get("repo", _REPO),
        row_fields.get("role", _DEVELOPER),
        row_fields.get("backend", _CLAUDE),
        row_fields.get("resume"),
        row_fields.get("session"),
        row_fields["row_id"],
        row_fields.get("triggered"),
        row_fields.get("incidental"),
    ]
    return tuple(row)


def _history_row(**row_fields: object) -> tuple:
    """A before-window-end `agent_exit` scan row (availability + loads).

    `available_present` mirrors the SQL `(extras -> 'skills_available') IS
    NOT NULL` key-presence flag; it defaults to "the array is not None" so a
    caller passing `available=()` models an explicit empty offered-set while
    `available=None` models an absent key.
    """
    available = row_fields.get("available")
    available_present = row_fields.get("available_present")
    if available_present is None:
        available_present = available is not None
    row = [
        row_fields.get("repo", _REPO),
        row_fields.get("role", _DEVELOPER),
        row_fields.get("backend", _CLAUDE),
        row_fields.get("resume"),
        row_fields.get("session"),
        row_fields["row_id"],
        available,
        available_present,
        row_fields.get("triggered"),
    ]
    return tuple(row)


def _chain_scans() -> tuple[tuple, tuple]:
    """Build both scans' rows for the declared resume-anchored chains.

    Every run carries its own `session_id` and its chain's `resume_session_id`,
    so the chain reads as one logical session however many runs it holds.
    """
    return (
        tuple(
            _window_row(
                row_id=row_id,
                resume=anchor,
                session=f"run-{row_id}",
                triggered=_DEVELOP_ONLY if loaded else None,
            )
            for row_id, (anchor, loaded) in enumerate(_CHAIN_RUNS, start=1)
        ),
        tuple(
            _history_row(
                row_id=row_id,
                resume=anchor,
                session=f"run-{row_id}",
                available=_DEVELOP_ONLY,
                triggered=_DEVELOP_ONLY if loaded else None,
            )
            for row_id, (anchor, loaded) in enumerate(_CHAIN_RUNS, start=1)
        ),
    )


def _assert_one_cell(
    test_case,
    window: tuple,
    history: tuple,
    **expected_fields: object,
) -> None:
    """Run the read over its two scans and check the one cell it answers with."""
    conn = FakeConnection(rows_for={_WINDOW_SCAN: window, _HISTORY_SCAN: history})
    with configured_db_url():
        rows = get_skill_adoption(connect=conn.as_connect)
    assert_column_values(
        test_case,
        rows,
        {name: [expected] for name, expected in expected_fields.items()},
    )


class SkillAdoptionScanTest(unittest.TestCase):
    """What the read settles before dialing, and what each scan reaches."""

    def test_an_unconfigured_database_answers_empty(self) -> None:
        with configured_db_url(None):
            self.assertEqual(get_skill_adoption(connect=FakeConnect()), [])

    def test_a_selection_without_exits_stops(self) -> None:
        # Both scans pin `agent_exit` themselves, so a selection those rows
        # fall outside of is answered without opening a socket.
        for events in _EXIT_FREE_SELECTIONS:
            conn = FakeConnection()
            with self.subTest(events=events):
                with configured_db_url():
                    empty = get_skill_adoption(events=events, connect=conn.as_connect)
                self.assertEqual(empty, [])
                self.assertEqual(conn.executed, [])

    def test_the_history_drops_start_and_stage(self) -> None:
        # A skill loaded in an earlier stage or before the window still means
        # the session adopted it, so the history scan keeps only the end bound
        # -- a later load must not leak backward into this window's answer.
        conn = FakeConnection()
        with configured_db_url():
            get_skill_adoption(
                start=_WINDOW_START,
                end=_WINDOW_END,
                stages=["implementing"],
                connect=conn.as_connect,
            )
        window_sql, window_bindings = conn.executed[0]
        history_sql, history_bindings = conn.executed[1]
        self.assertIn("ts >= %s", window_sql)
        self.assertIn("stage IN", window_sql)
        self.assertIn(_WINDOW_START, window_bindings)
        self.assertNotIn("ts >= %s", history_sql)
        self.assertNotIn("stage IN", history_sql)
        self.assertIn("ts < %s", history_sql)
        self.assertIn(_WINDOW_END, history_bindings)
        self.assertNotIn(_WINDOW_START, history_bindings)

    def test_both_scans_stay_on_the_events_table(self) -> None:
        # The `extras` blob these fields live in is carried by neither the
        # rollup nor the agent-run view, and the repository filter narrows
        # both scans so evidence from elsewhere cannot join the aggregate.
        conn = FakeConnection()
        with configured_db_url():
            get_skill_adoption(repo=_REPO, connect=conn.as_connect)
        for scan_sql, bindings in conn.executed:
            self.assertIn(_BASE_SCAN, scan_sql)
            self.assertIn(_EXIT_SCAN, scan_sql)
            self.assertIn(_REPO, bindings)
            self.assertNotIn(_ROLLUP_SCAN, scan_sql)
            self.assertNotIn(_VIEW_SCAN, scan_sql)


class SkillAdoptionSessionTest(unittest.TestCase):
    """Which rows are one session, and which are several."""

    def test_a_resumed_chain_is_one_session(self) -> None:
        # Two runs sharing a resume id adopt once between them, while both
        # their window invocations and load rows still count.
        _assert_one_cell(
            self,
            (
                _window_row(row_id=1, resume=_ANCHOR, session="a", triggered=_DEVELOP_ONLY),
                _window_row(row_id=2, resume=_ANCHOR, session="b", triggered=_DEVELOP_ONLY),
            ),
            (
                _history_row(
                    row_id=1,
                    resume=_ANCHOR,
                    session="a",
                    available=_DEVELOP_ONLY,
                    triggered=_DEVELOP_ONLY,
                ),
                _history_row(
                    row_id=2,
                    resume=_ANCHOR,
                    session="b",
                    available=_DEVELOP_ONLY,
                    triggered=_DEVELOP_ONLY,
                ),
            ),
            sessions=1,
            adopted=1,
            invocations=2,
            load_rows=2,
        )

    def test_every_idless_row_is_its_own_session(self) -> None:
        # A row carrying no id falls back to its primary key rather than
        # merging into one anonymous bucket: three sessions, two adopting.
        _assert_one_cell(
            self,
            (
                _window_row(row_id=1, triggered=_DEVELOP_ONLY),
                _window_row(row_id=2, triggered=_DEVELOP_ONLY),
                _window_row(row_id=3),
            ),
            (
                _history_row(row_id=1, available=_DEVELOP_ONLY, triggered=_DEVELOP_ONLY),
                _history_row(row_id=2, available=_DEVELOP_ONLY, triggered=_DEVELOP_ONLY),
                _history_row(row_id=3, available=_DEVELOP_ONLY),
            ),
            sessions=3,
            adopted=2,
            invocations=3,
            load_rows=2,
        )

    def test_a_pre_window_load_counts_as_adoption(self) -> None:
        # The in-window run resumed a session whose earlier run loaded the
        # skill, so the session is adopted even though the window shows no
        # load row of its own.
        _assert_one_cell(
            self,
            (_window_row(row_id=2, resume="sess-A", session="sess-B"),),
            (
                _history_row(
                    row_id=1,
                    session="sess-A",
                    available=_DEVELOP_ONLY,
                    triggered=_DEVELOP_ONLY,
                ),
                _history_row(
                    row_id=2,
                    resume="sess-A",
                    session="sess-B",
                    available=_DEVELOP_ONLY,
                ),
            ),
            sessions=1,
            adopted=1,
            invocations=1,
            load_rows=0,
        )

    def test_an_unrecorded_cohort_label_reads_unknown(self) -> None:
        _assert_one_cell(
            self,
            (
                _window_row(
                    row_id=1,
                    role=None,
                    backend=None,
                    session=_SESSION_ONE,
                    triggered=_DEVELOP_ONLY,
                ),
            ),
            (
                _history_row(
                    row_id=1,
                    role=None,
                    backend=None,
                    session=_SESSION_ONE,
                    available=_DEVELOP_ONLY,
                    triggered=_DEVELOP_ONLY,
                ),
            ),
            agent_role=_UNKNOWN,
            backend=_UNKNOWN,
        )


class SkillAdoptionDenominatorTest(unittest.TestCase):
    """Which sessions count as having been offered a skill at all."""

    def test_a_load_without_metadata_implies_offer(self) -> None:
        # A load recorded before availability metadata existed implies the
        # skill was offered, so it counts in the denominator; the equally
        # metadata-less session that loaded nothing fabricates none.
        _assert_one_cell(
            self,
            (
                _window_row(row_id=1, session="legacy", triggered=_DEVELOP_ONLY),
                _window_row(row_id=2, session="quiet"),
            ),
            (
                _history_row(row_id=1, session="legacy", triggered=_DEVELOP_ONLY),
                _history_row(row_id=2, session="quiet"),
            ),
            skill=_DEVELOP,
            sessions=1,
            adopted=1,
        )

    def test_an_empty_offer_blocks_that_implication(self) -> None:
        # "Scanned, found none" is metadata: the key is present and the array
        # empty, so a load against it must not fabricate availability -- while
        # the load itself stays a visible diagnostic row.
        _assert_one_cell(
            self,
            (
                _window_row(row_id=1, session="empty", triggered=_DEVELOP_ONLY),
                _window_row(row_id=2, session="offered", triggered=_DEVELOP_ONLY),
            ),
            (
                _history_row(
                    row_id=1,
                    session="empty",
                    available=(),
                    triggered=_DEVELOP_ONLY,
                ),
                _history_row(
                    row_id=2,
                    session="offered",
                    available=_DEVELOP_ONLY,
                    triggered=_DEVELOP_ONLY,
                ),
            ),
            sessions=1,
            adopted=1,
            load_rows=2,
        )

    def test_the_four_counters_stay_apart(self) -> None:
        # Sessions offered, sessions adopting, window invocations, and load
        # rows each answer a different question, so a cohort of chained runs
        # has to report four different numbers rather than one restated.
        window, history = _chain_scans()
        _assert_one_cell(
            self,
            window,
            history,
            repo=_REPO,
            skill=_DEVELOP,
            agent_role=_DEVELOPER,
            backend=_CLAUDE,
            sessions=4,
            adopted=2,
            invocations=_CHAIN_INVOCATIONS,
            load_rows=3,
            adoption_rate=2 / 4,
        )

    def test_an_incidental_stays_a_diagnostic(self) -> None:
        # A path-only mention never becomes availability or adoption, but its
        # own cell stays visible against the cohort's run count -- which is
        # how a skill nobody was offered still shows up as noticed.
        conn = FakeConnection(rows_for={
            _WINDOW_SCAN: (
                _window_row(
                    row_id=1,
                    session=_SESSION_ONE,
                    triggered=_DEVELOP_ONLY,
                    incidental=(_REVIEW,),
                ),
            ),
            _HISTORY_SCAN: (
                _history_row(
                    row_id=1,
                    session=_SESSION_ONE,
                    available=_DEVELOP_ONLY,
                    triggered=_DEVELOP_ONLY,
                ),
            ),
        })
        with configured_db_url():
            rows = get_skill_adoption(connect=conn.as_connect)
        by_skill = {row.skill: row for row in rows}
        assert_row_fields(
            self,
            by_skill[_DEVELOP],
            {"sessions": 1, "adopted": 1, "load_rows": 1, "incidental": 0},
        )
        assert_row_fields(
            self,
            by_skill[_REVIEW],
            {"sessions": 0, "adopted": 0, "invocations": 1, "incidental": 1},
        )


if __name__ == "__main__":
    unittest.main()
