# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""One logical session's identity, and the evidence gathered under it.

Adoption is a per-session question, not a per-run one: an agent that resumes
four times has adopted a skill once, not four times. A row's session is
therefore its `resume_session_id` when it has one -- a continuation belongs to
the session it continued -- its own `session_id` otherwise, and its primary key
when it carries neither, so an ID-less row from an older record or a CLI
hiccup stays its own session rather than merging into one anonymous bucket. The
primary key is stable across both scans below, so a shared ID-less row keys the
same in each.

Two scans feed one aggregate, and they are scoped differently on purpose. The
window scan is the reporting window as the caller selected it, and it decides
*which* sessions are counted at all. The history scan then reads every finished
run of those sessions before the window ends -- dropping the start bound and
the stage filter, keeping the end bound -- because a skill loaded in an earlier
stage or before the window still means the session adopted it, while a load
after the window ends has not happened yet from this page's point of view.
History rows for sessions the window never saw are dropped: their evidence
belongs to a window nobody asked about.

What a session accumulates is set-based on both sides, so folding a row twice
-- a window row is also returned by the history scan -- never double counts.
Every skill it accumulates is a name/level pair read off the row that reported
it, so an offer and a load are matched by provenance as well as by name.
Availability is tracked by JSON key presence rather than by a non-empty array,
which is what separates "scanned, found none" from "never reported": the first
is metadata that blocks the legacy fallback below, the second is not.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from orchestrator.observability.analytics.query.conditions import (
    AGENT_EXIT_CONDITION,
    append_where_condition,
)
from orchestrator.observability.analytics.query.execution import ReadQuery
from orchestrator.observability.analytics.query.filters import WindowFilters
from orchestrator.observability.analytics.query.predicates import build_window_where
from orchestrator.observability.analytics.query.row_cells import row_value
from orchestrator.observability.analytics.query.skill_values import (
    SkillCohort,
    SkillLevelPair,
    leveled_skills,
    skill_cohort,
)

# Where the identity columns sit in both scans' SELECT lists, which share their
# leading six columns so one session key is read the same way off either row.
SESSION_RESUME_INDEX = 3
SESSION_ID_INDEX = 4
SESSION_ROW_INDEX = 5


def skill_session_key(row: Sequence[Any]) -> str:
    """Identify a row's logical session: resume id, then session id, then row.

    A resumed run continues the session it resumed *from*, so the
    `resume_session_id` groups a continuation with its origin; a fresh run
    keys on its own `session_id`. A row carrying neither (an older record,
    or a CLI hiccup that yielded no id) falls back to its primary key so
    every ID-less row stays its own session -- never silently merged into a
    single anonymous bucket. The primary key is stable across the window
    and history scans, so a shared ID-less row keys the same in both.
    """
    resume = row_value(row, SESSION_RESUME_INDEX, None)
    if isinstance(resume, str) and resume:
        return resume
    session = row_value(row, SESSION_ID_INDEX, None)
    if isinstance(session, str) and session:
        return session
    return f"row:{row_value(row, SESSION_ROW_INDEX, None)}"


@dataclass
class SessionEvidence:
    """One logical session's availability + load evidence before window end.

    `available` unions every `skills_available` set the session reported;
    `has_availability_meta` records whether any row carried the
    `skills_available` *key* at all -- tracked by JSON key presence, not by
    a non-empty array, so an explicit `skills_available: []` ("scanned,
    found none") still registers as metadata. `adopted` unions the skills
    the session loaded across its rows. Both sets hold name/level pairs, so
    a load is credited to the offer of the same provenance rather than to
    a same-named skill from another level. All three are set-based, so
    folding the same row twice (a window row is also returned by the
    history scan) never double-counts.
    """

    available: set[SkillLevelPair] = field(default_factory=set)
    adopted: set[SkillLevelPair] = field(default_factory=set)
    has_availability_meta: bool = False

    def observe(
        self,
        *,
        available: Iterable[SkillLevelPair],
        available_present: bool,
        triggered: Iterable[SkillLevelPair],
    ) -> None:
        # `available_present` is the JSON key presence, kept apart from the
        # parsed pairs: an explicit empty `skills_available` is metadata that
        # blocks the legacy-load fallback, while an absent key is not.
        if available_present:
            self.has_availability_meta = True
        self.available.update(available)
        self.adopted.update(triggered)

    def resolved_available(self) -> set[SkillLevelPair]:
        """Skills that count toward this session's denominator.

        The reported `skills_available` union when the session carried any
        availability metadata; otherwise the loaded skills themselves -- a
        legacy load recorded before availability metadata existed implies
        the skill was offered, so it still counts in the denominator. An
        explicit empty `skills_available` is metadata, so it does *not* fall
        back: a load against a session that reported no offered skills does
        not fabricate availability.
        """
        if self.has_availability_meta:
            return self.available
        return set(self.adopted)


