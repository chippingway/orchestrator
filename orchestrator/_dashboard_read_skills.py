# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Dashboard per-skill read wrappers.

Both reads name the query owner rather than the `analytics.read` facade that
forwards the same two objects. Reaching through it would run identical SQL
while making the page depend on a hop kept for callers that predate the owner.
"""
from __future__ import annotations

from orchestrator._dashboard_read_core import _read_filtered
from orchestrator.observability.analytics.query import skill_reads


def _read_skill_trigger_matrix(key: tuple):
    return _read_filtered(skill_reads.get_skill_trigger_matrix, key)


def _read_skill_adoption(key: tuple):
    return _read_filtered(skill_reads.get_skill_adoption, key)
