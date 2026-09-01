# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a page settles before it draws: its chrome, its refusal, and its read."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from orchestrator.observability.dashboard.css import PAGE_CSS
from orchestrator.observability.trajectory_viewer import constants, css, page_setup
from tests.observability.trajectory_viewer.trajectory_viewer_test_support import (
    BACKEND_CLAUDE,
    REPO,
    record,
)

_FIXTURE_SESSION = "sess-abc"

_OTHER_REPO = "acme/gadgets"


def _holder(log_path):
    """A settings holder carrying nothing but the knob this page reads."""
    return SimpleNamespace(TRAJECTORY_LOG_PATH=log_path)


def _written(directory: str, *records) -> Path:
    log_path = Path(directory) / "trajectories.jsonl"
    log_path.write_text(
        "".join(f"{json.dumps(written)}\n" for written in records),
    )
    return log_path


class PageChromeTest(unittest.TestCase):
    """The two stylesheets are written in the order their cascade needs."""

    def test_shared_sheet_is_written_first(self) -> None:
        st = Mock()
        page_setup.configure_page(st)
        self.assertEqual(
            [call.args[0] for call in st.markdown.call_args_list],
            [PAGE_CSS, css.EXTRA_CSS],
        )
        self.assertEqual(
            st.set_page_config.call_args.kwargs["page_title"],
            "Orchestrator Trajectories",
        )


class UnconfiguredSinkTest(unittest.TestCase):
    """An install with the sink switched off is refused, not left empty."""

    def test_the_banner_stops_the_run(self) -> None:
        st = Mock()
        page_setup.stop_if_unconfigured(st, _holder(None))
        st.stop.assert_called_once_with()
        self.assertEqual(
            st.warning.call_args.args, (constants.UNCONFIGURED_LOG_MESSAGE,),
        )
        # The topbar is drawn above it, so the refusal still reads as this page
        # rather than as a bare warning on an empty canvas.
        self.assertIn("Orchestrator Trajectories", st.markdown.call_args.args[0])

    def test_a_configured_sink_draws_nothing(self) -> None:
        st = Mock()
        page_setup.stop_if_unconfigured(st, _holder(Path("/tmp/traj.jsonl")))
        st.stop.assert_not_called()
        st.markdown.assert_not_called()
        st.warning.assert_not_called()


class PageReadTest(unittest.TestCase):
    """One pass over the holder's file is what the whole page is built from."""

    def test_the_read_carries_what_a_page_needs(self) -> None:
        with tempfile.TemporaryDirectory() as work_dir:
            log_path = _written(
                work_dir,
                record(),
                record(repo=_OTHER_REPO, session_id=_FIXTURE_SESSION),
            )
            page = page_setup.load_trajectory_page(_holder(log_path))
        self.assertEqual(page.log_path, log_path)
        self.assertEqual(page.total, 2)
        # A dropdown is offered what the runs carried, and nothing besides.
        self.assertEqual(page.options.repos, (_OTHER_REPO, REPO))
        self.assertEqual(page.options.backends, (BACKEND_CLAUDE,))
        self.assertEqual(page.fixture_total, 1)

    def test_an_unwritten_file_reads_as_an_empty_page(self) -> None:
        # The sink is opt-in and writes on the first tracked run, so a
        # configured path that does not exist yet is the ordinary state.
        with tempfile.TemporaryDirectory() as work_dir:
            page = page_setup.load_trajectory_page(
                _holder(Path(work_dir) / "absent.jsonl"),
            )
        self.assertEqual((page.total, page.fixture_total), (0, 0))
        self.assertEqual(page.options.repos, ())


if __name__ == "__main__":
    unittest.main()
