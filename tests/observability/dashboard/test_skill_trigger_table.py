# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The panel each cohort's skill-trigger rate is reported in.

The cases name what the panel decides rather than what the shared table draws:
the six columns an operator reads across, the whole-point percentage a rate is
reported as, the bar that percentage is drawn against the busiest cohort in the
table by, and the label a cohort the sink named no role or backend for is read
under. A cohort that triggered nothing is here too, because a quiet role is the
reading this panel exists to report rather than a row it drops.
"""

from __future__ import annotations

import unittest
from dataclasses import dataclass

from orchestrator.observability.analytics.query.skill_models import (
    SkillTriggerRateRow,
)
from orchestrator.observability.dashboard import skill_trigger_table

_DEVELOPER = "developer"

_REVIEWER = "reviewer"

_CLAUDE = "claude"

_CODEX = "codex"

_ROLE_WITH_MARKUP = "dev<&>"

# A cohort that triggered a skill on one run in four, so the rounded percentage
# is readable off the rendered markup.
_QUARTER_RUNS = 4

_ONE_RUN = 1

_QUARTER_PCT = ">25%<"

# The busiest cohort in a case and the one drawn at half its rate.
_BUSY_RUNS = 10

_HALF_SKILL_RUNS = 5

_FULL_WIDTH = "width:100.0%"

_HALF_WIDTH = "width:50.0%"

_EMPTY_WIDTH = "width:0.0%"

_QUIET_RUNS = 5


@dataclass(frozen=True)
class _CohortCase:
    role: str = _DEVELOPER
    backend: str = _CLAUDE
    runs: int = _BUSY_RUNS
    skill_runs: int = _BUSY_RUNS
    triggers: int = _BUSY_RUNS


def _row(case: _CohortCase) -> SkillTriggerRateRow:
    """One read row of the aggregate a cohort is counted into."""
    return SkillTriggerRateRow(
        agent_role=case.role,
        backend=case.backend,
        runs=case.runs,
        skill_runs=case.skill_runs,
        total_triggers=case.triggers,
    )


def _rendered(*cases: _CohortCase) -> str:
    """The panel those cohorts are reported in."""
    return skill_trigger_table.skill_triggers_html(
        [_row(case) for case in cases],
    )


class SkillTriggersHtmlTest(unittest.TestCase):
    """What the panel reports across its six columns, and how it is sized."""

    def test_every_column_is_headed(self) -> None:
        rendered = _rendered(_CohortCase())
        for header, _aligned in skill_trigger_table.SKILL_TRIGGERS_TABLE_COLUMNS:
            with self.subTest(header=header):
                self.assertIn(f">{header}<", rendered)

    def test_a_rate_is_reported_in_whole_points(self) -> None:
        rendered = _rendered(
            _CohortCase(runs=_QUARTER_RUNS, skill_runs=_ONE_RUN, triggers=_ONE_RUN),
        )
        self.assertIn(_QUARTER_PCT, rendered)

    def test_a_bar_is_a_share_of_the_busiest_cohort(self) -> None:
        rendered = _rendered(
            _CohortCase(),
            _CohortCase(
                role=_REVIEWER,
                backend=_CODEX,
                skill_runs=_HALF_SKILL_RUNS,
                triggers=_HALF_SKILL_RUNS,
            ),
        )
        self.assertIn(_FULL_WIDTH, rendered)
        self.assertIn(_HALF_WIDTH, rendered)

    def test_a_quiet_cohort_still_reports(self) -> None:
        # There is no busiest cohort to be a share of, so the panel divides by
        # one and renders the quiet role as an explicit zero.
        rendered = _rendered(
            _CohortCase(
                role=_REVIEWER,
                backend=_CODEX,
                runs=_QUIET_RUNS,
                skill_runs=0,
                triggers=0,
            ),
        )
        self.assertIn(">0%<", rendered)
        self.assertIn(_EMPTY_WIDTH, rendered)

    def test_an_empty_category_reads_unknown(self) -> None:
        rendered = _rendered(_CohortCase(role="", backend=""))
        self.assertEqual(
            rendered.count(f">{skill_trigger_table.UNKNOWN}<"), 2,
        )

    def test_the_role_is_named_and_escaped(self) -> None:
        rendered = _rendered(_CohortCase(role=_ROLE_WITH_MARKUP))
        self.assertIn("dev&lt;&amp;&gt;", rendered)
        self.assertNotIn(_ROLE_WITH_MARKUP, rendered)


if __name__ == "__main__":
    unittest.main()
