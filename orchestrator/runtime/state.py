# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The mutable state one polling run carries.

The signal handler, the watchdog thread, the per-repo tick workers, and the
loop driving them all read and write the same four values, so they travel as
one object the composition point creates and hands out. Nothing here is a
module-level default: a caller that wants a run stopped, drained, or already
signaled builds the state that says so and passes it in.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field

from orchestrator.scheduler import IssueScheduler

# The shell convention for "stopped by signal N". `run.sh` keys on the two
# codes it produces (130 / 143) to skip its restart loop, so the base is part
# of what a signal stop means rather than a detail of one exit path.
SIGNAL_EXIT_BASE = 128


@dataclass
class RuntimeState:
    """What one polling run is stopped, drained, and exited by."""

    running: bool = True
    received_signal: int | None = None
    active_scheduler: IssueScheduler | None = None
    shutdown_complete: threading.Event = field(default_factory=threading.Event)

    def signal_exit_code(self) -> int:
        """Return a shell-style signal exit code, or zero when none arrived."""
        if self.received_signal is None:
            return 0
        return SIGNAL_EXIT_BASE + self.received_signal
