# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The call shape the drill-down is still reachable under, bound to its state.

The render pipeline threads the frozen shapes the page-state owner holds, but
the drill-down predates them: a caller outside that pipeline names the seven
keyword arguments the section was written with. This owner is where the two
spellings meet, so the section itself is written against the state every panel
beside it is handed and nothing on the page carries the older vocabulary.

Those keywords are bound through a declared signature rather than spelled as
parameters, and the same object is stamped onto the adapter. That is what keeps
the historical call shape one thing: what a caller may pass, what the typed
request holds, and what ``inspect.signature`` reports cannot drift into three
descriptions of one call. Binding also keeps the shape strict -- an unknown
keyword or a missing one raises here rather than reaching the render as a
half-filled request.

The theme handle is the one a drill-down has no use for: it draws no figure and
paints no card, so it is handed the modules shape with that slot left
unanswered rather than a fifth shape of its own.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from inspect import Parameter, Signature
from typing import Any

from orchestrator.observability.dashboard import drilldown, page_models


@dataclass(frozen=True)
class DrilldownRequest:
    st: Any
    pd: Any
    window: Any
    repo_filter: str | None
    issue_input_parsed: int | None
    event_filter: Sequence[str] | None
    stage_filter: Sequence[str] | None


def render_drilldown(*args: Any, **kwargs: Any) -> None:
    """Render a drill-down through the historical dashboard call shape."""
    bound = _DRILLDOWN_SIGNATURE.bind(*args, **kwargs)
    request = DrilldownRequest(**bound.arguments)
    modules = page_models.DashboardModules(
        st=request.st,
        pd=request.pd,
        theme=None,
    )
    filters = page_models.DashboardFilters(
        window=request.window,
        repo=request.repo_filter,
        issue_input=request.issue_input_parsed,
        events=request.event_filter,
        stages=request.stage_filter,
    )
    drilldown.render_drilldown_view(modules, filters)


_KEYWORD_ONLY = Parameter.KEYWORD_ONLY
_DRILLDOWN_SIGNATURE = Signature(
    parameters=(
        Parameter("st", _KEYWORD_ONLY),
        Parameter("pd", _KEYWORD_ONLY),
        Parameter("window", _KEYWORD_ONLY),
        Parameter("repo_filter", _KEYWORD_ONLY),
        Parameter("issue_input_parsed", _KEYWORD_ONLY),
        Parameter("event_filter", _KEYWORD_ONLY),
        Parameter("stage_filter", _KEYWORD_ONLY),
    ),
)
render_drilldown.__signature__ = _DRILLDOWN_SIGNATURE
