# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""How one wave of named readers is run, either way the flag can say.

The two branches answer the same question, so the cases below hold both to one
contract: every reader runs once, each result comes back under the name it was
submitted under, and a reader's exception is the caller's -- the page answers a
failed load with a single banner rather than a partial set of widgets.
"""

from __future__ import annotations

import threading
import time
import unittest
from functools import partial
from inspect import signature

from orchestrator.observability.analytics.query.connections import (
    AnalyticsReadError,
)
from orchestrator.observability.dashboard import fanout, read_mode

# Three readers named apart, so a case can say which of them ran and in which
# order rather than only how many did.
_FIRST, _SECOND, _THIRD = ("a", "b", "c")

_WORKERS = 4

# More readers than workers, so the parallel case covers a worker taking a
# second reader once its first one returned.
_WAVE = tuple(f"r{index}" for index in range(_WORKERS * 2))

# Long enough that four sleepers run as one wave rather than as a scheduling
# accident, short enough that the case stays cheap.
_READER_DELAY = 0.08

# The ceiling one wave of `_WORKERS` sleepers has to land under, as a multiple
# of one sleeper. Loose enough not to flake on a busy host, tight enough that a
# branch that ran them one after another -- `_WORKERS` times the delay -- fails
# it.
_ELAPSED_CEILING = 2.5

_READ_FAILED = "connection refused"


def _record_call(name: str, calls: list[str], payload: int) -> int:
    calls.append(name)
    return payload


def _raise_read_error(name: str, calls: list[str]) -> None:
    calls.append(name)
    raise AnalyticsReadError(_READ_FAILED)


def _record_threaded_call(
    name: str,
    calls: list[str],
    threads: set[int],
    lock: threading.Lock,
) -> str:
    with lock:
        calls.append(name)
        threads.add(threading.get_ident())
    return name


def _sleep_then_return(payload: str) -> str:
    time.sleep(_READER_DELAY)
    return payload


class FanOutReadsSequentialTest(unittest.TestCase):
    """The branch a default install issues every page load through."""

    def test_readers_run_once_in_submission_order(self) -> None:
        # Submission order is what lets a log line or an error message name
        # the reader it came from, and each name appearing once is the whole
        # of what "the wave ran" means.
        calls: list[str] = []
        readers = [
            (name, partial(_record_call, name, calls, payload))
            for payload, name in enumerate((_FIRST, _SECOND, _THIRD))
        ]

        read_results = fanout.fan_out_reads(readers, parallel=False)

        self.assertEqual(read_results, {_FIRST: 0, _SECOND: 1, _THIRD: 2})
        self.assertEqual(calls, [_FIRST, _SECOND, _THIRD])

    def test_the_first_failing_reader_stops_it(self) -> None:
        # The caller renders one banner and stops the page, so a wave whose
        # read cannot reach the database must not spend the rest of itself
        # collecting the same failure.
        calls: list[str] = []
        readers = [
            (_FIRST, partial(_record_call, _FIRST, calls, 1)),
            (_SECOND, partial(_raise_read_error, _SECOND, calls)),
            (_THIRD, partial(_record_call, _THIRD, calls, 2)),
        ]

        with self.assertRaisesRegex(AnalyticsReadError, _READ_FAILED):
            fanout.fan_out_reads(readers, parallel=False)

        self.assertEqual(calls, [_FIRST, _SECOND])


class FanOutReadsParallelTest(unittest.TestCase):
    """The branch an operator who set the knob gets instead.

    Each worker opens the analytics connection it reads over, so the fan-out
    owns only the dispatch and the collection: what it has to get right is
    that a reader is submitted once and its result read back under the name
    the caller will look for.
    """

    def test_every_reader_runs_once_off_the_caller(self) -> None:
        calls: list[str] = []
        threads: set[int] = set()
        lock = threading.Lock()
        readers = [
            (name, partial(_record_threaded_call, name, calls, threads, lock))
            for name in _WAVE
        ]

        read_results = fanout.fan_out_reads(
            readers, parallel=True, max_workers=_WORKERS,
        )

        self.assertEqual(read_results, {name: name for name in _WAVE})
        self.assertEqual(sorted(calls), sorted(_WAVE))
        self.assertNotIn(threading.get_ident(), threads)

    def test_the_wave_beats_running_it_one_by_one(self) -> None:
        readers = [
            (name, partial(_sleep_then_return, name))
            for name in _WAVE[:_WORKERS]
        ]

        started_at = time.perf_counter()
        read_results = fanout.fan_out_reads(
            readers, parallel=True, max_workers=_WORKERS,
        )
        elapsed = time.perf_counter() - started_at

        self.assertEqual(len(read_results), _WORKERS)
        self.assertLess(elapsed, _READER_DELAY * _ELAPSED_CEILING)

    def test_a_reader_error_surfaces_from_the_pool(self) -> None:
        # A failure raised on a worker has to reach the caller as its own
        # exception rather than as a future nobody looked at, or the page
        # would render its widgets over a wave that never completed.
        calls: list[str] = []
        readers = [
            (_FIRST, partial(_record_call, _FIRST, calls, 1)),
            (_SECOND, partial(_raise_read_error, _SECOND, calls)),
        ]

        with self.assertRaisesRegex(AnalyticsReadError, _READ_FAILED):
            fanout.fan_out_reads(readers, parallel=True, max_workers=2)

    def test_the_default_cap_is_the_knob_owners(self) -> None:
        # How wide a wave may run when the caller does not say. A literal here
        # would be a second cap to keep in step with the one documented beside
        # the knob that turns the fan-out on.
        default_cap = signature(fanout.fan_out_reads)
        self.assertIs(
            default_cap.parameters["max_workers"].default,
            read_mode.PARALLEL_READS_MAX_WORKERS,
        )


if __name__ == "__main__":
    unittest.main()
