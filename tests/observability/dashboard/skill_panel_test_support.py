# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The page surface the two skill cards are drawn onto, faked.

Streamlit is in the optional `dashboard` group and a card is handed its `st`
rather than reaching for one, so the cases drive a whole render against a
stand-in that records what each call was given. What they read back is the
markup, captions, and notices in the order they were written, and the label and
open state of every expander, which is what makes the order two panels are
drawn in and the flag one is folded behind observable rather than inferred from
the source.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

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
    """One fold-out the render opened, and whether it opened expanded."""

    label: str
    expanded: bool


class NullContext:
    """`with`-usable stand-in for `st.container(...)` / `st.expander(...)`."""

    def __enter__(self) -> "NullContext":
        return self

    def __exit__(self, *exc: Any) -> bool:
        return False


class PanelStreamlit:
    """Fake `st` recording the calls a skill card makes."""

    def __init__(self, query_params: Optional[Mapping[str, str]] = None):
        self.query_params = query_params or {}
        self.markdowns: list[str] = []
        self.captions: list[str] = []
        self.notices: list[str] = []
        self.expanders: list[Expander] = []

    def container(self, **kwargs: Any) -> NullContext:
        return NullContext()

    def expander(self, label: str, **kwargs: Any) -> NullContext:
        self.expanders.append(Expander(label, bool(kwargs.get("expanded"))))
        return NullContext()

    def markdown(self, markup: str, **kwargs: Any) -> None:
        self.markdowns.append(markup)

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
