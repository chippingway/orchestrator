# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The order a whole page is drawn in, and where each empty read stops it."""
from __future__ import annotations

import unittest
from importlib import import_module
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from orchestrator.observability.trajectory_viewer import (
    filter_models,
    page_models,
    page_render,
    page_setup,
)
from tests.observability.trajectory_viewer.trajectory_viewer_test_support import (
    AGENT_ROLE,
    BACKEND_CLAUDE,
    ISSUE,
    REPO,
    STAGE,
    run,
)


_LOG_PATH = Path("/var/log/orchestrator/trajectories.jsonl")

_MARKED_PATH = Path("/var/log/<orch>/trajectories.jsonl")

_OPTIONS = filter_models.FilterOptions(
    repos=(REPO,),
    backends=(BACKEND_CLAUDE,),
    agent_roles=(AGENT_ROLE,),
    stages=(STAGE,),
)

# The site a historical caller still reaches both of these through, and the
# spelling each one answered to there.
_FACADE = "orchestrator.trajectory_dashboard"

_PUBLISHED = (
    ("_render_trajectory_footer", "render_trajectory_footer"),
    ("_render_trajectory_page", "render_trajectory_page"),
)


def _page(*read: Any) -> page_models._TrajectoryPage:
    return page_models._TrajectoryPage(
        log_path=_LOG_PATH,
        runs=read,
        options=_OPTIONS,
        fixture_total=0,
    )


def _filters() -> page_models._TrajectoryFilters:
    return page_models._TrajectoryFilters(
        repo=None,
        backends=None,
        agent_roles=None,
        stages=None,
        issue=None,
        query="",
        hide_fixtures=False,
    )


def _markdown(st: Any) -> str:
    return "".join(call.args[0] for call in st.markdown.call_args_list)


class FooterTest(unittest.TestCase):
    """The receipt names both counts and the file they were read from."""

    def test_it_reads_shown_out_of_what_was_held(self) -> None:
        st = MagicMock()
        page_render.render_trajectory_footer(st, 1, _page(run(), run()))
        self.assertIn("1 of 2 recorded", _markdown(st))
        self.assertIn(str(_LOG_PATH), _markdown(st))

    def test_the_path_is_escaped_into_the_markup(self) -> None:
        # The path is an operator-supplied knob written out with
        # `unsafe_allow_html=True`, so a bracket in it is text, not a tag.
        st = MagicMock()
        page = page_models._TrajectoryPage(
            log_path=_MARKED_PATH,
            runs=(),
            options=_OPTIONS,
            fixture_total=0,
        )
        page_render.render_trajectory_footer(st, 0, page)
        self.assertIn("&lt;orch&gt;", _markdown(st))
        self.assertNotIn("<orch>", _markdown(st))


class EmptyReadTest(unittest.TestCase):
    """Each empty state stops the page where its own answer is complete."""

    def test_an_empty_file_stops_at_the_notice(self) -> None:
        st = MagicMock()
        page_render.render_trajectory_page(st, _page(), _filters(), ())
        self.assertIn("TRAJECTORY_LOG_PATH", st.info.call_args.args[0])
        st.expander.assert_not_called()

    def test_an_emptied_read_keeps_the_tiles(self) -> None:
        # The counts above the message are what say the narrowing is what
        # dropped the runs, so this one stops after the strip rather than
        # before it.
        st = MagicMock()
        page_render.render_trajectory_page(st, _page(run()), _filters(), ())
        self.assertEqual(
            st.info.call_args.args[0], page_setup.EMPTY_FILTER_MESSAGE,
        )
        self.assertIn("orch-kpi", _markdown(st))
        st.expander.assert_not_called()


class WholePageTest(unittest.TestCase):
    """A read with survivors is drawn through every section in order."""

    def test_every_section_is_drawn_once(self) -> None:
        st = MagicMock()
        st.selectbox.side_effect = [REPO, ISSUE, 0]
        shown = (run(),)
        page_render.render_trajectory_page(st, _page(*shown), _filters(), shown)
        st.info.assert_not_called()
        st.expander.assert_called_once()
        self.assertEqual(st.selectbox.call_count, 3)
        self.assertIn("1 of 1 recorded", _markdown(st))


class HistoricalSpellingTest(unittest.TestCase):
    """The page surface still answers under the names it published."""

    def test_each_name_resolves_to_the_owner(self) -> None:
        facade = import_module(_FACADE)
        for published, owned in _PUBLISHED:
            with self.subTest(name=published):
                self.assertIs(
                    getattr(facade, published), getattr(page_render, owned),
                )


if __name__ == "__main__":
    unittest.main()
