# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The stand-in the top of the page is drawn against.

Streamlit lives in the optional `dashboard` dependency group, so the cases
record what the controls asked for instead of rendering them: which widget was
drawn, whether it landed inside the sidebar, and what it was offered and seeded
with. One list carries all of them in the order they were drawn, which is what
lets a case say the topbar placeholder was taken after the sidebar and before
the filter bar rather than only that it was taken.

A box answers with the option its index preselected and a multiselect with the
whole default it was offered, the way untouched ones do; the constructor's
arguments are how a case says the operator picked something else, with the
multiselect answers queued in the order the two are drawn. The session is a
plain object, so a case opening on a zone somebody already picked just sets the
attribute on it.

The bar the days are picked in is the date owner's, so it is stood in for
rather than drawn. Its stand-in records into the same list, which is what lets
a case place it among the widgets above it, and answers with the window and
slot the caller is then held to.

The cache decorator hands each reader straight back. What one is wrapped in and
how long it is kept are the read plan's decisions and pinned there; here the
point is only that a staged wave arrives with its key already bound, and an
undecorated reader is what makes that key readable.
"""

from __future__ import annotations

from typing import Any, Callable, Sequence


# The one region the filter widgets are drawn inside, and what a widget drawn
# on the page itself records instead.
SIDEBAR = "sidebar"

PAGE = ""

# The widget kinds one pass is recorded under, so a case reads back only the
# ones it is about.
HEADER = "header"

REPO_BOX = "selectbox"

MULTISELECT = "multiselect"

ISSUE_BOX = "text_input"

PLACEHOLDER = "empty"

# The bar the days are picked in. It is the date owner's, so a case patches it
# and records the call under this kind to place it among the widgets above.
FILTER_BAR = "date_filter_bar"


class SidebarRegion:
    """The sidebar, entered for the widgets drawn inside it."""

    def __init__(self, page: FakeStreamlit) -> None:
        self._page = page

    def __enter__(self) -> SidebarRegion:
        self._page.open_region = SIDEBAR
        return self

    def __exit__(self, *exception: Any) -> bool:
        self._page.open_region = PAGE
        return False


class SessionState:
    """The two ways the page reaches the session: membership and attribute."""

    def __contains__(self, key: str) -> bool:
        return key in self.__dict__


class FakeStreamlit:
    """The widgets the top of the page draws, in the region each landed in."""

    def __init__(
        self,
        *,
        repo: str = "",
        multiselects: Sequence[Sequence[str]] = (),
        issue: str = "",
    ) -> None:
        self.session_state = SessionState()
        self.sidebar = SidebarRegion(self)
        self.open_region = PAGE
        self.drawn: list[tuple[str, str, Any]] = []
        self._repo = repo
        self._multiselects = [list(answer) for answer in multiselects]
        self._issue = issue

    def header(self, title: str) -> None:
        self.drawn.append((HEADER, self.open_region, title))

    def selectbox(self, label: str, options: Sequence[str], index: int) -> str:
        self.drawn.append(
            (REPO_BOX, self.open_region, {"label": label, "options": options}),
        )
        return self._repo or options[index]

    def multiselect(
        self,
        label: str,
        options: Sequence[str],
        **seeding: Any,
    ) -> list:
        self.drawn.append((
            MULTISELECT,
            self.open_region,
            {"label": label, "options": options, **seeding},
        ))
        if self._multiselects:
            return self._multiselects.pop(0)
        return list(seeding["default"])

    def text_input(self, label: str, **seeding: Any) -> str:
        self.drawn.append(
            (ISSUE_BOX, self.open_region, {"label": label, **seeding}),
        )
        return self._issue or seeding["value"]

    def empty(self) -> object:
        placeholder = object()
        self.drawn.append((PLACEHOLDER, self.open_region, placeholder))
        return placeholder

    def cache_data(self, **caching: Any) -> Callable:
        return pass_through


class BarAnswer:
    """The filter bar's stand-in, recorded among the widgets around it.

    The bar itself is the date owner's and pinned there, so a case patches it
    with one of these: the call lands in the same `drawn` list the sidebar
    widgets do, which is what places it in the pass, and the window and slot it
    answers with are the ones the caller is then held to.
    """

    def __init__(
        self,
        page: FakeStreamlit,
        window: Any,
        meta_slot: Any = None,
    ) -> None:
        self.page = page
        self.window = window
        self.meta_slot = meta_slot

    def __call__(self, **request: Any) -> tuple:
        self.page.drawn.append((FILTER_BAR, PAGE, request))
        return self.window, self.meta_slot


def pass_through(reader: Callable) -> Callable:
    """Stand in for `st.cache_data`, leaving the reader itself bound."""
    return reader


def drawn_as(page: FakeStreamlit, kind: str) -> list[tuple[str, Any]]:
    """Every widget of one kind, as the region it landed in and its request."""
    return [
        (region, request)
        for drawn_kind, region, request in page.drawn
        if drawn_kind == kind
    ]
