# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Hermetic dashboard reload and dependency lookup helpers."""

from __future__ import annotations

import importlib
import os
import sys
from types import ModuleType
from unittest.mock import patch

from tests.observability.analytics.analytics_reload_helpers import reload_analytics
from tests.import_world_helpers import CONFIG_MODULE, restored_import_world


SKIP_DOTENV_ENV = "ORCHESTRATOR_SKIP_DOTENV"
TOKEN_FILE_ENV = "ORCHESTRATOR_TOKEN_FILE"
MISSING_TOKEN_FILE = "/tmp/agent-orchestrator-token-missing"
DASHBOARD_MODULE = "orchestrator.dashboard"
WIDGETS_MODULE = "orchestrator.dashboard_widgets"
THEME_MODULE = "orchestrator.dashboard_theme"
DASHBOARD_OWNERS = "orchestrator.observability.dashboard"
READ_MODE_ATTRIBUTE = "read_mode"
READ_MODE_OWNER = f"{DASHBOARD_OWNERS}.{READ_MODE_ATTRIBUTE}"
_RELOAD_POP_MODULES = (
    CONFIG_MODULE,
    "orchestrator.dashboard_state",
    "orchestrator.dashboard_kpis",
    "orchestrator.dashboard_html",
    "orchestrator.dashboard_cards",
    "orchestrator.dashboard_kpi_strip",
    "orchestrator.dashboard_skill_adoption",
    "orchestrator.dashboard_skill_matrix",
    "orchestrator.dashboard_reads",
    WIDGETS_MODULE,
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
    """Load the analytics knobs and every dashboard leaf against one
    environment.

    The returned pair is the settings holder the environment landed on and the
    hermetic dashboard facade; `orchestrator.config` is put back so a later
    test that first imports a module binding it still binds the same object
    every earlier importer holds.

    The widget surface is named here rather than left to the facade's own
    import, and named after it. The page's composition reaches each owner
    inside the pass that draws with it, so importing the facade plants none of
    the flat hubs -- and its bootstrap evicts them on the way in, so a hub
    imported before it would be dropped again and a caller reading one back
    off `sys.modules` would find nothing there at all.
    """
    _, analytics = reload_analytics(environment)
    with restored_import_world():
        with patch.dict(os.environ, hermetic_environment(environment), clear=True):
            for module_name in _RELOAD_POP_MODULES:
                sys.modules.pop(module_name, None)
            _rebuild_read_mode_owner()
            dashboard = importlib.import_module(DASHBOARD_MODULE)
            importlib.import_module(WIDGETS_MODULE)
    return analytics, dashboard


def load_dashboard_theme() -> ModuleType:
    """Return the dashboard theme module for color-token assertions."""
    return importlib.import_module(THEME_MODULE)
