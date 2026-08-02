# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The extent and filter vocabulary a page opens before any window exists.

Neither read is narrowed by anything a run of the page carries: the recorded
span the presets are clamped to and the repo, event, and stage values the
filter bar offers move only as the sync ingests new events. So both are cached
under an empty key -- taking no argument is what makes the key empty, and is
why the connection is checked out inside the read rather than passed to it --
and under a TTL measured against that ingest cadence rather than the rerun
cadence. Streamlit reruns the whole script on every widget interaction, and a
per-filter TTL would put the topbar and the sidebar back on Postgres for each.

This pair is also the page's first read, which is what makes it the place a
failed one is answered rather than reported: a run that cannot name its own
window has nothing to draw, so the banner names the knob to check and the
script stops here instead of leaving every widget below to fail on its own.
"""
from __future__ import annotations

from typing import Any

from orchestrator.observability.analytics.query import connections, raw_reads
from orchestrator.observability.dashboard import scoped_reads


STATIC_METADATA_TTL_SECONDS = 300


def read_data_extent():
    """Read the recorded span a window preset is anchored and clamped to."""
    return scoped_reads.scoped_read(raw_reads.get_data_extent)


def read_filter_options():
    """Read the repo, event, and stage values the filter bar offers."""
    return scoped_reads.scoped_read(raw_reads.get_filter_options)


def read_static_metadata(*, st: Any):
    """Read the extent and the filter options through cached wrappers."""
    cached_extent = st.cache_data(
        show_spinner=False,
        ttl=STATIC_METADATA_TTL_SECONDS,
    )(read_data_extent)
    cached_options = st.cache_data(
        show_spinner=False,
        ttl=STATIC_METADATA_TTL_SECONDS,
    )(read_filter_options)
    try:
        return cached_extent(), cached_options()
    except connections.AnalyticsReadError as error:
        st.error(
            "Could not load analytics filter options: "
            f"{error}. Verify `ANALYTICS_DB_URL` and that the Postgres "
            "service is reachable, then reload."
        )
        st.stop()
