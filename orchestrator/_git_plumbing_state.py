# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Shared immutable values for :mod:`orchestrator.git_plumbing` leaves."""
from __future__ import annotations

import logging

log = logging.getLogger('orchestrator.git_plumbing')

_FETCH = "fetch"

_ASKPASS_MODE = 0o700
