# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The two unfiltered reads a page opens on, and what a failed one costs.

Streamlit lives in the optional `dashboard` dependency group, so the cases
below hand the load a stand-in that records what it was asked to cache and
what it was asked to say -- which is the whole of what this owner reaches
Streamlit for.
"""

from __future__ import annotations

import unittest
from collections.abc import Callable
from inspect import signature
from types import MappingProxyType
from typing import Any
from unittest.mock import patch

from orchestrator.observability.analytics.query import raw_reads
from orchestrator.observability.analytics.query.connections import (
    AnalyticsReadError,
)
from orchestrator.observability.dashboard import scoped_reads, static_metadata


_TTL_FIVE_MINUTES = 300

_EXTENT = "extent"

_OPTIONS = "options"

_READ_FAILED = "connection refused"

_DB_URL_KNOB = "ANALYTICS_DB_URL"

_SCOPED_READ_ATTRIBUTE = "scoped_read"

# What each unfiltered read is answered with, keyed by the query owner's read
# it names, so a case can say which of the two a value came back from.
_ANSWERS = MappingProxyType({
    raw_reads.get_data_extent: _EXTENT,
    raw_reads.get_filter_options: _OPTIONS,
})


class _FakeStreamlit:
    """The cache, banner, and stop this owner reaches Streamlit for."""

    def __init__(self) -> None:
        self.cache_options: list[dict[str, Any]] = []
        self.cached_readers: list[Callable[[], Any]] = []
        self.errors: list[str] = []
        self.stops = 0

    def cache_data(self, **cache_options: Any) -> Callable[..., Any]:
        self.cache_options.append(cache_options)

        def decorator(reader: Callable[[], Any]) -> Callable[[], Any]:
            self.cached_readers.append(reader)
            return reader

        return decorator

    def error(self, message: str) -> None:
        self.errors.append(message)

    def stop(self) -> None:
        self.stops += 1


def _answer_read(getter: Callable[..., Any], **read_filters: Any) -> Any:
    return _ANSWERS[getter]


def _fail_read(getter: Callable[..., Any], **read_filters: Any) -> Any:
    raise AnalyticsReadError(_READ_FAILED)


class StaticMetadataReaderTest(unittest.TestCase):
    """Each read names its query owner and carries nothing to key on."""

    def test_each_reader_uses_the_shared_scope(self) -> None:
        for reader, expected in (
            (static_metadata.read_data_extent, _EXTENT),
            (static_metadata.read_filter_options, _OPTIONS),
        ):
            with self.subTest(reader=reader.__name__), patch.object(
                scoped_reads, _SCOPED_READ_ATTRIBUTE, _answer_read,
            ):
                self.assertEqual(reader(), expected)

    def test_neither_reader_takes_an_argument(self) -> None:
        # An empty signature is what makes the cache key empty. A parameter
        # here -- the connection above all -- would land in that key, and
        # Streamlit cannot hash a psycopg connection.
        for reader in (
            static_metadata.read_data_extent,
            static_metadata.read_filter_options,
        ):
            with self.subTest(reader=reader.__name__):
                self.assertEqual(signature(reader).parameters, {})


class StaticMetadataLoadTest(unittest.TestCase):
    """What one page load asks Streamlit to cache, and reads back."""

    def test_the_pair_comes_back_extent_first(self) -> None:
        # The caller unpacks the pair positionally into the extent it picks a
        # window from and the options it draws the filter bar from.
        st = _FakeStreamlit()

        with patch.object(scoped_reads, _SCOPED_READ_ATTRIBUTE, _answer_read):
            self.assertEqual(
                static_metadata.read_static_metadata(st=st),
                (_EXTENT, _OPTIONS),
            )

    def test_both_reads_cached_under_that_ttl(self) -> None:
        # Neither read is narrowed by anything the operator can change, so
        # both are cached against the sync's ingest cadence rather than the
        # rerun cadence -- and without a spinner, because the topbar and the
        # sidebar are chrome rather than a widget somebody asked to reload.
        st = _FakeStreamlit()

        with patch.object(scoped_reads, _SCOPED_READ_ATTRIBUTE, _answer_read):
            static_metadata.read_static_metadata(st=st)

        self.assertEqual(
            st.cache_options,
            [
                {"show_spinner": False, "ttl": _TTL_FIVE_MINUTES},
                {"show_spinner": False, "ttl": _TTL_FIVE_MINUTES},
            ],
        )
        self.assertEqual(
            st.cached_readers,
            [
                static_metadata.read_data_extent,
                static_metadata.read_filter_options,
            ],
        )

    def test_the_declared_ttl_is_five_minutes(self) -> None:
        # Pinned so a change to the span is a deliberate one: five minutes is
        # long enough to absorb the rerun cadence and short enough that a
        # freshly synced repo or event value shows up within one sync cycle.
        self.assertEqual(
            static_metadata.STATIC_METADATA_TTL_SECONDS, _TTL_FIVE_MINUTES,
        )

    def test_a_failed_read_stops_the_page(self) -> None:
        # This pair is the page's first read, so there is no window to draw
        # anything else in: the run says which knob to check and stops rather
        # than leaving every widget below to fail on its own.
        st = _FakeStreamlit()

        with patch.object(scoped_reads, _SCOPED_READ_ATTRIBUTE, _fail_read):
            self.assertIsNone(static_metadata.read_static_metadata(st=st))

        self.assertEqual(st.stops, 1)
        self.assertEqual(len(st.errors), 1)
        self.assertIn(_DB_URL_KNOB, st.errors[0])
        self.assertIn(_READ_FAILED, st.errors[0])


if __name__ == "__main__":
    unittest.main()
