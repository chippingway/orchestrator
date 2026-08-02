# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical read-mode import site, and the fan-out still decided here.

The knob parse, the flag one page load is issued under, and the refusal an
unconfigured database is answered with are the read-mode owner's own objects,
so a caller that names this module compares against what the owner decided.
The fan-out itself stays beside the page: it is how a load's reads are issued
once the flag has said which way, which is the page's own arrangement rather
than something the state owners settle.
"""
from __future__ import annotations

from typing import Any, Callable, Sequence

from orchestrator.observability.dashboard import read_mode as constants


NamedReader = tuple[str, Callable[[], Any]]

parse_parallel_reads_flag = constants.parse_parallel_reads_flag
db_unconfigured_message = constants.db_unconfigured_message
dashboard_parallel_reads_enabled = constants.dashboard_parallel_reads_enabled


def fan_out_reads(
    readers: Sequence[NamedReader],
    *,
    parallel: bool,
    max_workers: int = constants.PARALLEL_READS_MAX_WORKERS,
) -> dict[str, Any]:
    if not parallel:
        return {name: reader() for name, reader in readers}
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [(name, pool.submit(reader)) for name, reader in readers]
        return {name: future.result() for name, future in futures}
