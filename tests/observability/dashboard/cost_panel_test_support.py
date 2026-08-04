# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The two-column page the cost sections are drawn onto, faked.

Streamlit lives in the optional `dashboard` group and a section is handed its
`st` rather than reaching for one, so the cases drive a whole render against a
stand-in that records what each call was given. Every markup payload, notice,
and figure is recorded with the column open around it, which is what lets a
case say the ranking landed left of the backend cards rather than only that
both were drawn -- and what makes the 7:5 split readable as the request it was
rather than inferred from the source.

Each record keeps the options the call carried alongside its payload, because
those options are the difference between what an operator sees and what they
do not: markup handed over without `unsafe_allow_html` renders as its own
source, a card opened without `border` loses the outline that makes it a card,
and a figure drawn without `use_container_width` sits at Plotly's own width
inside a column sized for something else. A stand-in that dropped them would
let all three regress with every case still passing.

The chart builders are the panel owners' own, so the recorder here stands in
for them under patch rather than being handed over, and hands back the request
it was asked for instead of a figure. A case reads the height each panel was
pinned to straight off that record, which is how two bars sized to one number
are told apart from two sized to their own.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

# The two columns every section here is split across, named as the owners' own
# locals are.
LEFT = "left"

RIGHT = "right"

# The ratio both sections request, spelled once so a case names it rather than
# repeating the pair.
COLUMN_RATIO = (7, 5)


@dataclass(frozen=True)
class ChartRequest:
    """One figure a section asked for, and the height it pinned."""

    builder: str
    rows: Sequence[Any]
    height: Optional[int]


@dataclass(frozen=True)
class Drawn:
    """One payload, the column it landed in, and the options it carried."""

    column: str
    payload: Any
    options: Mapping[str, Any]


class RecordingRegion:
    """One column or card, entered for whatever is drawn inside it."""

    def __init__(self, page: "CostPanelStreamlit", name: str) -> None:
        self.name = name
        self._page = page

    def __enter__(self) -> "RecordingRegion":
        self._page.open_column = self.name
        return self

    def __exit__(self, *exception: Any) -> bool:
        return False


class RecordingCharts:
    """Stand-in for the two builders, answering with the request it was given."""

    def __init__(self) -> None:
        self.requests: list[ChartRequest] = []

    def cost_by_stage(
        self,
        rows: Sequence[Any],
        *,
        height: Optional[int] = None,
    ) -> ChartRequest:
        return self._record("cost_by_stage", rows, height)

    def cost_by_review_round(
        self,
        rows: Sequence[Any],
        *,
        height: Optional[int] = None,
    ) -> ChartRequest:
        return self._record("cost_by_review_round", rows, height)

    def _record(
        self,
        builder: str,
        rows: Sequence[Any],
        height: Optional[int],
    ) -> ChartRequest:
        request = ChartRequest(builder, rows, height)
        self.requests.append(request)
        return request


class CostPanelStreamlit:
    """Fake `st` recording what each column of a cost section was drawn."""

    def __init__(self) -> None:
        self.column_request: Optional[tuple] = None
        self.open_column = ""
        self.borders: list[tuple[str, Any]] = []
        self.markdowns: list[Drawn] = []
        self.notices: list[tuple[str, str]] = []
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

    def show_notice(self, text: str) -> None:
        """Record an `st.info(...)`, which the lookup below routes here."""
        self.notices.append((self.open_column, text))

    def __getattr__(self, attribute_name: str) -> Any:
        if attribute_name == "info":
            return self.show_notice
        raise AttributeError(attribute_name)


def markup_in(page: CostPanelStreamlit, column: str) -> str:
    """Everything one column was drawn, in the order it was written."""
    return "".join(
        drawn.payload
        for drawn in page.markdowns
        if drawn.column == column
    )


def notices_in(page: CostPanelStreamlit, column: str) -> list[str]:
    """The empty-state notices one column rendered."""
    return [
        text for open_column, text in page.notices if open_column == column
    ]
