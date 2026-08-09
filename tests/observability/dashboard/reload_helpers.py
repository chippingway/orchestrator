# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The environment a page is loaded under, and the re-parse of the knob in it."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from importlib import import_module, reload
from types import ModuleType
from unittest.mock import patch

SKIP_DOTENV_ENV = "ORCHESTRATOR_SKIP_DOTENV"
TOKEN_FILE_ENV = "ORCHESTRATOR_TOKEN_FILE"
MISSING_TOKEN_FILE = "/tmp/agent-orchestrator-token-missing"
READ_MODE_OWNER = "orchestrator.observability.dashboard.read_mode"


def hermetic_environment(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Return the import-time environment a page is loaded under here.

    A test that imports a launch path must not pick up the operator's own
    `.env` or personal access token: what is under test is what the import
    costs, and either one would decide it from outside the repository.
    """
    environment = {
        SKIP_DOTENV_ENV: "1",
        TOKEN_FILE_ENV: MISSING_TOKEN_FILE,
    }
    if extra:
        environment.update(extra)
    return environment


@contextmanager
def read_mode_reloaded_under(
    environment: dict[str, str],
) -> Iterator[ModuleType]:
    """Re-parse the read-mode knob against `environment`, then put it back.

    The flag is bound while that owner imports, so an environment case is a
    re-import rather than a patched attribute -- and it has to be an *in-place*
    one. Popping `sys.modules` and importing again would build a second module
    object, and the first does not go away: the sibling owners that name this
    one -- the page controls that stage a load under the flag, the fan-out that
    reads the worker cap beside it -- bound it once, at their own import, and
    are not themselves rebuilt. A load would then be issued the way the world
    before it asked while the owner reported the new answer, which is the one
    thing this helper exists to prevent. Reloading keeps the single object and
    rebinds its globals, so every holder reads the knob this environment set.
    """
    owner = import_module(READ_MODE_OWNER)
    try:
        with patch.dict(os.environ, environment, clear=True):
            yield reload(owner)
    finally:
        reload(owner)
