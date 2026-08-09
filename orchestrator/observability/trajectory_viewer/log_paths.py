# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Which file this viewer reads, and what an operator gets when there is none.

The trajectory sink is opt-in and default-off, so an unset knob is the ordinary
state of an install rather than a misconfiguration: it answers with the banner
naming the knob, the relaunch that makes it take effect, and the order the two
happen in, instead of the empty table an operator would read as "nothing ran".

The knob is read off a settings holder the caller hands in rather than off the
holder's own name, because *which* one is the caller's own question: a reader
built against one import of it resolves that import's path for as long as it
is held, and patching the knob on the holder a caller captured is the
interception every read of it goes through.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from orchestrator.observability.analytics import config as analytics_config
from orchestrator.observability.trajectory_viewer import constants


def configured_path(settings_holder: Any) -> Optional[Path]:
    """Return the trajectory log path bound on `settings_holder`."""
    return analytics_config.settings_on(settings_holder).trajectory_log_path


def resolve_path(
    settings_holder: Any,
    path: Optional[Path],
) -> Optional[Path]:
    """Resolve one read's file: the caller's explicit path, else the knob.

    A caller pointing the reader at a file of its own is not asking about the
    sink at all, so the fallback policy is settled here once rather than at
    each read.
    """
    if path is None:
        return configured_path(settings_holder)
    return path


def unconfigured_message(settings_holder: Any) -> Optional[str]:
    """Return the opt-in banner when that holder's sink is switched off."""
    if configured_path(settings_holder) is None:
        return constants.UNCONFIGURED_LOG_MESSAGE
    return None
