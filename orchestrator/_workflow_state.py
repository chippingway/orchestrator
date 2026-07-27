# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Shared immutable values for :mod:`orchestrator.workflow` leaves."""
from __future__ import annotations

import logging

log = logging.getLogger('orchestrator.workflow')

_PROCESSING_FAILED_LOG = "repo=%s issue=#%s processing failed"

_STATE_ATTR = "state"

_ISSUE_STATE_OPEN = "open"

_ISSUE_STATE_CLOSED = "closed"
