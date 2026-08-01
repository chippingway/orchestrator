# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Where the trajectory page's HTML builders live and what it resolves to."""

import unittest


_VIEWER = "orchestrator.observability.trajectory_viewer"

# Each builder the page renders with, and the owner under `trajectory_viewer/`
# that defines it. Every one of them reports its owner -- a function's module is
# the module it is written in -- which is what makes this the inventory of where
# the page's HTML surface lives.
_HTML_MEMBERS = (
    ("_topbar_html", f"{_VIEWER}.summary_html"),
    ("_kpi_strip_html", f"{_VIEWER}.summary_html"),
    ("_card_header_html", f"{_VIEWER}.summary_html"),
    ("_meta_html", f"{_VIEWER}.run_html"),
    ("_labeled_chips_html", f"{_VIEWER}.run_html"),
    ("_runs_table_html", f"{_VIEWER}.run_html"),
    ("_run_picker_label", f"{_VIEWER}.run_html"),
    ("_run_usage_html", f"{_VIEWER}.usage_html"),
    ("_turn_usage_html", f"{_VIEWER}.usage_html"),
    ("_timeline_entry_html", f"{_VIEWER}.timeline_html"),
    ("_timeline_with_usage", f"{_VIEWER}.timeline_html"),
)


def _td():
    from orchestrator import trajectory_dashboard as td
    return td


class TrajectoryHtmlBoundaryTest(unittest.TestCase):
    """The viewer's pure inline-HTML builders are reached through one
    Streamlit-free leaf, `orchestrator._trajectory_dashboard_html`, and
    `orchestrator.trajectory_dashboard` publishes each under the same name so
    the page (and these tests) resolve to the same object.
    """

    def test_each_member_is_defined_where_declared(self) -> None:
        from orchestrator import _trajectory_dashboard_html as leaf
        for name, defining_module in _HTML_MEMBERS:
            with self.subTest(name=name):
                self.assertEqual(
                    getattr(leaf, name).__module__, defining_module,
                )

    def test_page_reaches_the_leaf_objects(self) -> None:
        from orchestrator import _trajectory_dashboard_html as leaf
        page = _td()
        for name, _ in _HTML_MEMBERS:
            with self.subTest(name=name):
                self.assertIs(getattr(page, name), getattr(leaf, name))
