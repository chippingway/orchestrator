# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for a sparkline's scaling and projection.

The floor a flat window's span is clamped at, the anchoring one window is
projected through, the height and step each of its days is placed by, and the
projection itself are the dashboard owner's own objects. The pair of path
strings beside them belongs to the rendering owner, since that is where both
are written. A caller that names this module -- or the HTML surface above it
-- gets those rather than a copy, so a line a page draws and one the owner
projects cannot disagree about where a day sits.
"""
from __future__ import annotations

from orchestrator.observability.dashboard import sparkline_html, sparkline_points


_EPSILON = sparkline_points.EPSILON
_SparklineLayout = sparkline_points.SparklineLayout
_SparklinePaths = sparkline_html.SparklinePaths
_sparkline_y = sparkline_points.sparkline_y
_sparkline_step = sparkline_points.sparkline_step
_sparkline_layout = sparkline_points.sparkline_layout
_sparkline_point = sparkline_points.sparkline_point
_sparkline_points = sparkline_points.sparkline_points
