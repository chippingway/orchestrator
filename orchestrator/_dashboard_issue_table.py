# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the most-expensive-issues table.

The six columns a window's costliest issues are ranked into, the rules the
in-row bars and status pills are painted by, the readings one row is reduced
to, and the panel they are assembled into are the dashboard owner's own
objects. A caller that names this module -- or the HTML surface above it --
gets those rather than a copy, so the ranking a page draws and the one the
owner builds cannot start disagreeing about what a row is worth.
"""
from __future__ import annotations

from orchestrator.observability.dashboard import issue_table


ISSUES_TABLE_COLUMNS = issue_table.ISSUES_TABLE_COLUMNS
ISSUES_TABLE_EXTRA_CSS = issue_table.ISSUES_TABLE_EXTRA_CSS
_issue_status_pill = issue_table.issue_status_pill
_review_round_html = issue_table.review_round_html
_IssueRowView = issue_table.IssueRowView
_issue_row_view = issue_table.issue_row_view
_issue_table_row_html = issue_table.issue_table_row_html
_issues_table_html = issue_table.issues_table_html
