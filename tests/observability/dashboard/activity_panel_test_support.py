# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The card surface the activity grid is drawn onto, faked.

Streamlit lives in the optional `dashboard` group and the section is handed
its `st` rather than reaching for one, so the cases drive a whole render
against a stand-in that records what each call was given.

Every call keeps the options it carried alongside its payload, because those
options are the difference between what an operator sees and what they do not:
markup handed over without `unsafe_allow_html` renders as its own source, a
card opened without `border` loses the outline that makes it a card, a
selectbox drawn without its key forgets the zone on the next rerun, and a
figure drawn without `use_container_width` sits at Plotly's own width inside a
column sized for something else. A stand-in that dropped them would let all
four regress with every case still passing.

The chart builder is the section's own module-scope import, so the stand-in
here answers for it under patch rather than being handed over, and hands back
the request it was asked for instead of a figure.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Self

from orchestrator.observability.analytics.query.activity_models import (
    HourlyHeatmapPoint,
)

_WEEKDAY = 2

_HOUR = 9

_EVENTS = 3

_TOKENS = 4200

# One cell with a volume no other reading on the fake page carries, so a case
# can tell the rows the grid was handed from anything the card built itself.
POINTS = (
    HourlyHeatmapPoint(
        weekday=_WEEKDAY, hour=_HOUR, count=_EVENTS, total_tokens=_TOKENS,
    ),
)


@dataclass(frozen=True)
class ChartRequest:
    """The rows the grid was asked for, and the zone it was annotated with."""

    rows: Sequence[HourlyHeatmapPoint]
    tz_label: str


@dataclass(frozen=True)
class Drawn:
    """One payload and the options the call carried it under."""

    payload: Any
    options: Mapping[str, Any]


class NullContext:
    """`with`-usable stand-in for `st.container(...)`."""

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exception: object) -> bool:
        return False


class ActivityStreamlit:
    """Fake `st` recording the card, the selectbox, and the figure drawn."""

    def __init__(self) -> None:
        self.borders: list[Any] = []
        self.markdowns: list[Drawn] = []
        self.selectboxes: list[Drawn] = []
        self.figures: list[Drawn] = []

    def container(self, **handed: Any) -> NullContext:
        self.borders.append(handed.get("border"))
        return NullContext()

    def markdown(self, markup: str, **handed: Any) -> None:
        self.markdowns.append(Drawn(markup, handed))

    def selectbox(self, label: str, options: Any, **handed: Any) -> None:
        self.selectboxes.append(Drawn(label, {"options": options, **handed}))

    def plotly_chart(self, figure: Any, **handed: Any) -> None:
        self.figures.append(Drawn(figure, handed))


def record_heatmap(
    rows: Sequence[HourlyHeatmapPoint],
    *,
    tz_label: str,
) -> ChartRequest:
    """Stand in for the grid builder, answering with the request itself."""
    return ChartRequest(rows, tz_label)
