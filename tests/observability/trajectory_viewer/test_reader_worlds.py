# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Two readers built against two environments, each on its own file.

The owner reads the trajectory knob off the settings holder it is handed, and
the record leaf hands it the analytics package that leaf captured at its own
import. This is what that buys: a reader rebuilt against a patched environment
resolves the file that environment names, and the reader built before it keeps
resolving the one it was built for.
"""
from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from unittest.mock import patch

from tests.import_world_helpers import RECORDING_EVENTS, republish_recording


_LOG_PATH_ATTR = "TRAJECTORY_LOG_PATH"

_READER_MODULE = "orchestrator.trajectory_reader"

_ANALYTICS_MODULE = "orchestrator.analytics"

_CONFIG_MODULE = "orchestrator.config"

_ORCHESTRATOR_PKG = "orchestrator"

_HERMETIC = MappingProxyType({
    "ORCHESTRATOR_SKIP_DOTENV": "1",
    "ORCHESTRATOR_TOKEN_FILE": "/tmp/agent-orchestrator-token-missing",
})


def _reload_reader_world(log_path):
    """Reload analytics + reader against `log_path` and return the fresh pair.

    Pops only the PUBLIC modules a caller would reload -- not the private
    `_trajectory_records` leaf -- so the reload exercises the facade's own
    eviction rather than masking it.
    """
    reload_env = {**_HERMETIC, _LOG_PATH_ATTR: str(log_path)}
    with patch.dict(os.environ, reload_env, clear=True):
        for name in (_READER_MODULE, _ANALYTICS_MODULE, _CONFIG_MODULE):
            sys.modules.pop(name, None)
        # Re-import through `importlib` so a popped submodule is rebuilt
        # rather than resolved from the parent package's stale attribute.
        fresh_analytics = importlib.import_module(_ANALYTICS_MODULE)
        fresh_reader = importlib.import_module(_READER_MODULE)
        return fresh_analytics, fresh_reader


def _snapshot_and_arm_orchestrator_reset(test):
    """Snapshot every `orchestrator*` module + the package namespace, restore after `test`.

    Importing a submodule binds it as an attribute of its parent package, so an
    A/B reload rebinds `orchestrator.analytics` (and `.config` /
    `.trajectory_reader` / `._trajectory_records`) on the persistent
    `orchestrator` package object. Restoring `sys.modules` alone would leave
    `from orchestrator import analytics` (how the reader leaf holds the
    settings it resolves through) pointing at a discarded reload, so the
    package's own namespace is snapshotted and reverted too.
    """
    saved = {
        name: module
        for name, module in sys.modules.items()
        if name.startswith(_ORCHESTRATOR_PKG)
    }
    orchestrator_pkg = sys.modules[_ORCHESTRATOR_PKG]
    test.addCleanup(
        _restore_orchestrator_modules,
        saved,
        orchestrator_pkg,
        dict(orchestrator_pkg.__dict__),
    )


def _restore_orchestrator_modules(saved, orchestrator_pkg, saved_pkg_attrs):
    """Evict the current `orchestrator*` modules and reinstate the snapshot."""
    stale = [name for name in sys.modules if name.startswith(_ORCHESTRATOR_PKG)]
    for name in stale:
        sys.modules.pop(name, None)
    sys.modules.update(saved)
    orchestrator_pkg.__dict__.clear()
    orchestrator_pkg.__dict__.update(saved_pkg_attrs)
    # The recording package's module object is never replaced -- every
    # producer holds the one it imported -- so putting `sys.modules` back is
    # not enough to stop it publishing the recorders this reload built.
    republish_recording(saved.get(RECORDING_EVENTS))


@dataclass(frozen=True)
class _ReaderWorld:
    path: Path
    analytics: object
    reader: object

    @classmethod
    def load(cls, path: Path) -> "_ReaderWorld":
        analytics, reader = _reload_reader_world(path)
        return cls(path, analytics, reader)


class ReloadIsolationTest(unittest.TestCase):
    """A reloaded reader resolves its own world's `TRAJECTORY_LOG_PATH`."""

    def test_each_world_keeps_resolving_its_own_path(self) -> None:
        _snapshot_and_arm_orchestrator_reset(self)
        with tempfile.TemporaryDirectory() as work_dir:
            world_a = _ReaderWorld.load(Path(work_dir) / "a.jsonl")
            world_b = _ReaderWorld.load(Path(work_dir) / "b.jsonl")
            # Each reader's leaf holds its own analytics instance, so world A
            # still resolves world A after world B has been loaded.
            self.assertIsNot(world_a.reader, world_b.reader)
            self.assertIsNot(world_a.analytics, world_b.analytics)
            self.assertEqual(
                (
                    world_a.reader.resolve_log_path(),
                    world_b.reader.resolve_log_path(),
                ),
                (world_a.path, world_b.path),
            )


if __name__ == "__main__":
    unittest.main()
