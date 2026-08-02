# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""How one page load's reads are issued, once the flag has said which way.

A wave is a list of readers, each under the name its result is later read back
by, and this owner is the one place either way of running that wave is spelled:
on the calling thread, or across a bounded pool. Both hand back the same
mapping keyed by the submitted name, so a widget reads its row out of the same
key whichever way the load ran, and neither collects a failure -- the page
answers a failed load with a single banner, so the first read error has to
reach the caller unchanged rather than arrive as one entry among the results.

Submission order is what the sequential branch runs in and what the parallel
branch collects in, so a wave reports against the same reader either way. The
worker cap is the read-mode owner's, because how many reads a load may have in
flight is part of what the fan-out is enabled by rather than a second number
decided here.
"""
from __future__ import annotations

from typing import Any, Callable, Sequence

from orchestrator.observability.dashboard import read_mode


NamedReader = tuple[str, Callable[[], Any]]


def fan_out_reads(
    readers: Sequence[NamedReader],
    *,
    parallel: bool,
    max_workers: int = read_mode.PARALLEL_READS_MAX_WORKERS,
) -> dict[str, Any]:
    """Run one wave of readers and key each result by its reader's name.

    Every reader runs exactly once. The parallel branch submits the wave in
    order and then waits on the futures in that same order, so a reader that
    raises surfaces as the caller's own exception from the same position the
    sequential branch would have stopped at.
    """
    if not parallel:
        return {name: reader() for name, reader in readers}
    # Reached only when an operator turned the fan-out on, so the default
    # install -- and every non-dashboard importer of this package -- never
    # builds a pool or pays for the machinery behind one.
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [(name, pool.submit(reader)) for name, reader in readers]
        return {name: future.result() for name, future in futures}
