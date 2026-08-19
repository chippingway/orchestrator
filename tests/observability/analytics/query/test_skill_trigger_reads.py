# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a cohort reached for, by rate and by named skill."""
from __future__ import annotations

import unittest
from itertools import product

from orchestrator.observability.analytics.query.skill_reads import (
    get_skill_trigger_matrix,
    get_skill_trigger_rates,
)
from tests.observability.analytics.analytics_assertions import assert_row_fields, assert_sql_fragments
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

_CATALOG_SCAN = "event = 'repo_skill_catalog'"

_RATE_GROUPING = "GROUP BY role_label, backend_label"

_LEVEL_FIELD = "extras -> 'skill_levels'"

_UNKNOWN = "unknown"

_CLAUDE = "claude"

_CODEX = "codex"

_DEVELOPER = "developer"

_REVIEWER = "reviewer"

_DECOMPOSER = "decomposer"

_QUESTION = "question"

_REPO = "owner/repo"

_DEVELOP = "develop"

_REVIEW = "review"

_DOCUMENT = "document"

_DEVELOP_ONLY = (_DEVELOP,)

_PROJECT = "project"

_USER = "user"

# One `agent_exit` row of the matrix's runs scan: repo, role, backend, the
# skill names that run loaded, and the level map it was offered them under. A
# codex run reports one level per offered skill; a claude run reports none,
# since its stream names no source directory for the skills it lists.
_DEVELOP_RUN = (_REPO, _DEVELOPER, _CLAUDE, _DEVELOP_ONLY, {_DEVELOP: _PROJECT})

_SKILL_FREE_RUN = (_REPO, _DEVELOPER, _CLAUDE, None)

# One `repo_skill_catalog` row: the repository, the names it offers, and the
# level each was classified at.
_DEVELOP_CATALOG = ((_REPO, _DEVELOP_ONLY, {_DEVELOP: _PROJECT}),)

_DRILL_DOWN_ISSUE = 551

# The two reads and one row wide enough for each, so what they share -- the
# scan target and the short circuits -- is pinned once per read.
_SKILL_READS = (
    (get_skill_trigger_rates, (_DEVELOPER, _CLAUDE, 9, 3, 3)),
    (get_skill_trigger_matrix, _DEVELOP_RUN),
)

_SKILL_READ_CALLS = tuple(read for read, _row in _SKILL_READS)

# The two selections that leave a scan pinned to `agent_exit` nothing to match:
# one naming other events, and the cleared multiselect.
_EXIT_FREE_SELECTIONS = ([_STAGE_ENTER], [])


def _catalog_and_runs(catalog: tuple, runs: tuple) -> dict[str, tuple]:
    """Route the matrix's two scans to their own rows."""
    return {_CATALOG_SCAN: catalog, _EXIT_SCAN: runs}


def _matrix_cells(rows) -> dict[tuple, tuple]:
    """Index the matrix by cell, dropping the repo every fixture here shares."""
    return {
        (row.skill, row.level, row.agent_role, row.backend): (row.runs, row.skill_runs)
        for row in rows
    }


class SkillReadShortCircuitTest(unittest.TestCase):
    """What both settle before dialing, because each pins its own event."""

    def test_an_unconfigured_database_answers_empty(self) -> None:
        for read in _SKILL_READ_CALLS:
            with self.subTest(read=read.__name__), configured_db_url(None):
                self.assertEqual(read(connect=FakeConnect()), [])

    def test_a_selection_without_exits_stops(self) -> None:
        # Each scan pins `agent_exit` itself, so a selection those rows fall
        # outside of would contradict the pin -- and is answered without
        # opening a socket, the matrix's catalog scan included.
        for read, events in product(_SKILL_READ_CALLS, _EXIT_FREE_SELECTIONS):
            conn = FakeConnection()
            with self.subTest(read=read.__name__, events=events):
                with configured_db_url():
                    empty = read(events=events, connect=conn.as_connect)
                self.assertEqual(empty, [])
                self.assertEqual(conn.executed, [])

    def test_the_extras_blob_keeps_both_off_rollup(self) -> None:
        # Skill fields live in the `extras` JSONB neither the rollup nor the
        # agent-run view carries, so both reads scan the events table.
        for read, row in _SKILL_READS:
            conn = FakeConnection(rows=(row,), rows_for=_catalog_and_runs((), (row,)))
            with self.subTest(read=read.__name__), configured_db_url():
                read(connect=conn.as_connect)
            for scan_sql, _ in conn.executed:
                self.assertIn(_BASE_SCAN, scan_sql)
                self.assertNotIn(_ROLLUP_SCAN, scan_sql)
                self.assertNotIn(_VIEW_SCAN, scan_sql)


