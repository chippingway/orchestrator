# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The knob a page's reads are issued under, and the refusal without a database."""

from __future__ import annotations

import os
import sys
import unittest
from collections.abc import Iterator
from contextlib import contextmanager
from importlib import import_module
from types import ModuleType
from unittest.mock import patch

from orchestrator.observability.dashboard import read_mode
from tests.dashboard_reload_helpers import reload_dashboard


_PACKAGE = "orchestrator.observability.dashboard"

_OWNER_ATTRIBUTE = "read_mode"

_OWNER = f"{_PACKAGE}.{_OWNER_ATTRIBUTE}"

_ANALYTICS = "orchestrator.analytics"

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


@contextmanager
def _owner_imported_under(environment: dict[str, str]) -> Iterator[ModuleType]:
    """Re-import the owner against `environment`, then put this world's back.

    The flag is bound while the owner imports, so an environment case is a
    re-import rather than a patched attribute -- and the entering module is
    reinstated under both names a later importer resolves it by, the
    `sys.modules` entry and the attribute on the package it hangs off, because
    every historical import site binds this owner's objects once and would
    otherwise be split across two copies of it.
    """
    package = import_module(_PACKAGE)
    entering = import_module(_OWNER)
    try:
        with patch.dict(os.environ, environment, clear=True):
            sys.modules.pop(_OWNER, None)
            package.__dict__.pop(_OWNER_ATTRIBUTE, None)
            yield import_module(_OWNER)
    finally:
        sys.modules[_OWNER] = entering
        package.__dict__[_OWNER_ATTRIBUTE] = entering


class ParseParallelReadsFlagTest(unittest.TestCase):
    """The vocabulary the fan-out knob is spelled in.

    Default off so the sequential behavior holds until an operator opts in,
    and the truthy spellings are the ones the codebase's other boolean knobs
    accept (`DECOMPOSE=on` etc.) so a playbook's spelling carries over.
    """

    def test_unset_and_empty_stay_sequential(self) -> None:
        for environment in ({}, {_PARALLEL_READS_ENV: ""}):
            with self.subTest(environment=environment):
                with patch.dict(os.environ, environment, clear=True):
                    self.assertFalse(read_mode.parse_parallel_reads_flag())

    def test_truthy_spellings_enable_the_fan_out(self) -> None:
        for spelling in _TRUTHY_SPELLINGS:
            with self.subTest(spelling=spelling):
                with patch.dict(
                    os.environ, {_PARALLEL_READS_ENV: spelling}, clear=True,
                ):
                    self.assertTrue(read_mode.parse_parallel_reads_flag())

    def test_anything_else_keeps_the_reads_sequential(self) -> None:
        for spelling in _FALSY_SPELLINGS:
            with self.subTest(spelling=spelling):
                with patch.dict(
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
    """The flag every page load of one process is issued under."""

    def test_the_import_binds_what_was_asked_for(self) -> None:
        for spelling, expected in ((_ENABLED, True), ("", False)):
            with self.subTest(spelling=spelling):
                with _owner_imported_under(
                    {_PARALLEL_READS_ENV: spelling},
                ) as owner:
                    self.assertIs(owner.DASHBOARD_PARALLEL_READS, expected)
                    self.assertIs(
                        owner.dashboard_parallel_reads_enabled(), expected,
                    )

    def test_a_later_env_change_does_not_move_it(self) -> None:
        # An operator turns the fan-out on by restarting the Streamlit process,
        # so what a load reads is what the import decided: re-parsing per
        # render could issue one page's reads two different ways.
        with _owner_imported_under({}) as owner:
            with patch.dict(os.environ, {_PARALLEL_READS_ENV: _ENABLED}):
                self.assertFalse(owner.dashboard_parallel_reads_enabled())


class ReloadedPageFlagTest(unittest.TestCase):
    """The page answers with the flag the world it was built in decided.

    The lazy facade and the state hub in front of this owner publish the flag
    rather than re-deriving it, so a dashboard loaded against one environment
    has to issue its reads the way that environment asked for -- which is also
    what keeps a knob parsed at import testable at all.
    """

    def test_the_facade_reads_the_reloaded_world(self) -> None:
        for spelling, expected in ((_ENABLED, True), ("", False)):
            with self.subTest(spelling=spelling):
                _, dashboard = reload_dashboard(
                    {_PARALLEL_READS_ENV: spelling},
                )
                self.assertIs(
                    dashboard.dashboard_parallel_reads_enabled(), expected,
                )
                self.assertIs(dashboard.DASHBOARD_PARALLEL_READS, expected)


class DbUnconfiguredMessageTest(unittest.TestCase):
    """What a page is refused with when there is no database to read.

    The knob's own vocabulary -- an unset variable, an empty value, and the
    `off` / `disabled` / `none` sentinels that collapse to no URL -- belongs to
    the analytics configuration owner, so what is read here is the answer that
    owner already gave, off whichever analytics package the name resolves to.
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
        """The package instance the knob a page reads is bound on."""
        return import_module(_ANALYTICS)


if __name__ == "__main__":
    unittest.main()
