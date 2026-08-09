# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The call shape a caller outside the render pipeline still reaches.

The adapter is bound rather than driven here: the render itself is intercepted
on the owner it lives on, so a case reads back the two shapes the keywords were
rebuilt into instead of the markup a page would draw from them.
"""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from inspect import signature
from types import MappingProxyType
from typing import Any
from unittest.mock import patch

from orchestrator.observability.dashboard import (
    drilldown,
    drilldown_request,
    windows,
)


_REPO = "owner/repo"

_ISSUE = 1181

_YEAR = 2026

_MAY = 5

_WINDOW = windows.DateWindow(
    start=datetime(_YEAR, _MAY, 1, tzinfo=timezone.utc),
    end=datetime(_YEAR, _MAY, 8, tzinfo=timezone.utc),
)

_EVENTS = ("stage_entered", "agent_exit")

_STAGES = ("implementing",)

_RENDER_ATTRIBUTE = "render_drilldown_view"

# The seven keywords the section was written with, in the order a caller has
# always been able to read them off `inspect.signature`.
_CALL_SHAPE = (
    "st",
    "pd",
    "window",
    "repo_filter",
    "issue_input_parsed",
    "event_filter",
    "stage_filter",
)

_ST = object()

_PD = object()

_CALL = MappingProxyType({
    "st": _ST,
    "pd": _PD,
    "window": _WINDOW,
    "repo_filter": _REPO,
    "issue_input_parsed": _ISSUE,
    "event_filter": _EVENTS,
    "stage_filter": _STAGES,
})


def _rendered(**overrides: Any) -> tuple:
    """The modules and filters one historical call is rebuilt into."""
    call = dict(_CALL)
    call.update(overrides)
    with patch.object(drilldown, _RENDER_ATTRIBUTE) as render:
        drilldown_request.render_drilldown(**call)
        render.assert_called_once()
        return render.call_args.args


class CallShapeTest(unittest.TestCase):
    """The keywords a caller passes are the ones the adapter reports."""

    def test_the_seven_keywords_are_reported_in_order(self) -> None:
        self.assertEqual(
            tuple(signature(drilldown_request.render_drilldown).parameters),
            _CALL_SHAPE,
        )

    def test_the_reported_shape_is_the_bound_one(self) -> None:
        # One object behind both, so what `inspect.signature` says and what a
        # call is accepted under cannot become two descriptions.
        for unbound in ({}, {"repo_filter": None}):
            with self.subTest(call=unbound):
                with self.assertRaises(TypeError):
                    drilldown_request.render_drilldown(**unbound)

    def test_every_keyword_is_keyword_only(self) -> None:
        # Seven arguments of which four are optional selections: positional
        # order here is how a repository ends up read as an issue number.
        with self.assertRaises(TypeError):
            drilldown_request.render_drilldown(_ST, _PD)


class RequestRebuildTest(unittest.TestCase):
    """A historical call is rebuilt into the state the section renders."""

    def test_the_handles_travel_as_the_modules_shape(self) -> None:
        # A drill-down draws no figure and paints no card, so the one handle
        # it has no use for is left unanswered rather than invented.
        modules, _ = _rendered()
        self.assertEqual(
            (modules.st, modules.pd, modules.theme),
            (_ST, _PD, None),
        )

    def test_the_selections_travel_as_filters(self) -> None:
        _, filters = _rendered()
        self.assertEqual(
            (
                filters.window,
                filters.repo,
                filters.issue_input,
                filters.events,
                filters.stages,
            ),
            (_WINDOW, _REPO, _ISSUE, _EVENTS, _STAGES),
        )

    def test_an_unscoped_number_stays_unscoped(self) -> None:
        # The adapter rebuilds rather than decides: whether a number narrows
        # anything is the filters shape's own reading, and re-deriving it here
        # is how the two answers drift apart.
        _, filters = _rendered(repo_filter=None)
        self.assertEqual(filters.issue_input, _ISSUE)
        self.assertIsNone(filters.issue)


class RequestImmutabilityTest(unittest.TestCase):
    """The bound request is read once and cannot be narrowed after."""

    def test_the_request_is_frozen(self) -> None:
        request = drilldown_request.DrilldownRequest(**_CALL)
        with self.assertRaises(FrozenInstanceError):
            request.repo_filter = None


if __name__ == "__main__":
    unittest.main()