class SkillTriggerRateReadTest(unittest.TestCase):
    """How often each role-and-backend cohort reached for a skill at all."""

    def test_each_cohort_reports_against_its_own_runs(self) -> None:
        conn = FakeConnection(rows=(
            (_DEVELOPER, _CLAUDE, 9, 3, 3),
            (_REVIEWER, _CODEX, 5, 0, 0),
            (_DECOMPOSER, _CODEX, 2, 0, 0),
        ))
        with configured_db_url():
            rows = get_skill_trigger_rates(connect=conn.as_connect)
        self.assertEqual(
            [(row.agent_role, row.backend) for row in rows],
            [(_DEVELOPER, _CLAUDE), (_REVIEWER, _CODEX), (_DECOMPOSER, _CODEX)],
        )
        assert_row_fields(
            self,
            rows[0],
            {"runs": 9, "skill_runs": 3, "total_triggers": 3, "rate": 3 / 9},
        )
        # A cohort that never triggered is a real 0% rate rather than a
        # dropped category -- which is the case the panel exists to surface.
        assert_row_fields(self, rows[1], {"skill_runs": 0, "rate": float()})

    def test_the_scan_probes_and_sums_the_count(self) -> None:
        # `skill_runs` is a key-presence test, so a run that recorded an empty
        # load list still counts as one that reported; `total_triggers` sums
        # the recorded count, so a run that loaded three contributes three.
        conn = FakeConnection(rows=((_DEVELOPER, _CLAUDE, 9, 3, 3),))
        with configured_db_url():
            get_skill_trigger_rates(connect=conn.as_connect)
        scan_sql, _ = conn.executed[0]
        assert_sql_fragments(
            self,
            scan_sql,
            (
                _EXIT_SCAN,
                _RATE_GROUPING,
                "extras -> 'skills_triggered' IS NOT NULL",
                "skills_triggered_count",
            ),
        )

    def test_an_unrecorded_cohort_label_reads_unknown(self) -> None:
        conn = FakeConnection(rows=((None, None, 4, 0, 0),))
        with configured_db_url():
            rows = get_skill_trigger_rates(connect=conn.as_connect)
        assert_row_fields(
            self,
            rows[0],
            {"agent_role": _UNKNOWN, "backend": _UNKNOWN},
        )

    def test_the_window_and_repo_bind(self) -> None:
        conn = FakeConnection(rows=((_DEVELOPER, _CLAUDE, 9, 3, 3),))
        with configured_db_url():
            get_skill_trigger_rates(repo=_REPO, connect=conn.as_connect)
        scan_sql, bindings = conn.executed[0]
        self.assertIn("repo = %s", scan_sql)
        self.assertIn(_REPO, bindings)


class SkillMatrixScopeTest(unittest.TestCase):
    """Which selection reaches which of the matrix's two scans."""

    def test_the_repo_narrows_both_scans(self) -> None:
        conn = FakeConnection(rows_for=_catalog_and_runs(
            _DEVELOP_CATALOG,
            (_DEVELOP_RUN,),
        ))
        with configured_db_url():
            get_skill_trigger_matrix(repo=_REPO, connect=conn.as_connect)
        for scan_sql, bindings in conn.executed:
            self.assertIn("repo = %s", scan_sql)
            self.assertIn(_REPO, bindings)

    def test_the_run_selection_spares_the_catalog(self) -> None:
        # A catalog record is a repository-level fact -- no issue, no stage,
        # and written whenever the catalog was last scanned -- so pushing the
        # window, issue, or stage selection onto it would drop every row and
        # silently collapse the padding.
        conn = FakeConnection(rows_for=_catalog_and_runs(
            _DEVELOP_CATALOG,
            (_DEVELOP_RUN,),
        ))
        with configured_db_url():
            get_skill_trigger_matrix(
                issue=_DRILL_DOWN_ISSUE,
                stages=["implementing"],
                connect=conn.as_connect,
            )
        catalog_sql, catalog_bindings = conn.executed[0]
        run_sql, run_bindings = conn.executed[1]
        self.assertNotIn("issue = %s", catalog_sql)
        self.assertNotIn("stage IN", catalog_sql)
        self.assertEqual(catalog_bindings, ())
        self.assertIn("issue = %s", run_sql)
        self.assertIn("stage IN", run_sql)
        self.assertIn(_DRILL_DOWN_ISSUE, run_bindings)
        self.assertIn("implementing", run_bindings)

    def test_each_scan_reads_its_own_skill_field(self) -> None:
        # Both scans read the recorded levels beside the names they differ
        # over, since a cell is filed under the two together.
        conn = FakeConnection(rows_for=_catalog_and_runs(
            _DEVELOP_CATALOG,
            (_DEVELOP_RUN,),
        ))
        with configured_db_url():
            get_skill_trigger_matrix(connect=conn.as_connect)
        catalog_sql, _ = conn.executed[0]
        run_sql, _ = conn.executed[1]
        assert_sql_fragments(
            self,
            catalog_sql,
            ("extras -> 'skills_available'", _LEVEL_FIELD),
        )
        assert_sql_fragments(
            self,
            run_sql,
            (
                _EXIT_SCAN,
                "extras -> 'skills_triggered'",
                _LEVEL_FIELD,
                "COALESCE(agent_role, 'unknown')",
                "COALESCE(backend, 'unknown')",
            ),
        )


