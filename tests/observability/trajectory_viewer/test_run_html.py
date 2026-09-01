# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What one run is identified by in a metadata tile, a table row, and a label."""
from __future__ import annotations

import unittest

from orchestrator.observability.trajectory_viewer import constants, run_html
from tests.observability.trajectory_viewer.trajectory_viewer_test_support import (
    REPO,
    TOOL_BASH,
    TOOL_CALL,
    TOOL_RESULT,
    run,
    step,
)

_UNSAFE_REPO = "o/<r&>"

_ESCAPED_REPO = "o/&lt;r&amp;&gt;"

_REVIEW_ROUND = 2


class MetaHtmlTest(unittest.TestCase):
    """The identity grid draws the fields the record carried, and no others."""

    def test_only_present_fields_render(self) -> None:
        rendered = run_html.meta_html(
            run(session_id="sess-1", review_round=_REVIEW_ROUND),
        )
        self.assertIn(">Repo</div>", rendered)
        self.assertIn(f">{REPO}</div>", rendered)
        self.assertIn(">Review round</div>", rendered)
        self.assertIn(">sess-1</div>", rendered)
        # No retry count on this run -> the tile is omitted entirely, so an
        # absent field never reads as a recorded blank.
        self.assertNotIn(">Retry count</div>", rendered)

    def test_html_escaped(self) -> None:
        rendered = run_html.meta_html(run(repo=_UNSAFE_REPO))
        self.assertIn(_ESCAPED_REPO, rendered)
        self.assertNotIn(_UNSAFE_REPO, rendered)


class LabeledChipsHtmlTest(unittest.TestCase):
    """A chip row is drawn, marked empty, or dropped, depending on the ask."""

    def test_label_and_pills(self) -> None:
        rendered = run_html.labeled_chips_html("Tools offered", [TOOL_BASH, "Edit"])
        self.assertIn("Tools offered", rendered)
        self.assertIn(">Bash</span>", rendered)
        self.assertIn(">Edit</span>", rendered)

    def test_empty_is_blank(self) -> None:
        self.assertEqual(run_html.labeled_chips_html("Tools", []), "")

    def test_empty_marker_renders_none_state(self) -> None:
        # With a marker, an empty list still renders the row and flags the
        # chip with the `none` empty-state class instead of a real pill, so
        # "nothing fired" is distinguishable from an omitted row.
        rendered = run_html.labeled_chips_html(
            "Skills triggered", [], empty_marker="none",
        )
        self.assertIn(">Skills triggered</span>", rendered)
        self.assertIn('class="orch-traj-chip none"', rendered)
        self.assertIn(">none</span>", rendered)

    def test_escaped(self) -> None:
        rendered = run_html.labeled_chips_html("Skills", ["<x>"])
        self.assertIn("&lt;x&gt;", rendered)
        self.assertNotIn("<x>", rendered)


class RunsTableHtmlTest(unittest.TestCase):
    """The overview table's headers, its cells, and its fixture marking."""

    def test_headers_and_row_cells(self) -> None:
        rendered = run_html.runs_table_html([
            run(
                review_round=1,
                steps=(
                    step(TOOL_CALL, name=TOOL_BASH),
                    step(TOOL_RESULT, tool_id="t"),
                ),
            ),
        ])
        for header in (
            "Issue", "Repo", "Stage", "Role",
            "Backend", "Round", "Steps", "Tool calls", "Recorded",
        ):
            with self.subTest(header=header):
                self.assertIn(f">{header}</th>", rendered)
        self.assertIn("#42", rendered)
        self.assertIn(f">{REPO}</td>", rendered)
        # Two steps, one of which is a tool call.
        self.assertIn(">2</td>", rendered)
        self.assertIn(">1</td>", rendered)

    def test_repo_escaped(self) -> None:
        rendered = run_html.runs_table_html([run(repo=_UNSAFE_REPO)])
        self.assertIn(_ESCAPED_REPO, rendered)
        self.assertNotIn(_UNSAFE_REPO, rendered)

    def test_only_a_fixture_row_is_tagged(self) -> None:
        # The dimming class and the tag are what let an operator who left the
        # toggle off tell a synthetic record apart from a real one.
        fixture = run(user_input=constants.FIXTURE_PROMPT)
        self.assertTrue(fixture.is_fixture)
        tagged = run_html.runs_table_html([fixture])
        self.assertIn('<tr class="fixture">', tagged)
        self.assertIn(">fixture</span>", tagged)

        real = run()
        self.assertFalse(real.is_fixture)
        plain = run_html.runs_table_html([real])
        self.assertNotIn('class="fixture"', plain)
        self.assertNotIn("orch-traj-fixture-tag", plain)


class RunPickerLabelTest(unittest.TestCase):
    """One run's label inside the cohort already chosen above the picker."""

    def test_fixture_run_prefixed(self) -> None:
        fixture = run(session_id="sess-9")
        self.assertTrue(fixture.is_fixture)
        label = run_html.run_picker_label(fixture)
        self.assertTrue(label.startswith(run_html.FIXTURE_LABEL_PREFIX))
        self.assertIn(fixture.detail_label(), label)

    def test_real_run_plain_label(self) -> None:
        # The per-run picker drops repo / issue (chosen in the cascading
        # selectors above it) and shows only the `detail_label` cohort.
        real = run()
        self.assertEqual(run_html.run_picker_label(real), real.detail_label())
        self.assertNotIn(real.repo, run_html.run_picker_label(real))


if __name__ == "__main__":
    unittest.main()
