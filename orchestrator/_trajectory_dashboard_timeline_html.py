# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the timeline HTML, answered by its owner.

Each name is the owner's own object under the spelling this module published it
as, so the badge vocabulary a caller reads a kind through and the entry-to-strip
pairing it walks are the ones the page walks.
"""

from __future__ import annotations

from orchestrator.observability.trajectory_viewer import timeline_html


TimelineUsagePair = timeline_html.TimelineUsagePair
BADGE_BY_KIND = timeline_html.BADGE_BY_KIND
_timeline_entry_html = timeline_html.timeline_entry_html
_timeline_with_usage = timeline_html.timeline_with_usage