class SkillMatrixCellTest(unittest.TestCase):
    """Which cells exist, what each counts, and which survive the cap."""

    def test_the_catalog_pads_every_running_cohort(self) -> None:
        # A skill on offer that a cohort never triggered is an explicit zero
        # rather than a missing row, for every cohort that ran -- a decomposer
        # or question run emits `agent_exit` like any other, and a run that
        # recorded neither label is its own cohort under `unknown` rather than
        # one dropped for having nothing to group by.
        conn = FakeConnection(rows_for=_catalog_and_runs(
            _DEVELOP_CATALOG,
            (
                _DEVELOP_RUN,
                (_REPO, _DECOMPOSER, _CLAUDE, None),
                (_REPO, _QUESTION, _CODEX, None),
                (_REPO, None, None, _DEVELOP_ONLY, {_DEVELOP: _PROJECT}),
            ),
        ))
        with configured_db_url():
            rows = get_skill_trigger_matrix(connect=conn.as_connect)
        cells = _matrix_cells(rows)
        self.assertEqual(cells[(_DEVELOP, _PROJECT, _DEVELOPER, _CLAUDE)], (1, 1))
        self.assertEqual(cells[(_DEVELOP, _PROJECT, _DECOMPOSER, _CLAUDE)], (1, 0))
        self.assertEqual(cells[(_DEVELOP, _PROJECT, _QUESTION, _CODEX)], (1, 0))
        self.assertEqual(cells[(_DEVELOP, _PROJECT, _UNKNOWN, _UNKNOWN)], (1, 1))
        self.assertEqual({row.repo for row in rows}, {_REPO})

    def test_an_uncatalogued_skill_keeps_its_cell(self) -> None:
        # What ran is not discarded for disagreeing with what was offered; it
        # simply earns no zeros elsewhere. Both cells read against the same
        # cohort size, so a low trigger count stays legible.
        conn = FakeConnection(rows_for=_catalog_and_runs(
            ((_REPO, (_REVIEW,), {_REVIEW: _PROJECT}),),
            (_DEVELOP_RUN, _SKILL_FREE_RUN),
        ))
        with configured_db_url():
            rows = get_skill_trigger_matrix(connect=conn.as_connect)
        cells = _matrix_cells(rows)
        self.assertEqual(cells[(_DEVELOP, _PROJECT, _DEVELOPER, _CLAUDE)], (2, 1))
        self.assertEqual(cells[(_REVIEW, _PROJECT, _DEVELOPER, _CLAUDE)], (2, 0))

    def test_a_missing_catalog_leaves_observed_cells(self) -> None:
        # No catalog record matches, so the matrix degrades to what was
        # observed rather than inventing zero rows or raising -- and a cohort
        # that triggered nothing contributes no cell at all.
        conn = FakeConnection(rows_for={_EXIT_SCAN: (
            _DEVELOP_RUN,
            (_REPO, _REVIEWER, _CODEX, None),
        )})
        with configured_db_url():
            rows = get_skill_trigger_matrix(connect=conn.as_connect)
        self.assertEqual(
            [(row.skill, row.level, row.agent_role, row.backend) for row in rows],
            [(_DEVELOP, _PROJECT, _DEVELOPER, _CLAUDE)],
        )
        # Both scans still ran; only the catalog one came back empty.
        self.assertEqual(len(conn.executed), 2)

    def test_a_cell_is_keyed_by_name_and_level(self) -> None:
        # One name at two levels is two definitions, so the cohort's loads of
        # each report as their own cells rather than one blended average -- a
        # run that classified nothing (a record written before levels, or a
        # claude run whose stream names no source directory) under `unknown`.
        # The catalog record classified nothing either, and still pads at
        # `project`: that scan reads a repository's own checked-in definitions.
        conn = FakeConnection(rows_for=_catalog_and_runs(
            ((_REPO, _DEVELOP_ONLY, None),),
            (
                (_REPO, _DEVELOPER, _CLAUDE, _DEVELOP_ONLY, {_DEVELOP: _USER}),
                (_REPO, _DEVELOPER, _CLAUDE, _DEVELOP_ONLY, None),
            ),
        ))
        with configured_db_url():
            rows = get_skill_trigger_matrix(connect=conn.as_connect)
        cells = _matrix_cells(rows)
        self.assertEqual(cells[(_DEVELOP, _USER, _DEVELOPER, _CLAUDE)], (2, 1))
        self.assertEqual(cells[(_DEVELOP, _UNKNOWN, _DEVELOPER, _CLAUDE)], (2, 1))
        self.assertEqual(cells[(_DEVELOP, _PROJECT, _DEVELOPER, _CLAUDE)], (2, 0))

    def test_skill_names_parse_from_raw_json_text(self) -> None:
        # A driver or fixture that hands the JSONB arrays and maps back as
        # text rather than as adapted objects still parses, on both scans.
        conn = FakeConnection(rows_for=_catalog_and_runs(
            (
                (
                    _REPO,
                    '["develop", "review"]',
                    '{"develop": "project", "review": "project"}',
                ),
            ),
            ((_REPO, _DEVELOPER, _CLAUDE, '["develop"]', '{"develop": "project"}'),),
        ))
        with configured_db_url():
            rows = get_skill_trigger_matrix(connect=conn.as_connect)
        cells = _matrix_cells(rows)
        self.assertEqual(cells[(_DEVELOP, _PROJECT, _DEVELOPER, _CLAUDE)], (1, 1))
        self.assertEqual(cells[(_REVIEW, _PROJECT, _DEVELOPER, _CLAUDE)], (1, 0))

    def test_the_busiest_cell_and_cohort_rank_first(self) -> None:
        # Triggered runs first, then cohort size, then the stable
        # repo / role / backend / skill / level tiebreak.
        levels = {_DEVELOP: _PROJECT, _REVIEW: _PROJECT}
        reviewer_run = (_REPO, _REVIEWER, _CODEX, _DEVELOP_ONLY, levels)
        conn = FakeConnection(rows_for=_catalog_and_runs(
            ((_REPO, (_DEVELOP, _REVIEW), levels),),
            (
                _DEVELOP_RUN,
                _DEVELOP_RUN,
                _SKILL_FREE_RUN,
                reviewer_run,
                reviewer_run,
            ),
        ))
        with configured_db_url():
            rows = get_skill_trigger_matrix(connect=conn.as_connect)
        self.assertEqual(
            [
                (row.skill, row.agent_role, row.backend, row.runs, row.skill_runs)
                for row in rows
            ],
            [
                (_DEVELOP, _DEVELOPER, _CLAUDE, 3, 2),
                (_DEVELOP, _REVIEWER, _CODEX, 2, 2),
                (_REVIEW, _DEVELOPER, _CLAUDE, 3, 0),
                (_REVIEW, _REVIEWER, _CODEX, 2, 0),
            ],
        )

    def test_the_cap_keeps_the_top_of_that_ranking(self) -> None:
        review_run = (_REPO, _DEVELOPER, _CLAUDE, (_REVIEW,), {_REVIEW: _PROJECT})
        conn = FakeConnection(rows_for=_catalog_and_runs(
            ((_REPO, (_DEVELOP, _REVIEW, _DOCUMENT), None),),
            (_DEVELOP_RUN, review_run, review_run),
        ))
        with configured_db_url():
            capped = get_skill_trigger_matrix(limit=2, connect=conn.as_connect)
            uncapped = get_skill_trigger_matrix(limit=0, connect=conn.as_connect)
        self.assertEqual(
            [(row.skill, row.skill_runs) for row in capped],
            [(_REVIEW, 2), (_DEVELOP, 1)],
        )
        # A non-positive cap means every cell, not no rows.
        self.assertEqual(len(uncapped), 3)


if __name__ == "__main__":
    unittest.main()
