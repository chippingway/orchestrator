# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The three panel reads a page's skill sections are drawn from.

Each one is a window already decided: the page hashed its filters into a cache
key, and what is left to say is which read that key is spent on. So the whole
of an adapter here is a query owner's read named beside the binding that issues
it, and everything under that -- the socket it runs on, the filters the key is
read back as, and the empty answer an unconfigured database yields -- is
decided by the owners it passes through rather than restated per panel.

The three sit under one owner because they are answered by one family. A skill
name, the set a repository offered, and the count one run loaded are all
recorded inside an `agent_exit` row's `extras`, which the day-bucketed rollup
does not carry, so `skill_reads.py` scans the events table for all three.
Naming that owner rather than the `analytics.read` facade forwarding the same
objects is what keeps these panels off a hop kept for callers that predate it.

None of the three carries a filter of its own: what a page narrows a skill
panel by is the window and the selections every other read shares, so the key
is the whole of each signature.
"""
from __future__ import annotations

from orchestrator.observability.analytics.query import skill_reads
from orchestrator.observability.dashboard import filter_binding


def read_skill_trigger_rates(key: tuple):
    """Read skill-trigger rates grouped by agent role and backend."""
    return filter_binding.read_filtered(
        skill_reads.get_skill_trigger_rates,
        key,
    )


def read_skill_trigger_matrix(key: tuple):
    """Read per-skill trigger cells for each repository cohort."""
    return filter_binding.read_filtered(
        skill_reads.get_skill_trigger_matrix,
        key,
    )


def read_skill_adoption(key: tuple):
    """Read per-session skill adoption cells for each repository cohort."""
    return filter_binding.read_filtered(skill_reads.get_skill_adoption, key)
