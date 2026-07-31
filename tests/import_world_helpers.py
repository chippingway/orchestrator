# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Keep one `orchestrator.config` object installed across a reload test.

A reload test pops modules so a re-import re-runs against a patched
environment. What it must not leave behind is a rebuilt `orchestrator.config`:
dozens of unrelated modules bind that module object once, at their own import
time, so a swap splits them into two camps -- whoever imported before the swap
holds one object, whoever imports after holds the other. A
`patch.object(config, ...)` then reaches only one camp and the other keeps
answering with the real settings. Which module lands in which camp depends on
when it happened to be first imported, so the symptom is a test that passes
alone and fails in a full run.

The canonical recording package is put back for the same reason and one more:
its module object is never replaced -- every producer imported it under its own
name and holds that one object -- so a reload that leaves it publishing the
recorders it just built would point every later producer call at a package
instance only that reload ever drove. The trajectory append owner is put back
too: the analytics bootstrap rebuilds it for every instance it initializes, and
the copy a reload leaves behind resolves the sink path off the throwaway
instance it captured, so a later importer would write nowhere.

The reloaded modules themselves are still what the test drives; only the
process-wide bindings are put back. Restoring `sys.modules` alone would not do
it: importing `orchestrator.config` also rebinds `config` on the persistent
`orchestrator` package object, so a later `from orchestrator import config`
would resolve the discarded reload straight out of the package namespace.
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import Iterator
from contextlib import contextmanager

CONFIG_MODULE = "orchestrator.config"

RECORDING_PACKAGE = "orchestrator.observability.analytics.recording"

EVENTS_ATTRIBUTE = "events"

RECORDING_EVENTS = f"{RECORDING_PACKAGE}.{EVENTS_ATTRIBUTE}"

TRAJECTORY_PACKAGE = "orchestrator.observability.analytics.trajectories"

API_ATTRIBUTE = "api"

TRAJECTORY_API = f"{TRAJECTORY_PACKAGE}.{API_ATTRIBUTE}"

_PACKAGE = "orchestrator"

_ATTRIBUTE = "config"

_MISSING = object()


def republish_recording(events) -> None:
    """Re-execute the canonical recording package over one `events` owner.

    `events` is the owner module the package should publish from, or None to
    rebuild against a fresh one -- which is what a world that never imported
    the owner is restored to. A no-op when the package itself was never
    imported.
    """
    package = sys.modules.get(RECORDING_PACKAGE)
    if package is None:
        return
    if events is None:
        sys.modules.pop(RECORDING_EVENTS, None)
        package.__dict__.pop(EVENTS_ATTRIBUTE, None)
    else:
        sys.modules[RECORDING_EVENTS] = events
        package.__dict__[EVENTS_ATTRIBUTE] = events
    importlib.reload(package)


def reinstate_trajectory_api(api) -> None:
    """Put one trajectory append owner back under both names it is reached by.

    `api` is the module the world entered with, or None when nothing had
    imported it -- in which case whatever a reload left is dropped so the next
    importer builds its own against the live analytics package. A no-op when
    the package itself was never imported.
    """
    package = sys.modules.get(TRAJECTORY_PACKAGE)
    if package is None:
        return
    if api is None:
        sys.modules.pop(TRAJECTORY_API, None)
        package.__dict__.pop(API_ATTRIBUTE, None)
    else:
        sys.modules[TRAJECTORY_API] = api
        package.__dict__[API_ATTRIBUTE] = api


def _reinstate(saved_module, saved_attribute, saved_owners) -> None:
    """Drop whatever the reload installed and put the entering pair back."""
    package = sys.modules[_PACKAGE]
    sys.modules.pop(CONFIG_MODULE, None)
    package.__dict__.pop(_ATTRIBUTE, None)
    if saved_module is not _MISSING:
        sys.modules[CONFIG_MODULE] = saved_module
    if saved_attribute is not _MISSING:
        package.__dict__[_ATTRIBUTE] = saved_attribute
    republish_recording(saved_owners[0])
    reinstate_trajectory_api(saved_owners[1])


@contextmanager
def restored_import_world() -> Iterator[None]:
    """Reinstate the entering `orchestrator.config` module when the body ends.

    The body is free to pop and re-import it; whatever it installs is what the
    body returns, but the module the rest of the session resolves is the one it
    started with. The recording package is republished over the owner it
    entered with, and the trajectory append owner put back beside it, for the
    same reason.
    """
    saved_module = sys.modules.get(CONFIG_MODULE, _MISSING)
    saved_attribute = sys.modules[_PACKAGE].__dict__.get(_ATTRIBUTE, _MISSING)
    saved_owners = (
        sys.modules.get(RECORDING_EVENTS),
        sys.modules.get(TRAJECTORY_API),
    )
    try:
        yield
    finally:
        _reinstate(saved_module, saved_attribute, saved_owners)
