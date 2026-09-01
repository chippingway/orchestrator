# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Composition point for the orchestrator polling loop.

`main` is what the `chipping-orchestrator` console script and the
`python -m orchestrator` launch form both call. It reads the options, settles
logging, creates the state one run carries, and hands that state to each owner
under `orchestrator/runtime/` in turn; the order below is the startup contract
and lives nowhere else.

The signal handler is installed before the first GitHub call, so a stop that
arrives during a slow connect is honoured rather than swallowed, and the
scheduler is published on the state as soon as it exists so the same handler
can close the submit path mid-tick. The exit code is whichever answer came
first: a restart the loop asked for, or the signal that stopped the run.
"""
from __future__ import annotations

from orchestrator.runtime import logs, loop, shutdown, startup
from orchestrator.runtime.state import RuntimeState


def main(argv: list[str] | None = None) -> int:
    """Run the polling loop and return its process exit code."""
    options = startup.parse_options(argv)
    logs.configure_logging(options.log_level)
    state = RuntimeState()
    shutdown.install_signal_handlers(state)
    clients = startup.connect_clients()
    scheduler = startup.create_scheduler()
    state.active_scheduler = scheduler
    with loop.scheduler_drained(state, scheduler):
        restart_exit_code = loop.drive_polling(
            state,
            options,
            clients,
            scheduler,
        )
    if restart_exit_code is not None:
        return restart_exit_code
    return state.signal_exit_code()
