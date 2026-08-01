# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""How a page's reads are issued, and what it says when they cannot be.

The knob a fan-out is enabled by, the truthy spellings it accepts, the worker
cap it runs under, and the text an unconfigured database is refused with. The
helpers that read them still live beside the page, so this owner is where the
knob's name and the message an operator sees are decided rather than where the
fan-out runs -- keeping both here is what stops the environment variable a
`.env` sets and the one the page parses from drifting apart.
"""
from __future__ import annotations


PARALLEL_READS_ENV = "DASHBOARD_PARALLEL_READS"
PARALLEL_READS_MAX_WORKERS = 8
TRUTHY = frozenset(("1", "true", "on", "yes"))
UNCONFIGURED_DB_MESSAGE = (
    "`ANALYTICS_DB_URL` is not configured. Set it in your environment "
    "(see `.env.example.advanced` and `docs/configuration.md`) and "
    "reload the dashboard to view analytics."
)
