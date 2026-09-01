# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The knob a page's reads are issued under, and the refusal without a database."""

from __future__ import annotations

import os
import unittest
from importlib import import_module
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from orchestrator.observability.dashboard import (
    date_filter,
    page_controls,
    page_models,
    read_mode,
    windows,
)
from tests.observability.dashboard import (
    dashboard_test_support as fixtures,
    page_controls_test_support as fakes,
    reload_helpers,
)

_ANALYTICS_SETTINGS = "orchestrator.observability.analytics.settings"

_DB_URL_ATTRIBUTE = "ANALYTICS_DB_URL"

# The knob's name is what an operator's `.env` is written against, so the cases
# below set that variable rather than the constant naming it: a rename would be
# a migration for every install that already carries the line.
_PARALLEL_READS_ENV = "DASHBOARD_PARALLEL_READS"

_ENABLED = "on"

_TRUTHY_SPELLINGS = ("1", "true", _ENABLED, "yes", "ON", "Yes", "TRUE")

_FALSY_SPELLINGS = ("0", "false", "off", "no", "disabled", "none")

_PADDED_SPELLING = "  on  "

_CONFIGURED_DB_URL = "postgresql://h/db"

# What makes the refusal actionable: the knob to set and the two documents that
# say what to set it to.
_MESSAGE_POINTERS = (
    _DB_URL_ATTRIBUTE,
    ".env.example.advanced",
    "docs/configuration.md",
)

# What one page load is staged against, whichever world the reload built: the
# extent a window could be picked from at all, the window the bar is stood in
# for with, and a sidebar vocabulary empty enough that the selections normalize
# without naming anything.
_STAGED_EXTENT = fixtures.data_extent(fixtures.MAY01, fixtures.MAY28)

_STAGED_WINDOW = windows.to_window(fixtures.MAY02, fixtures.MAY06)

_STAGED_OPTIONS = SimpleNamespace(repos=(), events=(), stages=())

_BAR_ATTRIBUTE = "render_date_filter_bar"


def _staged_reads(page: fakes.FakeStreamlit):
    """Stage one page load against the current knob, issuing no read.

    The controls are drawn against a stand-in Streamlit and the bar is answered
    for, so what comes back is the plan alone -- which is where the flag the
    world under test set has to have landed.
    """
    with patch.object(
        date_filter,
        _BAR_ATTRIBUTE,
        side_effect=fakes.BarAnswer(page, _STAGED_WINDOW),
    ):
        prepared = page_controls.prepare_dashboard_page(
            page_models.DashboardModules(st=page, pd=None, theme=None),
            _STAGED_EXTENT,
            _STAGED_OPTIONS,
        )
    return prepared.reads


class ParseParallelReadsFlagTest(unittest.TestCase):
    """The vocabulary the fan-out knob is spelled in.

    Default off so the sequential behavior holds until an operator opts in,
    and the truthy spellings are the ones the codebase's other boolean knobs
    accept (`DECOMPOSE=on` etc.) so a playbook's spelling carries over.
    """

    def test_unset_and_empty_stay_sequential(self) -> None:
        for environment in ({}, {_PARALLEL_READS_ENV: ""}):
            with self.subTest(environment=environment), patch.dict(os.environ, environment, clear=True):
                self.assertFalse(read_mode.parse_parallel_reads_flag())

    def test_truthy_spellings_enable_the_fan_out(self) -> None:
        for spelling in _TRUTHY_SPELLINGS:
            with self.subTest(spelling=spelling), patch.dict(
                os.environ, {_PARALLEL_READS_ENV: spelling}, clear=True,
            ):
                self.assertTrue(read_mode.parse_parallel_reads_flag())

    def test_anything_else_keeps_the_reads_sequential(self) -> None:
        for spelling in _FALSY_SPELLINGS:
            with self.subTest(spelling=spelling), patch.dict(
                os.environ, {_PARALLEL_READS_ENV: spelling}, clear=True,
            ):
                self.assertFalse(read_mode.parse_parallel_reads_flag())

    def test_surrounding_whitespace_is_stripped(self) -> None:
        # Operators paste env values out of playbooks, so a stray newline must
        # not silently fall back to the sequential path.
        with patch.dict(
            os.environ, {_PARALLEL_READS_ENV: _PADDED_SPELLING}, clear=True,
        ):
            self.assertTrue(read_mode.parse_parallel_reads_flag())


