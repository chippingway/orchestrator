# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The two-column page the repository-and-reliability section is drawn onto.

Streamlit lives in the optional `dashboard` group and a section is handed its
`st` rather than reaching for one, so the cases drive a whole render against a
stand-in that records what each call was given. Every markup payload and
figure is recorded with the column open around it, which is what lets a case
say the run-health tiles landed right of the repository ranking rather than
only that both were drawn -- and what makes the 7:5 split readable as the
request it was rather than inferred from the source.

Each record keeps the options the call carried alongside its payload, because
those options are the difference between what an operator sees and what they
do not: markup handed over without `unsafe_allow_html` renders as its own
source, a card opened without `border` loses the outline that makes it a card,
and a figure drawn without `use_container_width` sits at Plotly's own width
inside a column sized for something else. A stand-in that dropped them would
let all three regress with every case still passing.

Both chart builders are the section's own, so the recorder here stands in for
them under patch rather than being handed over, and hands back the request it
was asked for instead of a figure. The keywords a builder was bounded by are
kept whole rather than reduced to the two dates a case happens to read, so the
day strip's window can be asserted without the recorder deciding in advance
which of its keywords matter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

# The two columns the section is split across, named as the owner's own locals
# are.
LEFT = "left"

RIGHT = "right"

# The ratio the section requests, spelled once so a case names it rather than
# repeating the pair.
COLUMN_RATIO = (7, 5)


@dataclass(frozen=True)
class ChartRequest:
    """One figure the section asked for, and the keywords bounding it."""

    builder: str
    rows: Sequence[Any]
    bounds: Mapping[str, Any]


@dataclass(frozen=True)
class Drawn:
    """One payload, the column it landed in, and the options it carried."""

    column: str
    payload: Any
    options: Mapping[str, Any]


class RecordingRegion:
    """One column or card, entered for whatever is drawn inside it."""

    def __init__(self, page: "ReliabilityStreamlit", name: str) -> None:
        self.name = name
        self._page = page

    def __enter__(self) -> "RecordingRegion":
        self._page.open_column = self.name
        return self

    def __exit__(self, *exception: Any) -> bool:
        return False


class RecordingCharts:
    """Stand-in for both builders, answering with the request it was given."""

    def __init__(self) -> None:
        self.requests: list[ChartRequest] = []

    def cost_by_repo(self, rows: Sequence[Any]) -> ChartRequest:
        return self._record("cost_by_repo", rows, {})

    def done_per_day_bars(
        self,
        rows: Sequence[Any],
        **bounds: Any,
    ) -> ChartRequest:
        return self._record("done_per_day_bars", rows, bounds)

    def _record(
        self,
        builder: str,
        rows: Sequence[Any],
        bounds: Mapping[str, Any],
    ) -> ChartRequest:
        request = ChartRequest(builder, rows, bounds)
        self.requests.append(request)
        return request


class ReliabilityStreamlit:
    """Fake `st` recording what each column of the section was drawn."""

    def __init__(self) -> None:
        self.column_request: tuple | None = None
        self.open_column = ""
        self.borders: list[tuple[str, Any]] = []
        self.markdowns: list[Drawn] = []
        self.figures: list[Drawn] = []

    def columns(self, widths: Any) -> list[RecordingRegion]:
        self.column_request = tuple(widths)
        return [RecordingRegion(self, name) for name in (LEFT, RIGHT)]

    def container(self, **handed: Any) -> RecordingRegion:
        self.borders.append((self.open_column, handed.get("border")))
        return RecordingRegion(self, self.open_column)

    def markdown(self, markup: str, **handed: Any) -> None:
        self.markdowns.append(Drawn(self.open_column, markup, handed))

    def plotly_chart(self, figure: Any, **handed: Any) -> None:
        self.figures.append(Drawn(self.open_column, figure, handed))


def markup_in(page: ReliabilityStreamlit, column: str) -> str:
    """Everything one column was drawn, in the order it was written."""
    return "".join(
        drawn.payload
        for drawn in page.markdowns
        if drawn.column == column
    )
