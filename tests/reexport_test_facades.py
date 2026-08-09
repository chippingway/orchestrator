# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Facade and manifest inventories used by compatibility tests."""
from __future__ import annotations

import importlib

from orchestrator import _dashboard_export_manifest


DASHBOARD_FACADE = importlib.import_module("orchestrator.dashboard")

FACADES = (DASHBOARD_FACADE,)
STUBBED_FACADES = (DASHBOARD_FACADE,)
STATIC_FACADES = ()
PURE_STATIC_HUBS = ()
LAZY_FACADES = ((DASHBOARD_FACADE, _dashboard_export_manifest),)
