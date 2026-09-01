# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The page surface the two skill cards are drawn onto, faked.

Streamlit is in the optional `dashboard` group and a card is handed its `st`
rather than reaching for one, so the cases drive a whole render against a
stand-in that records what each call was given. What they read back is the
markup, captions, and notices in the order they were written, and the label,
open state, and own markup of every expander, which is what makes the order two
panels are drawn in, the flag one is folded behind, and which table landed in
which fold observable rather than inferred from the source.

An expander records the markup written while it is open as well as appending
it to the page, so a case reading one section's table apart from its siblings
names the fold rather than counting payloads: several sections drawing the same
panel class is exactly the shape a positional read would misattribute.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from orchestrator.observability.analytics.query.skill_models import (
    SkillTriggerRateRow,
)

DEVELOPER = "developer"

CLAUDE = "claude"

# A cohort that ran five times, so a case names how many of those runs reached
# for a skill and leaves the denominator alone.
COHORT_RUNS = 5


def rate_row(*, skill_runs: int = 2) -> SkillTriggerRateRow:
    """One aggregate trigger-rate row for the cohort named here."""
    return SkillTriggerRateRow(
        agent_role=DEVELOPER,
        backend=CLAUDE,
        runs=COHORT_RUNS,
        skill_runs=skill_runs,
        total_triggers=skill_runs,
    )


@dataclass(frozen=True)
class Expander:
    """One fold-out the render opened, how it opened, and what it drew."""

    label: str
    expanded: bool
    markdowns: list[str] = field(default_factory=list)


class NullContext:
    """`with`-usable stand-in for `st.container(...)` / `st.expander(...)`.

    A container records nothing, while a fold-out names itself on the page for
    as long as it is open, so what was written inside it is attributed to it.
    """

    def __init__(
        self,
        page: PanelStreamlit | None = None,
        fold: Expander | None = None,
    ):
        self.page = page
        self.fold = fold

    def __enter__(self) -> "NullContext":
        if self.page is not None:
            self.page.open_fold = self.fold
        return self

    def __exit__(self, *exc: Any) -> bool:
        if self.page is not None:
            self.page.open_fold = None
        return False


class PanelStreamlit:
    """Fake `st` recording the calls a skill card makes."""

    def __init__(self, query_params: Mapping[str, str] | None = None):
        self.query_params = query_params or {}
        self.markdowns: list[str] = []
        self.captions: list[str] = []
        self.notices: list[str] = []
        self.expanders: list[Expander] = []
        self.open_fold: Expander | None = None

    def container(self, **kwargs: Any) -> NullContext:
        return NullContext()

    def expander(self, label: str, **kwargs: Any) -> NullContext:
        fold = Expander(label, bool(kwargs.get("expanded")))
        self.expanders.append(fold)
        return NullContext(self, fold)

    def markdown(self, markup: str, **kwargs: Any) -> None:
        self.markdowns.append(markup)
        if self.open_fold is not None:
            self.open_fold.markdowns.append(markup)

    def caption(self, text: str) -> None:
        self.captions.append(text)

    def show_notice(self, text: str) -> None:
        """Record an `st.info(...)`, which the lookup below routes here."""
        self.notices.append(text)

    def __getattr__(self, attribute_name: str) -> Any:
        if attribute_name == "info":
            return self.show_notice
        raise AttributeError(attribute_name)


def all_markup(page: PanelStreamlit) -> str:
    """Every payload the render wrote, in the order it wrote them."""
    return "".join(page.markdowns)


def panel_markup(page: PanelStreamlit, marker: str) -> str:
    """The one payload carrying `marker`, so a case names its own table."""
    return next(markup for markup in page.markdowns if marker in markup)


def fold_markup(page: PanelStreamlit, label_fragment: str) -> str:
    """Everything drawn inside the fold-out whose label carries the words."""
    fold = next(
        opened
        for opened in page.expanders
        if label_fragment in opened.label
    )
    return "".join(fold.markdowns)
