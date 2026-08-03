# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Where a KPI tile's sparkline puts each of the days behind it.

The line under a headline tile is drawn in a box narrow enough that no axis,
tick, or label fits in it, so its shape carries the whole reading. That shape
comes from scaling the window to its own lowest and highest day rather than to
zero: a fortnight of spend that drifted by a percent draws as a visible move
here, where a zero-anchored line would draw it as a flat rule and read as a
window in which nothing happened.

Two windows have no shape to draw that way. One whose days are all equal has
no range to divide by, so the span floors at ``EPSILON`` and every day lands at
the same height instead of the projection raising. One with no days at all, or
one whose days are every zero, projects to no points: it would sit exactly on
the baseline a window that merely never rose above its own minimum draws on,
and the caller renders the empty box rather than let one line say both things.

A day a read answered with a null is counted as a zero before any of that, so
a quiet day narrows the window it is scaled inside instead of dropping out of
it. Projecting these points costs neither Streamlit nor Plotly, so an importer
that never renders one still loads cleanly.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


EPSILON = 1e-9


def sparkline_y(
    sample: float,
    *,
    low: float,
    span: float,
    padding: int,
    height: int,
) -> float:
    """The height one day is drawn at, measured down from the box's top."""
    normalized = (sample - low) / span
    drawable_height = height - padding * 2
    return padding + (1 - normalized) * drawable_height


@dataclass(frozen=True)
class SparklineLayout:
    """What every day of one window is projected through."""

    low: float
    span: float
    padding: int
    height: int
    step: float


def sparkline_step(width: int, padding: int, sample_count: int) -> float:
    """The horizontal distance between two neighbouring days."""
    drawable_width = width - padding * 2
    intervals = max(sample_count - 1, 1)
    return drawable_width / intervals


def sparkline_layout(
    series: Sequence[float],
    *,
    width: int,
    height: int,
) -> SparklineLayout:
    """Anchor one window to its own lowest and highest day."""
    low = min(series)
    padding = 2
    return SparklineLayout(
        low=low,
        span=max(max(series) - low, EPSILON),
        padding=padding,
        height=height,
        step=sparkline_step(width, padding, len(series)),
    )


def sparkline_point(
    index: int,
    sample: float,
    layout: SparklineLayout,
) -> tuple[float, float]:
    """Place one day of a window inside the box the line is drawn in."""
    return (
        layout.padding + index * layout.step,
        sparkline_y(
            sample,
            low=layout.low,
            span=layout.span,
            padding=layout.padding,
            height=layout.height,
        ),
    )


def sparkline_points(
    series: Sequence[float],
    *,
    width: int,
    height: int,
) -> list[tuple[float, float]]:
    """Project one window, or answer with nothing worth drawing a line for."""
    numbers = [float(sample or 0) for sample in series]
    if not numbers or max(numbers) == min(numbers) == 0:
        return []
    layout = sparkline_layout(numbers, width=width, height=height)
    return [
        sparkline_point(index, sample, layout)
        for index, sample in enumerate(numbers)
    ]
