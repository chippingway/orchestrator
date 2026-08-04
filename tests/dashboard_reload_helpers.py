# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Hermetic dashboard reload and dependency lookup helpers."""

from __future__ import annotations

import importlib
import os
import sys
from types import ModuleType
from unittest.mock import patch

from tests.import_world_helpers import CONFIG_MODULE, restored_import_world


SKIP_DOTENV_ENV = "ORCHESTRATOR_SKIP_DOTENV"
TOKEN_FILE_ENV = "ORCHESTRATOR_TOKEN_FILE"
MISSING_TOKEN_FILE = "/tmp/agent-orchestrator-token-missing"
ANALYTICS_READ_MODULE = "orchestrator.analytics.read"
DASHBOARD_MODULE = "orchestrator.dashboard"
THEME_MODULE = "orchestrator.dashboard_theme"
DASHBOARD_OWNERS = "orchestrator.observability.dashboard"
READ_MODE_ATTRIBUTE = "read_mode"
READ_MODE_OWNER = f"{DASHBOARD_OWNERS}.{READ_MODE_ATTRIBUTE}"
_RELOAD_POP_MODULES = (
    CONFIG_MODULE,
    ANALYTICS_READ_MODULE,
    "orchestrator.analytics",
    "orchestrator.dashboard_state",
    "orchestrator.dashboard_kpis",
    "orchestrator.dashboard_html",
    "orchestrator.dashboard_cards",
    "orchestrator.dashboard_kpi_strip",
    "orchestrator.dashboard_skill_adoption",
    "orchestrator.dashboard_skill_matrix",
    "orchestrator.dashboard_reads",
    "orchestrator.dashboard_widgets",
    DASHBOARD_MODULE,
)


def hermetic_environment(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Return the import-time environment shared by dashboard tests."""
    environment = {
        SKIP_DOTENV_ENV: "1",
        TOKEN_FILE_ENV: MISSING_TOKEN_FILE,
    }
    if extra:
        environment.update(extra)
    return environment


def _rebuild_read_mode_owner() -> None:
    """Re-parse the read-mode owner's knob against the environment under patch.

    The parallel-read flag is bound while that owner imports, so the reload has
    to be what re-runs that import, and it has to re-run it *in place*. Popping
    `sys.modules` and importing again would build a second module object, and
    the first one does not go away: the sibling owners that name this one --
    the page controls that stage a load under the flag, the fan-out that reads
    the worker cap beside it -- bound it once, at their own import, and are not
    themselves rebuilt. A page would then report the reloaded world's flag
    through the facade while issuing its reads the way the world before it
    asked, which is the one thing this helper exists to prevent.

    Reloading keeps that single object and rebinds its globals, so every holder
    -- the flat sites the facade resolves through, and the owners that never
    left `sys.modules` -- reads the knob this environment set.
    """
    importlib.reload(importlib.import_module(READ_MODE_OWNER))


def reload_dashboard(
    environment: dict[str, str] | None = None,
) -> tuple[ModuleType, ModuleType]:
    """Load analytics and every dashboard leaf against one environment.

    The returned pair is the hermetic reload; `orchestrator.config` is put back
    so a later test that first imports a module binding it still binds the same
    object every earlier importer holds.
    """
    with restored_import_world():
        with patch.dict(os.environ, hermetic_environment(environment), clear=True):
            for module_name in _RELOAD_POP_MODULES:
                sys.modules.pop(module_name, None)
            _rebuild_read_mode_owner()
            analytics = importlib.import_module("orchestrator.analytics")
            dashboard = importlib.import_module(DASHBOARD_MODULE)
    return analytics, dashboard


def load_analytics_read() -> ModuleType:
    """Return the analytics read facade bound to the current import world."""
    return importlib.import_module(ANALYTICS_READ_MODULE)


def load_dashboard_theme() -> ModuleType:
    """Return the dashboard theme module for color-token assertions."""
    return importlib.import_module(THEME_MODULE)
