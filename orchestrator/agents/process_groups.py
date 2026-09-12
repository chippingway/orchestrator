# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The process-group operations every spawned child is torn down through.

Agent runs and verify commands both start their child into its own process
group (``start_new_session=True``), so a teardown is never about one pid: the
leader can exit on the first signal while a build grandchild it forked keeps
mutating the worktree. What that costs lives here as four operations -- a
bounded drain that reports a wedged pipe rather than blocking its caller for as
long as the descendant holds the fd open, the ``killpg(_, 0)`` probe that says
whether the group still holds anybody after the leader is gone, the
wait-then-SIGKILL escalation that reads it, and the per-timeout SIGTERM over
that escalation.

They sit apart from the registry that tracks which groups are in flight because
they answer nothing about it: the shutdown sweep spends the escalation over
every registered group under one shared deadline, the agent runner spends the
SIGTERM form on the single group its own timeout just expired on, and the
verify command's teardown reaches the drain without registering anything.
"""
from __future__ import annotations

import os
import signal
import subprocess
from contextlib import suppress


def communicate_bounded(
    proc: subprocess.Popen,
    timeout: float,
) -> tuple[str, str] | None:
    """Communicate within a wall-clock cap, returning ``None`` on timeout."""
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        return None
    return stdout or "", stderr or ""


def process_group_alive(process_group_id: int) -> bool:
    """Probe whether a process group still contains a live member."""
    try:
        os.killpg(process_group_id, 0)
    except ProcessLookupError:
        return False
    return True


def sigkill_unless_group_gone(
    proc: subprocess.Popen,
    timeout: float,
) -> None:
    """Wait for the leader, then SIGKILL any surviving process group."""
    leader_exited = True
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        leader_exited = False
    if leader_exited and not process_group_alive(proc.pid):
        return
    with suppress(ProcessLookupError):
        os.killpg(proc.pid, signal.SIGKILL)


def terminate_process_group(proc: subprocess.Popen) -> None:
    """SIGTERM one process group, then SIGKILL it if anything survives."""
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    sigkill_unless_group_gone(proc, timeout=5)
