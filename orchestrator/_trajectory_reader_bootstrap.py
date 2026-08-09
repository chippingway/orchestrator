# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Load a fresh trajectory-record facade over the current settings holder."""

from __future__ import annotations

import importlib
import sys
from types import ModuleType


RECORD_MODULE = "orchestrator._trajectory_records"


def load_fresh_records() -> ModuleType:
    """Rebuild the record module over the settings holder installed now."""
    sys.modules.pop(RECORD_MODULE, None)
    return importlib.import_module(RECORD_MODULE)
