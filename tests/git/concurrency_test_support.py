# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Thread scaffolding shared by the git owners' serialization tests."""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock

PROBE_DELAY_SECONDS = 0.02
THREAD_TIMEOUT_SECONDS = 10.0
BARRIER_TIMEOUT_SECONDS = 5.0


def _start_and_join(threads: list[threading.Thread], *, timeout: float) -> None:
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=timeout)


class _ConcurrencyProbe:
    """Count how many callers are inside a lock-protected section at once.

    Each recorded call holds its slot open -- on a delay, or until every
    peer reaches a shared barrier -- so serialized callers cap
    `maximum_in_flight` at 1 while genuinely parallel ones exceed it.
    """

    def __init__(
        self,
        *,
        delay: float = 0,
        barrier: threading.Barrier | None = None,
    ) -> None:
        self.maximum_in_flight = 0
        self.order: list[str] = []
        self._in_flight = 0
        self._delay = delay
        self._barrier = barrier
        self._lock = threading.Lock()

    def record(self, label: str) -> MagicMock:
        with self._lock:
            self._in_flight += 1
            self.maximum_in_flight = max(
                self.maximum_in_flight,
                self._in_flight,
            )
            self.order.append(label)
        try:
            self._hold()
        except BaseException:
            self._leave()
            raise
        else:
            self._leave()
        return MagicMock(returncode=0, stdout="", stderr="")

    def git(self, *args, cwd) -> MagicMock:
        return self.record(f"{args[0]}({threading.get_ident()})")

    def fetch(self, _spec, _branch) -> MagicMock:
        return self.record(f"fetch({threading.get_ident()})")

    def subprocess_run(self, args, **_kwargs) -> MagicMock:
        if "fetch" in args and "--quiet" in args:
            return self.record("fetch")
        return MagicMock(returncode=0, stdout="", stderr="")

    def _hold(self) -> None:
        if self._barrier is not None:
            self._barrier.wait()
        if self._delay:
            time.sleep(self._delay)

    def _leave(self) -> None:
        with self._lock:
            self._in_flight -= 1
