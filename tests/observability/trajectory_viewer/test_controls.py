# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What the sidebar answers with, and what those answers narrow a read to."""
from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock

from orchestrator.observability.trajectory_viewer import controls, page_models
from orchestrator.observability.trajectory_viewer.filter_models import FilterOptions
from tests.observability.trajectory_viewer.trajectory_viewer_test_support import (
    BACKEND_CLAUDE,
    REPO,
    STAGE,
    run,
)

_ALL = "All"

_OTHER_REPO = "acme/gadgets"

_BACKEND_CODEX = "codex"

_FIXTURE_SESSION = "sess-abc"

_ISSUE_TYPED = "#7"

_ISSUE_MEANT = 7

_QUERY = "rebase"

_OPTIONS = FilterOptions(
    repos=(_OTHER_REPO, REPO),
    backends=(BACKEND_CLAUDE, _BACKEND_CODEX),
    agent_roles=("developer", "reviewer"),
    stages=(STAGE,),
)


def _sidebar(
    repo: str = _ALL,
    categorical: tuple = ((), (), ()),
    text: tuple = ("", ""),
    hide_fixtures: bool = False,
) -> Any:
    """A Streamlit double scripted with what each control was answered."""
    st = MagicMock()
    st.selectbox.return_value = repo
    st.multiselect.side_effect = list(categorical)
    st.text_input.side_effect = list(text)
    st.checkbox.return_value = hide_fixtures
    return st


def _page(*runs) -> page_models._TrajectoryPage:
    return page_models._TrajectoryPage(
        log_path=None,
        runs=runs,
        options=_OPTIONS,
        fixture_total=sum(1 for shown in runs if shown.is_fixture),
    )


def _request(**answered) -> page_models._TrajectoryFilters:
    return controls.render_trajectory_sidebar(_sidebar(**answered), _OPTIONS)


class SidebarWidgetTest(unittest.TestCase):
    """Each control is offered what the read actually held."""

    def test_multiselects_offer_the_read_s_values(self) -> None:
        st = _sidebar(categorical=((BACKEND_CLAUDE,), (), ()))
        picked = controls.render_categorical_filters(st, _OPTIONS)
        self.assertEqual(
            [call.args[1] for call in st.multiselect.call_args_list],
            [
                list(_OPTIONS.backends),
                list(_OPTIONS.agent_roles),
                list(_OPTIONS.stages),
            ],
        )
        self.assertEqual(picked, ((BACKEND_CLAUDE,), (), ()))

    def test_text_filters_come_back_as_typed(self) -> None:
        # Neither box is parsed here: the issue spelling is settled once, where
        # the whole request is assembled.
        st = _sidebar(text=(_ISSUE_TYPED, _QUERY))
        self.assertEqual(
            controls.render_text_filters(st), (_ISSUE_TYPED, _QUERY),
        )

    def test_the_repo_choice_leads_with_every_repo(self) -> None:
        st = _sidebar()
        controls.render_trajectory_sidebar(st, _OPTIONS)
        self.assertEqual(
            st.selectbox.call_args.args[1], (_ALL, *_OPTIONS.repos),
        )


class SidebarRequestTest(unittest.TestCase):
    """What the controls answered, read back as one filter request."""

    def test_nothing_narrowed_is_no_clause_at_all(self) -> None:
        # An unticked multiselect and the `All` repository are how a page
        # spells "everything", so neither may reach the filter as a selection
        # that would match no run.
        request = _request()
        self.assertEqual(
            (request.repo, request.backends, request.agent_roles),
            (None, None, None),
        )
        self.assertEqual((request.stages, request.issue), (None, None))
        self.assertEqual((request.query, request.hide_fixtures), ("", False))

    def test_every_answer_reaches_the_request(self) -> None:
        request = _request(
            repo=REPO,
            categorical=((BACKEND_CLAUDE,), ("developer",), (STAGE,)),
            text=(_ISSUE_TYPED, _QUERY),
            hide_fixtures=True,
        )
        self.assertEqual(request.repo, REPO)
        self.assertEqual(request.backends, (BACKEND_CLAUDE,))
        self.assertEqual(request.agent_roles, ("developer",))
        self.assertEqual(request.stages, (STAGE,))
        self.assertEqual((request.query, request.hide_fixtures), (_QUERY, True))

    def test_the_issue_box_takes_either_spelling(self) -> None:
        for typed in (_ISSUE_TYPED, str(_ISSUE_MEANT)):
            with self.subTest(typed=typed):
                self.assertEqual(_request(text=(typed, "")).issue, _ISSUE_MEANT)


class PageNarrowingTest(unittest.TestCase):
    """The request narrows the read the page already made."""

    def test_the_request_keeps_matches_in_order(self) -> None:
        page = _page(
            run(seq=2, repo=REPO),
            run(seq=1, repo=_OTHER_REPO),
            run(seq=0, repo=REPO, session_id=_FIXTURE_SESSION),
        )
        kept = controls.filter_page_runs(page, _request(repo=REPO))
        self.assertEqual([shown.seq for shown in kept], [2, 0])

    def test_the_toggle_drops_synthetic_runs(self) -> None:
        page = _page(run(seq=1), run(seq=0, session_id=_FIXTURE_SESSION))
        kept = controls.filter_page_runs(page, _request(hide_fixtures=True))
        self.assertEqual([shown.seq for shown in kept], [1])


if __name__ == "__main__":
    unittest.main()
