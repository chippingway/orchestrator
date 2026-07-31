# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the session evidence, answered by its owner.

The seven names are the owner's own, so which row belongs to which logical
session, what a session is allowed to have been offered, and how far back the
history scan reaches for that answer are all decided there.
"""

from __future__ import annotations

from orchestrator.observability.analytics.query.skill_sessions import (
    SessionEvidence as _SessionEvidence,
    SkillWindowRun as _SkillWindowRun,
    skill_history_rows as _skill_history_rows,
    skill_session_evidence as _skill_session_evidence,
    skill_session_key as _skill_session_key,
    skill_window_run as _skill_window_run,
    skill_window_rows as _skill_window_rows,
)

_COMPATIBILITY_EXPORTS = (
    _SessionEvidence,
    _SkillWindowRun,
    _skill_history_rows,
    _skill_session_evidence,
    _skill_session_key,
    _skill_window_run,
    _skill_window_rows,
)
