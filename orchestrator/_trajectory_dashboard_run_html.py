# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the run renderings, answered by its owner.

Each name is the owner's own object under the spelling this module published it
as, so the metadata grid, the overview table, and the picker label a caller
draws are the ones the page draws.
"""

from __future__ import annotations

from orchestrator.observability.trajectory_viewer import run_html


REPO_LABEL = run_html.REPO_LABEL
FIXTURE_LABEL_PREFIX = run_html.FIXTURE_LABEL_PREFIX
_meta_html = run_html.meta_html
_labeled_chips_html = run_html.labeled_chips_html
_run_table_row_html = run_html.run_table_row_html
_runs_table_html = run_html.runs_table_html
_run_picker_label = run_html.run_picker_label
