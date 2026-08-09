# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Which read a skill panel is drawn from, and under which key.

An adapter here settles two things and nothing else: the query owner's read a
panel is answered by, and the key that read is issued under. So the cases below
patch the binding all three travel through and read back what was handed to it,
rather than standing a database up to observe the same two facts through rows.

The key is built by the filter owner rather than written out here, because what
an adapter owes a page is its own key passed through untouched -- a hand-rolled
tuple would keep passing after the two spellings drifted apart.
"""

from __future__ import annotations

import inspect
import unittest
from typing import Any
from unittest.mock import patch

from orchestrator.observability.analytics.query import skill_reads
from orchestrator.observability.dashboard import (
    filter_binding,
    filters,
    skills,
    windows,
)
from tests.observability.dashboard.dashboard_test_support import (
    MAY01,
    MAY07,
    utc_midnight,
)


_REPO = "owner/repo"

_EVENTS = ("stage_entered", "agent_exit")

_STAGES = ("implementing",)

_ISSUE = 42

_READ_FILTERED_ATTRIBUTE = "read_filtered"

# The key a run narrowed to one repo and issue stores its reads under.
_KEY = filters.cache_key(
    windows.DateWindow(start=utc_midnight(MAY01), end=utc_midnight(MAY07)),
    _REPO,
    _EVENTS,
    _STAGES,
    _ISSUE,
)

# What a page hands an adapter, which is what its cached key is built out of.
# A connection may never appear here: `st.cache_data` would have to hash a
# psycopg connection, which is unhashable, and a stringified one would make
# every refreshed socket look like a cache miss.
_KEY_ONLY = ("key",)

# Each skill-panel read and the query owner's read it names: the aggregate
# rates an invocation-level table is drawn from, the per-repository trigger
# cells beneath it, and the per-session adoption cells above both.
_SKILL_READS = (
    (skills.read_skill_trigger_rates, skill_reads.get_skill_trigger_rates),
    (skills.read_skill_trigger_matrix, skill_reads.get_skill_trigger_matrix),
    (skills.read_skill_adoption, skill_reads.get_skill_adoption),
)


class SkillReadOwnerTest(unittest.TestCase):
    """Each skill read issues its own query owner's read under the page's key."""

    def test_each_read_names_its_query_owner(self) -> None:
        # Identity, not behavior: a read bound to a copy of the owner's
        # function would answer every panel correctly and still leave a patch
        # aimed at that owner intercepting nothing.
        for read, getter in _SKILL_READS:
            with self.subTest(read=read.__name__):
                issued = self._issued(read)

                self.assertIs(issued.args[0], getter)
                self.assertIs(issued.args[1], _KEY)

    def test_no_read_narrows_by_anything_else(self) -> None:
        # A skill panel is narrowed by the window and selections every other
        # read shares, so a filter passed beside the key here would be one the
        # page never asked for.
        for read, _ in _SKILL_READS:
            with self.subTest(read=read.__name__):
                self.assertEqual(self._issued(read).kwargs, {})

    def _issued(self, read: Any) -> Any:
        """What one adapter handed the binding, having handed its rows back."""
        with patch.object(
            filter_binding, _READ_FILTERED_ATTRIBUTE,
        ) as read_filtered:
            read_rows = read(_KEY)
            self.assertIs(read_rows, read_filtered.return_value)
            return read_filtered.call_args


class CacheKeySignatureTest(unittest.TestCase):
    """A page's call is the whole of what a cached read is stored under."""

    def test_each_read_takes_the_key_alone(self) -> None:
        for read, _ in _SKILL_READS:
            with self.subTest(read=read.__name__):
                self.assertEqual(
                    tuple(inspect.signature(read).parameters),
                    _KEY_ONLY,
                )


if __name__ == "__main__":
    unittest.main()
