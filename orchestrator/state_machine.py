# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Forwarding surface for the typed workflow state.

Every name below is defined by :mod:`orchestrator.workflow.state`; nothing is
rebuilt here, so a caller reaching through this module sees the owner's exact
object. Orchestrator code imports the owner, and this module stays the import
site tests and external operator scripts already reference.
"""
from __future__ import annotations

from orchestrator.workflow import state as _state

ALLOWED_TRANSITIONS = _state.ALLOWED_TRANSITIONS
ControlLabel = _state.ControlLabel
IllegalTransition = _state.IllegalTransition
WorkflowLabel = _state.WorkflowLabel
_DETOUR_TO_RESOLVING = _state._DETOUR_TO_RESOLVING
coerce_workflow_label = _state.coerce_workflow_label
guard_transition = _state.guard_transition
is_allowed_transition = _state.is_allowed_transition
log = _state.log
