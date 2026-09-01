# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The stand-in the filter bar is drawn against.

Streamlit lives in the optional `dashboard` dependency group, so the cases
record what the bar asked for instead of rendering it: which slot each widget
landed in, what it was seeded and bounded with, and what the session was left
carrying. Every widget records the region open around it, which is what lets a
case say the preset radio landed in the second slot rather than only that one
was drawn.

A radio answers with the option its index preselected, the way an untouched one
does; `chosen` is how a case says the operator clicked a different button. A
picker answers with the day it was seeded with unless the case queued one, for
the same reason.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any, Self


# The region the bar's own card opens, and the five slots inside it, named as
# the owner's columns are.
CARD = "card"

SLOT_NAMES = ("label", "preset", "start", "end", "meta")

# The widget kinds one draw is recorded under, so a case reads back only the
# ones it is about.
MARKDOWN = "markdown"

RADIO = "radio"

PICKER = "date_input"

PLACEHOLDER = "empty"


class RecordingRegion:
    """One region of the page, entered for the widgets drawn inside it."""

    def __init__(self, page: FakeStreamlit, name: str) -> None:
        self.name = name
        self._page = page

    def __enter__(self) -> Self:
        self._page.open_region = self.name
        return self

    def __exit__(self, *exception: object) -> bool:
        self._page.open_region = ""
        return False


class SessionState:
    """The two ways the bar reaches the session: membership and attribute."""

    def __contains__(self, key: str) -> bool:
        return key in self.__dict__


class FakeStreamlit:
    """The widgets the bar draws, recorded in the region each landed in."""

    def __init__(
        self,
        *,
        preset: str = "",
        chosen: str = "",
        picked: Sequence[date] = (),
    ) -> None:
        self.session_state = SessionState()
        if preset:
            self.session_state.preset = preset
        self.open_region = ""
        self.bordered: list[bool] = []
        self.column_request: tuple | None = None
        self.slots: list[RecordingRegion] = []
        self.drawn: list[tuple[str, str, Any]] = []
        self._chosen = chosen
        self._picked = list(picked)

    def container(self, border: bool = False) -> RecordingRegion:
        self.bordered.append(border)
        return RecordingRegion(self, CARD)

    def columns(
        self,
        widths: Any,
        vertical_alignment: str = "",
    ) -> list[RecordingRegion]:
        self.column_request = (tuple(widths), vertical_alignment)
        self.slots = [RecordingRegion(self, name) for name in SLOT_NAMES]
        return self.slots

    def markdown(self, markup: str, unsafe_allow_html: bool = False) -> None:
        self.drawn.append(
            (MARKDOWN, self.open_region, (markup, unsafe_allow_html)),
        )

    def radio(self, label: str, **options: Any) -> str:
        self.drawn.append((RADIO, self.open_region, options))
        return self._chosen or options["options"][options["index"]]

    def date_input(self, label: str, **bounds: Any) -> date:
        self.drawn.append(
            (PICKER, self.open_region, {"label": label, **bounds}),
        )
        if self._picked:
            return self._picked.pop(0)
        return bounds["value"]

    def empty(self) -> RecordingRegion:
        placeholder = RecordingRegion(self, self.open_region)
        self.drawn.append((PLACEHOLDER, self.open_region, placeholder))
        return placeholder


def drawn_as(page: FakeStreamlit, kind: str) -> list[tuple[str, Any]]:
    """Every widget of one kind, as the region it landed in and its request."""
    return [
        (region, request)
        for drawn_kind, region, request in page.drawn
        if drawn_kind == kind
    ]