class DashboardParallelReadsTest(unittest.TestCase):
    """The flag every page load of one process is issued under.

    What this owner reports and what a load actually runs are asserted apart,
    because they reach the flag by different routes: the owner reads its own
    global, while the staged plan comes from the sibling owner that bound this
    module once, at its own import, and is not rebuilt with it. A re-parse that
    replaced this module rather than re-running it in place would satisfy the
    first and leave the second issuing the world before it.
    """

    def test_the_import_binds_what_was_asked_for(self) -> None:
        for spelling, expected in ((_ENABLED, True), ("", False)):
            with self.subTest(spelling=spelling), reload_helpers.read_mode_reloaded_under(
                {_PARALLEL_READS_ENV: spelling},
            ) as owner:
                self.assertIs(owner.DASHBOARD_PARALLEL_READS, expected)
                self.assertIs(
                    owner.dashboard_parallel_reads_enabled(), expected,
                )

    def test_the_staged_load_is_issued_that_way(self) -> None:
        # The plan a page carries between its two waves is what the fan-out is
        # actually driven off, so it is the reading an operator's `parallel=`
        # log line and the threads behind it come from.
        for spelling, expected in ((_ENABLED, True), ("", False)):
            with self.subTest(spelling=spelling):
                with reload_helpers.read_mode_reloaded_under(
                    {_PARALLEL_READS_ENV: spelling},
                ):
                    staged = _staged_reads(fakes.FakeStreamlit())

                self.assertIs(staged.parallel, expected)

    def test_a_later_env_change_does_not_move_it(self) -> None:
        # An operator turns the fan-out on by restarting the Streamlit process,
        # so what a load reads is what the import decided: re-parsing per
        # render could issue one page's reads two different ways.
        with (
            reload_helpers.read_mode_reloaded_under({}) as owner,
            patch.dict(os.environ, {_PARALLEL_READS_ENV: _ENABLED}),
        ):
            self.assertFalse(owner.dashboard_parallel_reads_enabled())


class DbUnconfiguredMessageTest(unittest.TestCase):
    """What a page is refused with when there is no database to read.

    The knob's own vocabulary -- an unset variable, an empty value, and the
    `off` / `disabled` / `none` sentinels that collapse to no URL -- belongs to
    the analytics configuration owner, so what is read here is the answer that
    owner already gave, off whichever settings holder the name resolves to.
    """

    def test_no_configured_url_is_refused(self) -> None:
        with patch.object(self._analytics(), _DB_URL_ATTRIBUTE, None):
            self.assertEqual(
                read_mode.db_unconfigured_message(),
                read_mode.UNCONFIGURED_DB_MESSAGE,
            )

    def test_a_configured_url_reads_through(self) -> None:
        with patch.object(
            self._analytics(), _DB_URL_ATTRIBUTE, _CONFIGURED_DB_URL,
        ):
            self.assertIsNone(read_mode.db_unconfigured_message())

    def test_the_message_says_what_to_set(self) -> None:
        for pointer in _MESSAGE_POINTERS:
            with self.subTest(pointer=pointer):
                self.assertIn(pointer, read_mode.UNCONFIGURED_DB_MESSAGE)

    def _analytics(self) -> ModuleType:
        """The holder instance the knob a page reads is bound on."""
        return import_module(_ANALYTICS_SETTINGS)


if __name__ == "__main__":
    unittest.main()