@dataclass(frozen=True)
class SkillWindowRun:
    """One reporting-window `agent_exit` row's session + skill fields."""

    session_key: str
    cohort: SkillCohort
    triggered: frozenset[SkillLevelPair]
    incidental: frozenset[SkillLevelPair]


def skill_window_run(row: Sequence[Any]) -> SkillWindowRun:
    """Project one window scan row onto its session, cohort, and skills."""
    levels = row_value(row, 8, None)
    return SkillWindowRun(
        session_key=skill_session_key(row),
        cohort=skill_cohort(row),
        triggered=leveled_skills(row_value(row, 6, None), levels),
        incidental=leveled_skills(row_value(row, 7, None), levels),
    )


def skill_window_rows(
    query: ReadQuery,
    filters: WindowFilters,
) -> list[SkillWindowRun]:
    """Scan the finished runs the caller's window selected."""
    window_where, window_bindings = build_window_where(filters.without_events())
    clause = append_where_condition(window_where, AGENT_EXIT_CONDITION)
    rows = query.select(
        "SELECT repo, "
        "COALESCE(agent_role, 'unknown') AS role_label, "
        "COALESCE(backend, 'unknown') AS backend_label, "
        "resume_session_id, session_id, id, "
        "extras -> 'skills_triggered' AS skills_triggered, "
        "extras -> 'skills_incidental' AS skills_incidental, "
        "extras -> 'skill_levels' AS skill_levels "
        f"FROM analytics_events{clause}",
        window_bindings,
    )
    return [skill_window_run(row) for row in rows]


def skill_history_rows(
    query: ReadQuery,
    filters: WindowFilters,
) -> list[tuple]:
    """Scan every finished run before the window ends, at any stage."""
    history_where, history_bindings = build_window_where(
        filters.historical_scope(),
    )
    clause = append_where_condition(history_where, AGENT_EXIT_CONDITION)
    return query.select(
        "SELECT repo, "
        "COALESCE(agent_role, 'unknown') AS role_label, "
        "COALESCE(backend, 'unknown') AS backend_label, "
        "resume_session_id, session_id, id, "
        "extras -> 'skills_available' AS skills_available, "
        "(extras -> 'skills_available') IS NOT NULL AS has_skills_available, "
        "extras -> 'skills_triggered' AS skills_triggered, "
        "extras -> 'skill_levels' AS skill_levels "
        f"FROM analytics_events{clause}",
        history_bindings,
    )


def skill_session_evidence(
    query: ReadQuery,
    filters: WindowFilters,
    window_runs: Sequence[SkillWindowRun],
) -> dict[str, SessionEvidence]:
    """Gather each active session's before-window-end availability + loads.

    Seeds one `SessionEvidence` per window session (a window row is itself
    evidence observed before the end) so only sessions active in the window
    are tracked, then folds in the history scan -- every `agent_exit` row
    for those sessions before the window end, ignoring the window start and
    stage filter -- so a load from a prior stage or from before the window
    stays visible. History rows for sessions not seen in the window are
    dropped: their evidence must not leak into the aggregate.
    """
    evidence: dict[str, SessionEvidence] = {}
    for run in window_runs:
        evidence.setdefault(run.session_key, SessionEvidence()).observe(
            available=(),
            available_present=False,
            triggered=run.triggered,
        )
    for row in skill_history_rows(query, filters):
        session = evidence.get(skill_session_key(row))
        if session is None:
            continue
        levels = row_value(row, 9, None)
        session.observe(
            available=leveled_skills(row_value(row, 6, None), levels),
            available_present=bool(row_value(row, 7, False)),
            triggered=leveled_skills(row_value(row, 8, None), levels),
        )
    return evidence
