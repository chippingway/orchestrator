# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a run of the page is narrowed by, and the load that narrowing opens.

The top of the page is one pass, and these cases follow it in order: what the
sidebar offers and answers with, the zone the session carries between reruns,
the normalization those raw selections go through, the order the whole band is
drawn in, and the staged plan the panels below are read through.

The bar the days are picked in is the date owner's and pinned there, so it is
patched here and recorded among the widgets around it -- what these cases are
about is where it sits in the pass and what the window it hands back is spent
on. The reads themselves are never issued: the cache decorator hands each
reader straight back, so a staged wave can be read as the key each entry was
bound to.
"""

from __future__ import annotations

import unittest
from time import perf_counter
from unittest.mock import patch

from orchestrator.observability.analytics.query.overview_models import (
    FilterOptions,
)
from orchestrator.observability.dashboard import (
    date_filter,
    filters,
    page_controls,
    page_models,
    read_mode,
    windows,
)
from tests.observability.dashboard import dashboard_test_support as fixtures
from tests.observability.dashboard import page_controls_test_support as fakes


_REPOS = ("owner/one", "owner/two")

_EVENTS = ("agent_exit", "stage_entered")

_STAGES = ("implementing", "validating")

# The vocabulary the sidebar is offered, read off the whole database rather
# than off the window the bar beside it picks.
_OPTIONS = FilterOptions(repos=_REPOS, events=_EVENTS, stages=_STAGES)

_EXTENT = fixtures.data_extent(fixtures.MAY01, fixtures.MAY28)

# What the patched bar hands back: the window every read below is bounded by,
# and the slot the filter line is written into once the first wave answers.
_WINDOW = windows.to_window(fixtures.MAY02, fixtures.MAY06)

_META_SLOT = object()

# The pair of keys an untouched sidebar over that window hashes to. Both are
# built through the filter and window owners here rather than read off the
# plan, so a key that stopped covering a selection is visible as a difference.
_EXPECTED_KEY = filters.cache_key(_WINDOW, None, list(_EVENTS), None, None)

_PREVIOUS_KEY = filters.cache_key(
    windows.previous_window(_WINDOW), None, list(_EVENTS), None, None,
)

# An offset no default would produce, so a session already carrying one can be
# told from a session the first render seeded.
_PICKED_OFFSET = -5

# What the free-text issue box is read back as: the bare number, the hash an
# operator copies out of a title, and the two spellings that narrow nothing.
_TYPED_ISSUES = (
    ("123", 123),
    ("#123", 123),
    ("", None),
    ("x", None),
)

_BAR_ATTRIBUTE = "render_date_filter_bar"

_PARALLEL_FLAG = "DASHBOARD_PARALLEL_READS"

_PREVIOUS_READ = "prev_summary"

_ZONED_READ = "heatmap_rows"


def _modules(page: fakes.FakeStreamlit) -> page_models.DashboardModules:
    """The caller's handles, of which only Streamlit's is reached up here."""
    return page_models.DashboardModules(
        st=page, pd=None, charts=None, theme=None,
    )


class SidebarFiltersTest(unittest.TestCase):
    """What the sidebar offers, and what one pass through it answers with."""

    def test_every_control_lands_in_the_sidebar(self) -> None:
        # The bar and the panels below share the page itself, so a filter drawn
        # outside this region would sit in the middle of the readings it
        # narrows rather than beside the ones it narrows them with.
        page, _ = self._render(_OPTIONS)

        self.assertEqual(
            {region for _kind, region, _request in page.drawn},
            {fakes.SIDEBAR},
        )
        self.assertEqual(
            fakes.drawn_as(page, fakes.HEADER),
            [(fakes.SIDEBAR, page_controls.SIDEBAR_HEADER)],
        )

    def test_the_repo_box_leads_with_all(self) -> None:
        # A database with nothing ingested still gets the box, so the control
        # reads as a filter set to everything rather than as a broken one.
        for repos, offered in (
            (_REPOS, (page_controls.ALL_REPOS, *_REPOS)),
            ((), (page_controls.ALL_REPOS,)),
        ):
            with self.subTest(repos=repos):
                page, _ = self._render(
                    FilterOptions(repos=repos, events=_EVENTS, stages=_STAGES),
                )
                _, request = fakes.drawn_as(page, fakes.REPO_BOX)[0]

                self.assertEqual(request["options"], offered)

    def test_the_sidebar_opens_on_everything(self) -> None:
        # Every multiselect starts holding the whole vocabulary and the issue
        # box starts empty, so a page nobody has touched reports the window the
        # bar picked rather than a slice of it.
        page, _ = self._render(_OPTIONS)
        _, issue_request = fakes.drawn_as(page, fakes.ISSUE_BOX)[0]

        self.assertEqual(
            [
                (request["label"], request["options"], request["default"])
                for _region, request in fakes.drawn_as(page, fakes.MULTISELECT)
            ],
            [
                ("Events", list(_EVENTS), list(_EVENTS)),
                ("Stages", list(_STAGES), list(_STAGES)),
            ],
        )
        self.assertEqual(issue_request["value"], "")

    def test_one_pass_answers_what_was_picked(self) -> None:
        # The selections come back raw -- a repository named, one event kept,
        # every stage unticked, an issue typed with its hash -- because what
        # each of them means is decided in one place afterwards.
        _, selections = self._render(
            _OPTIONS,
            repo=_REPOS[1],
            multiselects=(_EVENTS[:1], ()),
            issue="#7",
        )

        self.assertEqual(
            selections,
            page_controls.SidebarSelections(
                repo=_REPOS[1],
                events=[_EVENTS[0]],
                stages=[],
                issue_input="#7",
            ),
        )

    def _render(self, options: FilterOptions, **picks) -> tuple:
        page = fakes.FakeStreamlit(**picks)
        return page, page_controls.render_sidebar_filters(
            st=page, options=options,
        )


class TimezoneChoiceTest(unittest.TestCase):
    """The one selection the sidebar does not draw."""

    def test_a_first_render_seeds_the_default(self) -> None:
        # The card offering the zone sits at the foot of the page while the
        # read it changes is bound at the top, so a page nobody has scrolled
        # yet still has an offset to bucket its hours under.
        page = fakes.FakeStreamlit()

        self.assertEqual(
            page_controls.timezone_choice(page),
            filters.DEFAULT_TZ_OFFSET_HOURS,
        )
        self.assertEqual(
            page.session_state.tz_offset_hours,
            filters.DEFAULT_TZ_OFFSET_HOURS,
        )

    def test_a_picked_zone_survives_a_rerun(self) -> None:
        # Streamlit reruns the whole script on every interaction, so the
        # selectbox at the foot of the page only holds if the seeding up here
        # leaves an offset somebody already picked alone.
        page = fakes.FakeStreamlit()
        page.session_state.tz_offset_hours = _PICKED_OFFSET

        self.assertEqual(page_controls.timezone_choice(page), _PICKED_OFFSET)


class ResolvedFiltersTest(unittest.TestCase):
    """What those raw selections mean once they are one set of filters."""

    def test_the_all_option_names_no_repository(self) -> None:
        # `All` is the absence of a repository rather than one named `All`,
        # which is also what leaves an issue number narrowing nothing until a
        # repository is picked, since those numbers repeat across them.
        picked = _REPOS[0]

        self.assertIsNone(self._resolved().repo)
        self.assertEqual(self._resolved(repo=picked).repo, picked)

    def test_only_the_stages_collapse_to_none(self) -> None:
        # A stage is optional -- a repository-level record is filed under none
        # -- and the box offers only the stages actually recorded, so a clause
        # naming every one of them would drop exactly the rows carrying no
        # stage. An event is on every row, so naming all of those narrows
        # nothing and the selection is carried as it was picked.
        self.assertIsNone(self._resolved().stages)
        self.assertEqual(
            self._resolved(stages=_STAGES[:1]).stages, [_STAGES[0]],
        )
        self.assertEqual(self._resolved().events, list(_EVENTS))

    def test_either_cleared_box_shows_nothing(self) -> None:
        # An operator who unticked every value is asking for nothing, which is
        # a clause matching no row rather than the absence of a clause -- so
        # the box that otherwise collapses to no clause keeps this one.
        self.assertEqual(self._resolved(stages=()).stages, [])
        self.assertEqual(self._resolved(events=()).events, [])

    def test_the_issue_box_is_read_as_a_number(self) -> None:
        # The box is free text, so the hash an operator copies out of a title
        # and the bare number are one issue, and anything else is none.
        for typed, expected in _TYPED_ISSUES:
            with self.subTest(typed=typed):
                self.assertEqual(
                    self._resolved(issue=typed).issue_input, expected,
                )

    def _resolved(self, **picks) -> page_models.DashboardFilters:
        selections = page_controls.SidebarSelections(
            repo=picks.get("repo", page_controls.ALL_REPOS),
            events=picks.get("events", _EVENTS),
            stages=picks.get("stages", _STAGES),
            issue_input=picks.get("issue", ""),
        )
        return page_controls.resolve_dashboard_filters(
            _WINDOW, selections, _OPTIONS,
        )


class RenderedControlsTest(unittest.TestCase):
    """The order the top of the page is drawn in, and what it hands on."""

    def test_the_page_is_drawn_from_the_top(self) -> None:
        # The sidebar comes first, the placeholder the topbar is written into
        # is taken next -- the banner it holds counts rows the first wave has
        # not answered yet -- and the bar the days are picked in closes the
        # band above the panels.
        page, _, _ = self._render()

        self.assertEqual(
            [kind for kind, _region, _request in page.drawn],
            [
                fakes.HEADER,
                fakes.REPO_BOX,
                fakes.MULTISELECT,
                fakes.MULTISELECT,
                fakes.ISSUE_BOX,
                fakes.PLACEHOLDER,
                fakes.FILTER_BAR,
            ],
        )

    def test_the_bar_is_bounded_by_the_extent(self) -> None:
        # A window reaching past what the database holds is a panel drawn over
        # days nobody wrote, so the bar is handed the recorded span as the
        # inclusive days its pickers may be clamped to.
        _, drawn_bar, _ = self._render()

        self.assertIs(drawn_bar.call_args.kwargs["extent"], _EXTENT)
        self.assertEqual(
            (
                drawn_bar.call_args.kwargs["extent_min_d"],
                drawn_bar.call_args.kwargs["extent_max_d"],
            ),
            (fixtures.MAY01, fixtures.MAY28),
        )

    def test_both_slots_reach_the_caller(self) -> None:
        # Neither line above the panels can be written yet, so the controls
        # carry the two placeholders they are written into rather than markup.
        page, _, controls = self._render()

        self.assertIs(
            controls.topbar_slot,
            fakes.drawn_as(page, fakes.PLACEHOLDER)[0][1],
        )
        self.assertIs(controls.meta_slot, _META_SLOT)

    def test_the_picked_window_reaches_filters(self) -> None:
        # What the bar resolved is what every read below is bounded by, and the
        # zone read out of the session travels beside it.
        _, _, controls = self._render()

        self.assertIs(controls.filters.window, _WINDOW)
        self.assertEqual(
            controls.timezone_offset, filters.DEFAULT_TZ_OFFSET_HOURS,
        )

    def _render(self) -> tuple:
        page = fakes.FakeStreamlit()
        with patch.object(
            date_filter,
            _BAR_ATTRIBUTE,
            side_effect=fakes.BarAnswer(page, _WINDOW, _META_SLOT),
        ) as drawn_bar:
            return page, drawn_bar, page_controls.render_dashboard_controls(
                _modules(page), _EXTENT, _OPTIONS,
            )


class PreparedPageTest(unittest.TestCase):
    """The load those controls open: what it is keyed by, how it is issued,
    and when the clock it is measured against starts.
    """

    def test_the_waves_are_bound_to_one_key(self) -> None:
        # Every read below the controls is hashed from the same selections, so
        # two panels cannot report different windows under one filter line. The
        # zone is the exception, bound beside that key rather than inside it,
        # because an offset moves which cell a row is counted into rather than
        # which rows the window holds.
        bound = self._bound_reads()
        zoned = bound.pop(_ZONED_READ)
        bound.pop(_PREVIOUS_READ)

        self.assertEqual(set(bound.values()), {(_EXPECTED_KEY,)})
        self.assertEqual(
            zoned, (_EXPECTED_KEY, filters.DEFAULT_TZ_OFFSET_HOURS),
        )

    def test_the_window_before_it_is_hashed_too(self) -> None:
        # The delta pills and the cost-trend banner report this window against
        # the one before it, narrowed by the same selections and measured back
        # by the window owner's own arithmetic.
        self.assertEqual(self._bound_reads()[_PREVIOUS_READ], (_PREVIOUS_KEY,))

    def test_the_flag_decides_how_reads_issue(self) -> None:
        # The knob is parsed once, while the read-mode owner imports, and the
        # plan carries what it said, so one load cannot issue its two waves two
        # different ways.
        for parallel in (True, False):
            with self.subTest(parallel=parallel):
                prepared = self._prepare(parallel=parallel)

                self.assertIs(prepared.reads.parallel, parallel)

    def test_the_clock_starts_with_the_plan(self) -> None:
        # The load line reports the whole wait an operator sat through, so the
        # reading is taken where the plan is built rather than inside the
        # dispatch that runs it -- which is also what leaves the empty-window
        # notice, skipping that dispatch entirely, something to measure.
        before = perf_counter()
        started_at = self._prepare().reads.started_at

        self.assertGreaterEqual(started_at, before)
        self.assertLessEqual(started_at, perf_counter())

    def test_the_page_opens_on_that_extent(self) -> None:
        # The extent is what a window could be picked from at all, so the page
        # carries it beside the controls the picking happened in.
        prepared = self._prepare()

        self.assertIs(prepared.extent, _EXTENT)
        self.assertIs(prepared.controls.filters.window, _WINDOW)

    def _prepare(self, *, parallel: bool = False) -> page_models.DashboardPage:
        page = fakes.FakeStreamlit()
        with (
            patch.object(read_mode, _PARALLEL_FLAG, parallel),
            patch.object(
                date_filter,
                _BAR_ATTRIBUTE,
                side_effect=fakes.BarAnswer(page, _WINDOW, _META_SLOT),
            ),
        ):
            return page_controls.prepare_dashboard_page(
                _modules(page), _EXTENT, _OPTIONS,
            )

    def _bound_reads(self) -> dict:
        reads = self._prepare().reads
        return {
            name: reader.args
            for name, reader in (*reads.first_wave, *reads.second_wave)
        }


if __name__ == "__main__":
    unittest.main()
