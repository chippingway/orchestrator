# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Shared immutable values for :mod:`orchestrator.workflow_messages` leaves."""
from __future__ import annotations

import re

_SECTION_SEP = "\n\n"

_MANIFEST_RE = re.compile(
    r"```orchestrator-manifest\s*\n(.*?)\n```",
    re.DOTALL,
)

_MAX_CHILDREN = 10
