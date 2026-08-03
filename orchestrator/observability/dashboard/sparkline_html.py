# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The inline SVG one of those lines reaches the browser as.

A sparkline is written as markup rather than asked of Plotly: it is one
polyline and one filled path in a box a KPI tile has room for, so a page that
drew four of them as figures would pay for four charts to render a shape with
no axis, legend, or hover in it. Both strings are built from a single
projection, because they trace the same days and differ only in how they end
-- computing them apart is where a tint could start shading a line the tile
above it does not show.

The filled path closes on the baseline the points were laid out above rather
than on the window's own lowest day, so the tint under every tile reaches the
bottom of its box and four tiles read as one strip. A window that projects to
no points is answered with an empty box of the requested size: the tile keeps
the room the drawn line would have taken, so a strip whose windows are not all
alike still lines up.

The keyword surface a caller reaches this through -- `values`, `color`, `w`,
and `h` -- is bound as an explicit signature rather than spelled out as
parameters, because two of those names are shorter than a readable parameter
may be here while the calls that pass them predate that rule. The renderer
underneath takes one request object, so what a caller passes is bound, applied,
and rendered without either spelling constraining the other.
"""
from __future__ import annotations

from dataclasses import dataclass
from inspect import Parameter, Signature
from typing import Any, Sequence

from orchestrator.observability.dashboard.sparkline_points import (
    sparkline_points,
)


DEFAULT_SPARKLINE_WIDTH = 96
DEFAULT_SPARKLINE_HEIGHT = 26


@dataclass(frozen=True)
class SparklinePaths:
    """The two strings one projected window is written as."""

    polyline: str
    area: str


@dataclass(frozen=True)
class SparklineRequest:
    """One line as the caller asked for it: its days, hue, and box."""

    samples: Sequence[float]
    color: str
    width: int
    height: int


def sparkline_paths(
    points: Sequence[tuple[float, float]],
    *,
    height: int,
) -> SparklinePaths:
    """Write one projection as both the stroked line and the tint under it."""
    # The inset the points were laid out inside, so the fill closes on the
    # baseline of the box rather than under the lowest day in the window.
    padding = 2
    polyline = " ".join(map(sparkline_point_text, points))
    area = sparkline_area_path(points, height=height, padding=padding)
    return SparklinePaths(polyline=polyline, area=area)


def sparkline_point_text(point: tuple[float, float]) -> str:
    """One projected day, rounded to the precision the markup carries."""
    return f"{point[0]:.1f},{point[1]:.1f}"


def sparkline_area_path(
    points: Sequence[tuple[float, float]],
    *,
    height: int,
    padding: int,
) -> str:
    """Trace the line, then close it along the baseline into a fill."""
    baseline = height - padding
    first_x = points[0][0]
    last_x = points[-1][0]
    segments = " L".join(map(sparkline_point_text, points))
    return (
        f"M{first_x:.1f},{baseline:.1f}"
        f" L{segments}"
        f" L{last_x:.1f},{baseline:.1f} Z"
    )


def render_sparkline(request: SparklineRequest) -> str:
    """Draw one window, or hold the tile's room with an empty box."""
    points = sparkline_points(
        request.samples,
        width=request.width,
        height=request.height,
    )
    if not points:
        return (
            f'<svg width="{request.width}" height="{request.height}" '
            f'viewBox="0 0 {request.width} {request.height}"></svg>'
        )
    paths = sparkline_paths(points, height=request.height)
    return (
        f'<svg width="{request.width}" height="{request.height}" '
        f'viewBox="0 0 {request.width} {request.height}" style="display:block">'
        f'<path d="{paths.area}" fill="{request.color}" fill-opacity="0.18" />'
        f'<polyline points="{paths.polyline}" fill="none" stroke="{request.color}" '
        'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />'
        "</svg>"
    )


def sparkline_svg(*args: Any, **kwargs: Any) -> str:
    """Render an inline SVG through the historical keyword surface."""
    bound = SPARKLINE_SIGNATURE.bind(*args, **kwargs)
    bound.apply_defaults()
    request = SparklineRequest(
        samples=bound.arguments["values"],
        color=bound.arguments["color"],
        width=bound.arguments["w"],
        height=bound.arguments["h"],
    )
    return render_sparkline(request)


SPARKLINE_SIGNATURE = Signature(
    (
        Parameter("values", Parameter.POSITIONAL_OR_KEYWORD),
        Parameter("color", Parameter.KEYWORD_ONLY),
        Parameter("w", Parameter.KEYWORD_ONLY, default=DEFAULT_SPARKLINE_WIDTH),
        Parameter("h", Parameter.KEYWORD_ONLY, default=DEFAULT_SPARKLINE_HEIGHT),
    ),
)
sparkline_svg.__signature__ = SPARKLINE_SIGNATURE
