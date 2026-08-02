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
    READ_MODE_OWNER,
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


def _unbind_read_mode_owner() -> None:
    """Drop the parent binding the read-mode owner is also resolved by.

    The parallel-read flag is parsed while that owner imports, so it is one of
    the modules a reload has to rebuild. Clearing `sys.modules` alone would not
    do it: the import system also binds a submodule as an attribute of its
    package, and `from <package> import read_mode` answers off that attribute
    without consulting `sys.modules` at all -- so the page would read whatever
    flag some earlier import happened to decide.
    """
    package = sys.modules.get(DASHBOARD_OWNERS)
    if package is not None:
        package.__dict__.pop(READ_MODE_ATTRIBUTE, None)


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
            _unbind_read_mode_owner()
            analytics = importlib.import_module("orchestrator.analytics")
            dashboard = importlib.import_module(DASHBOARD_MODULE)
    return analytics, dashboard


def load_analytics_read() -> ModuleType:
    """Return the analytics read facade bound to the current import world."""
    return importlib.import_module(ANALYTICS_READ_MODULE)


def load_dashboard_theme() -> ModuleType:
    """Return the dashboard theme module for color-token assertions."""
    return importlib.import_module(THEME_MODULE)
