# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the page setup, and where its world is bound.

The two entry points that read the trajectory knob are this module's own, for
the reason the record leaf holds the same shape: the owner answers on the
settings holder it is handed, and this is the site that hands it one -- the
analytics package captured at this module's own import, so a page composed
against a reloaded environment resolves that environment's file, and a patch on
the package a caller holds reaches every read the page makes. The chrome and
the two empty-state messages need no world at all, so they are the owner's own
objects under the spelling this module published them as.
"""

from __future__ import annotations

from typing import Any

from orchestrator import analytics
from orchestrator.observability.trajectory_viewer import page_models, page_setup


NO_TRAJECTORIES_MESSAGE = page_setup.NO_TRAJECTORIES_MESSAGE
EMPTY_FILTER_MESSAGE = page_setup.EMPTY_FILTER_MESSAGE
_configure_page = page_setup.configure_page


def _stop_if_unconfigured(st: Any) -> None:
    """Halt the page where this world's trajectory sink is switched off."""
    page_setup.stop_if_unconfigured(st, analytics)


def _load_trajectory_page() -> page_models._TrajectoryPage:
    """Read this world's trajectory file into one page."""
    return page_setup.load_trajectory_page(analytics)
