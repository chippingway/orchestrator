# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Hermetic analytics-package reload support for recording tests."""

from __future__ import annotations

import importlib
import os
import sys
from dataclasses import dataclass
from contextlib import ExitStack
from types import ModuleType
from unittest.mock import patch

from tests.import_world_helpers import (
    CONFIG_MODULE,
    RECORDING_EVENTS,
    republish_recording,
)


_MODULE_PREFIX = "orchestrator.analytics"
_CONFIG_MODULE = CONFIG_MODULE
_MISSING = object()

# Where each tree a reload rebuilds is bound. Restoring `sys.modules` alone is
# not enough: the import system also binds a submodule as an attribute of its
# parent, and `from <parent> import <name>` answers off that attribute without
# consulting `sys.modules` at all. Leaving one behind would hand every later
# importer the throwaway copy this reload built.
_PARENT_BINDINGS = (
    ("orchestrator", "analytics"),
    ("orchestrator", "config"),
)


@dataclass(frozen=True)
class _ModuleSnapshot:
    modules: dict[str, ModuleType]
    parent_bindings: dict[tuple[str, str], object]

    @classmethod
    def capture(cls) -> "_ModuleSnapshot":
        """Record the import world a reload is about to rebuild."""
        return cls(
            {
                name: module
                for name, module in sys.modules.items()
                if _reloaded(name)
            },
            {
                binding: _parent_namespace(binding).get(binding[1], _MISSING)
                for binding in _PARENT_BINDINGS
            },
        )

    def restore(self) -> None:
        """Put the recorded world back over whatever the reload left."""
        _clear()
        sys.modules.update(self.modules)
        for binding, member in self.parent_bindings.items():
            _rebind(binding, member)
        republish_recording(self.modules.get(RECORDING_EVENTS))


def _hermetic_env(extra: dict[str, str] | None) -> dict[str, str]:
    environment = {
        "ORCHESTRATOR_SKIP_DOTENV": "1",
        "ORCHESTRATOR_TOKEN_FILE": "/tmp/agent-orchestrator-token-missing",
    }
    if extra:
        environment.update(extra)
    return environment


def _reloaded(module_name: str) -> bool:
    """Whether one import is rebuilt by a reload.

    This mirrors the package bootstrap's own reload inventory rather than
    sweeping a prefix, because over-clearing rebuilds more than the bootstrap
    does. `events` is named exactly, and its recording siblings deliberately
    are not: it is the only one carrying per-instance state -- each instance's
    recorders capture the instance they were imported alongside, which is what
    a reference held across a reload keeps dispatching to -- while clearing
    the rest would have the re-execution mint a second `io` and, with it, a
    second sink lock for the append and the prune to take one each of. The
    package above them is re-executed in place rather than replaced, so it is
    not cleared either.
    """
    return module_name in {_CONFIG_MODULE, RECORDING_EVENTS} or (
        module_name.startswith(_MODULE_PREFIX)
    )


def _parent_namespace(binding: tuple[str, str]) -> dict:
    """The namespace one reloaded tree is bound in.

    A throwaway mapping when the parent is not imported at all: a binding
    nobody can observe is the same no-op as skipping the write.
    """
    parent = sys.modules.get(binding[0])
    return {} if parent is None else parent.__dict__


def _rebind(binding: tuple[str, str], member: object) -> None:
    namespace = _parent_namespace(binding)
    if member is _MISSING:
        namespace.pop(binding[1], None)
    else:
        namespace[binding[1]] = member


def _clear() -> None:
    for module_name in tuple(sys.modules):
        if _reloaded(module_name):
            sys.modules.pop(module_name, None)
    for binding in _PARENT_BINDINGS:
        _rebind(binding, _MISSING)


def reload_analytics(
    environment: dict[str, str] | None = None,
) -> tuple[ModuleType, ModuleType]:
    """Load a fresh analytics world and restore the process import world."""
    importlib.import_module("orchestrator")
    snapshot = _ModuleSnapshot.capture()
    with ExitStack() as cleanup:
        cleanup.callback(snapshot.restore)
        with patch.dict(os.environ, _hermetic_env(environment), clear=True):
            _clear()
            config = importlib.import_module(_CONFIG_MODULE)
            analytics = importlib.import_module(_MODULE_PREFIX)
    return config, analytics
