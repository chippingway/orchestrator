# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""How a page's reads are issued, and what it says when they cannot be.

The knob a fan-out is enabled by, the truthy spellings it accepts, the parse
that reads it, the flag one page load is issued under, the worker cap it runs
under, and the text an unconfigured database is refused with. Naming the knob
beside the parse is what stops the environment variable a `.env` sets and the
one a page reads from drifting apart. Running a wave of readers either way is
the `fanout` sibling's, which reads the cap back from here: what is decided
here is what the reads are issued under rather than how they are issued.

The two answers are read at opposite times on purpose. The flag is parsed once,
at this module's import, because an operator turns the fan-out on by restarting
the Streamlit process rather than mid-session, and a page that re-parsed per
render could issue one load's reads two ways. The database URL is read through
the analytics configuration owner inside the call, off whichever settings
holder the name resolves to, so a page answers for the target that holder
carries now rather than the one this module happened to be imported alongside.
"""
from __future__ import annotations

import os

from orchestrator.observability.analytics import config as analytics_config


PARALLEL_READS_ENV = "DASHBOARD_PARALLEL_READS"
PARALLEL_READS_MAX_WORKERS = 8
TRUTHY = frozenset(("1", "true", "on", "yes"))
UNCONFIGURED_DB_MESSAGE = (
    "`ANALYTICS_DB_URL` is not configured. Set it in your environment "
    "(see `.env.example.advanced` and `docs/configuration.md`) and "
    "reload the dashboard to view analytics."
)


def parse_parallel_reads_flag() -> bool:
    """Read the fan-out knob out of the environment.

    Default off, so an install that never named the knob keeps issuing its
    reads sequentially. The truthy spellings are the vocabulary the rest of
    the codebase's boolean knobs use, and surrounding whitespace is stripped
    because the value is as often pasted out of a playbook as typed.
    """
    raw_flag = os.environ.get(PARALLEL_READS_ENV, "").strip().lower()
    return raw_flag in TRUTHY


DASHBOARD_PARALLEL_READS = parse_parallel_reads_flag()


def dashboard_parallel_reads_enabled() -> bool:
    """Whether this process's page loads issue their reads in parallel."""
    return DASHBOARD_PARALLEL_READS


def db_unconfigured_message() -> str | None:
    """Refuse a read when no analytics database is configured, else `None`.

    What counts as unconfigured -- an unset knob, an empty value, or a disable
    sentinel -- is the analytics configuration owner's decision, so this reads
    back the URL that owner resolved rather than the environment behind it.
    """
    if analytics_config.live_settings().db_url:
        return None
    return UNCONFIGURED_DB_MESSAGE
