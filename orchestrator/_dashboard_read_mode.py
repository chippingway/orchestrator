# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical read-mode import site.

The knob parse, the flag one page load is issued under, and the refusal an
unconfigured database is answered with are the read-mode owner's own objects;
how a load's reads are then issued is the fan-out owner's. A caller that names
this module reaches what those two decided rather than a copy of either, so a
page and the owners cannot answer differently.
"""
from __future__ import annotations

from orchestrator.observability.dashboard import fanout, read_mode


NamedReader = fanout.NamedReader
fan_out_reads = fanout.fan_out_reads
parse_parallel_reads_flag = read_mode.parse_parallel_reads_flag
db_unconfigured_message = read_mode.db_unconfigured_message
dashboard_parallel_reads_enabled = read_mode.dashboard_parallel_reads_enabled
