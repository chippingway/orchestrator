# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Which process on this host may take its artifacts, and which one is live.

Every other coordination in this tree is between threads: the scheduler's caps
and claims, the maintenance barrier over them, the per-target-root git locks
that are process-local by construction. A second orchestrator process on the
same host is outside all of it -- its workers are in its own scheduler, its
claims in its own sets -- and the artifacts are not: one host's checkouts and
one remote's refs are shared by every process pointed at them.

So there is one file, and one rule over it. A polling run holds it SHARED for
its whole life, which says a process that may be running work for any issue is
live here. A maintenance pass holds it EXCLUSIVE for as long as it acts, and it
is the SAME rule whoever runs the pass: the one-shot mode takes the host on the
way in, and a polling run's own recurring pass hands its presence over and
takes it back afterwards. No pass anywhere touches an artifact without holding
this host exclusively, because a hold on one process's scheduler says nothing
about another process's workers -- and the per-candidate gates under it,
fail-closed as they are, are a second line and not a substitute: the quiet
period reads a modification time, and a worker that has not written yet leaves
none.

What a presence MEANS is the reason handing one over has a precondition this
file cannot check. It says work may be running in the process that holds it, so
it may only be given up by a process that has already stopped admitting and
drained -- and it has to be back before that process admits anything again.
Nothing here can see a scheduler, so the caller composing the two owns that
order: `runtime/artifacts.py` takes its own barrier around the handover, and a
future caller that did it the other way round would publish this host with a
worker still live in it.

Which way the waiting runs is the whole of the safety argument. A pass NEVER
waits: refused the host, it defers whole, and what that costs is one interval
of a finished issue's disk. A poller ALWAYS waits: it may not start submitting
while another process is deleting, and there is no length of wait that makes
doing so safe. What keeps that wait finite is not a timeout here -- it is that
a pass bounds its own hold and gives the host back at a candidate boundary, so
the poller waits out one candidate's teardown and no more.

`flock` rather than the presence of a file, because a lock is released when the
process holding it dies however it dies. A host powered off mid-pass comes back
with a stale file and no lock; a marker or a pid file would come back holding
this host's artifacts hostage until an operator noticed.

A lock that is HELD and a lock that does not work are two different answers and
are kept apart throughout. Only the refusal a non-blocking request gets when
somebody else has it means contention; a filesystem with no `flock`, a full
lock table, a descriptor that is not one -- none of those say anything about
another process, and answering them as contention would have a poller waiting
out a holder that does not exist. They resolve to the same claim an unopenable
file does: this host cannot be coordinated on, so a poller polls and a pass
does not act.

The file sits under `WORKTREES_DIR` because that is the resource being spent:
two deployments with checkout roots of their own are independent whatever else
they share, and two processes over one root are not.
"""
from __future__ import annotations

import contextlib
import fcntl
import logging
import time
from collections.abc import Iterator
from pathlib import Path
from typing import TextIO

from orchestrator import config

log = logging.getLogger("orchestrator")

# Named for what it guards rather than for who takes it, and hidden, because it
# is this deployment's own bookkeeping sitting in a directory whose other
# entries are checkouts the artifact scan reads. A dotted name is no issue
# number, so the scan passes over it as it does over any other entry it cannot
# derive.
_LOCK_FILE_NAME = ".artifact-maintenance.lock"

# How often a run waiting for the host asks again, and how often it says so
# while it waits. The retry is short because what it is waiting out is one
# candidate's teardown; the notice is spaced so a long wait is visible in the
# log without filling it.
_PRESENCE_RETRY_SECONDS = 0.5

_PRESENCE_NOTICE_SECONDS = 15.0


def _lock_path() -> Path:
    """Where this host's artifact lock lives, read at the call.

    Off the configuration each time rather than bound at import, so a process
    coordinates over the checkout root it was started with.
    """
    return config.WORKTREES_DIR / _LOCK_FILE_NAME


def _created() -> TextIO:
    """Open the host's lock file, creating its directory if it is not there.

    Appending rather than writing, so nothing is truncated under a holder, and
    the file stays empty on purpose: what it carries is the lock, and a line
    written by one of several shared holders would only describe one of them.
    """
    lock_path = _lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    return lock_path.open("a", encoding="utf-8")


def _opened() -> TextIO | None:
    """The host's lock file, or `None` if this host cannot be coordinated on.

    An unwritable or unreachable checkout root is the whole of that case, and
    what it costs is each caller's to decide: a polling run says so and goes on
    polling, and a maintenance pass that cannot be told whether anything else
    is live does not run at all.
    """
    try:
        return _created()
    except OSError:
        log.warning(
            "could not open the host artifact lock at %s; this process cannot "
            "coordinate with another over these artifacts",
            _lock_path(), exc_info=True,
        )
        return None


def _unusable(error: OSError) -> None:
    """Say that this host's lock is broken rather than held."""
    log.warning(
        "the host artifact lock at %s could not be worked with (%s); this "
        "process cannot coordinate with another over these artifacts",
        _lock_path(), error,
    )


def _taken(lock_file: TextIO, flags: int) -> bool:
    """Whether the lock could be taken right now, without waiting on it.

    `False` is the lock being HELD and nothing else. `BlockingIOError` is
    exactly what a non-blocking request that would have waited raises, so it is
    the one refusal that means another process has this host.

    Every other `OSError` is raised rather than reported as contention. A
    filesystem that does not implement `flock`, a lock table with no room, a
    descriptor that is not one: none of them are a holder, so waiting for one
    to let go would be a wait nothing could ever end, and a pass told they were
    contention would defer forever on a host nobody is on.
    """
    try:
        fcntl.flock(lock_file, flags | fcntl.LOCK_NB)
    except BlockingIOError:
        return False
    return True


def _waited(lock_file: TextIO, flags: int) -> None:
    """Take the lock, however long the pass holding this host takes.

    Unbounded on purpose, and the one place in this file that waits at all. The
    caller is a process about to submit work on a host something else may be
    deleting from, so there is no answer for it other than the lock: giving up
    and going on is what would let a tick and a teardown overlap, and giving up
    and refusing to poll would be a crash loop under a supervisor that restarts
    on exit.

    What makes it finite is on the other side. A pass bounds its own hold and
    releases the host at a candidate boundary, so the wait is one candidate's
    teardown -- and a pass whose process dies holds nothing at all, since the
    kernel drops the lock with the file description.

    Retried rather than blocked in the kernel so the wait stays interruptible:
    a run stalled here still takes a second signal, which is what an operator
    reaches for when they have decided not to wait.

    Only a lock somebody HOLDS is waited for. A lock that does not work raises
    out of here on the first attempt, because there is nothing to wait for and
    the caller has a different answer to give for it.
    """
    if _taken(lock_file, flags):
        return
    waited_since = time.monotonic()
    announced = waited_since
    log.info("waiting for the process holding this host's artifacts")
    while not _taken(lock_file, flags):
        time.sleep(_PRESENCE_RETRY_SECONDS)
        if time.monotonic() - announced >= _PRESENCE_NOTICE_SECONDS:
            announced = time.monotonic()
            log.warning(
                "still waiting for this host's artifacts after %.0fs",
                announced - waited_since,
            )
    log.info(
        "took this host's artifacts after %.0fs",
        time.monotonic() - waited_since,
    )


def _handed_over(lock_file: TextIO) -> bool:
    """Give a presence up and try to take the host in its place.

    The two halves are one step because nothing may sit between them: what the
    caller is doing is trading a claim that says work may be running here for
    one that says nothing is.
    """
    fcntl.flock(lock_file, fcntl.LOCK_UN)
    return _taken(lock_file, fcntl.LOCK_EX)


def _restored(lock_file: TextIO, sole: bool) -> None:
    """Give the host back if it was taken, and take the presence again."""
    if sole:
        fcntl.flock(lock_file, fcntl.LOCK_UN)
    _waited(lock_file, fcntl.LOCK_SH)


class UnclaimedHost:
    """A host this process holds no claim on, and may not reclaim on.

    What an unopenable lock file leaves a run with. A polling run carries it
    and polls -- refusing to poll because a tidying job cannot be coordinated
    would trade the workflow for the disk -- and a pass carries it and does
    nothing, because every artifact it would take belongs to a host it cannot
    be told about.
    """

    taken = False

    @contextlib.contextmanager
    def exclusive(self) -> Iterator[bool]:
        """No pass may act on a host this process could not claim."""
        yield False


class ExclusiveHost:
    """The host already held exclusively, by a run that does nothing else.

    The maintenance-only mode's standing: it took the host before it connected
    anything, so its pass has nothing left to arrange and simply acts.
    """

    taken = True

    @contextlib.contextmanager
    def exclusive(self) -> Iterator[bool]:
        """Already the sole claimant, for the whole of this run."""
        yield True


class SharedHost:
    """A polling run's own presence, and the handover its pass needs.

    A presence claim is shared, so it does not exclude another poller -- two
    pollers bound their own work with their own schedulers. It does not
    exclude this run's OWN pass either, which is the thing it has to: so the
    pass hands the presence back, takes the host exclusively, and restores the
    presence when it is done.

    Only from a process that has gone quiet, and only for as long as it stays
    that way. Giving a presence up says nothing is running here, so a caller
    that had not closed its own admission and drained its own workers first
    would be saying something untrue -- and whatever took the host on the
    strength of it would be reading its own empty scheduler as proof about
    this one. The caller keeps its barrier around this whole context for the
    same reason: the presence has to be back before it admits work again.

    The window between giving the presence up and taking the host is real: a
    one-shot pass or another poller can be granted the lock inside it. Both
    answers are safe, because the process is quiet either way. Refused the
    host, this pass defers -- and takes its presence back, waiting out whatever
    was granted instead, which is exactly the wait a poller owes a live
    teardown.

    A lock that stops working half way through is the one case with no good
    answer, so it takes the least bad one: the pass does not act, and the
    presence is asked for again anyway. What that leaves is a run polling
    without a claim on a host nothing can be coordinated on -- which is where a
    run whose lock never worked starts, and it is said out loud both times.
    """

    def __init__(self, lock_file: TextIO) -> None:
        self._lock_file = lock_file

    taken = True

    @contextlib.contextmanager
    def exclusive(self) -> Iterator[bool]:
        """Hand this run's presence over to its own pass, and take it back.

        Called from inside the caller's own barrier, which is what makes the
        gap between the two locks a gap in which this process has nothing
        running.
        """
        try:
            sole = _handed_over(self._lock_file)
        except OSError as error:
            _unusable(error)
            sole = False
        try:
            yield sole
        finally:
            self._restored(sole)

    def _restored(self, sole: bool) -> None:
        """Give the host back, and take this run's presence again."""
        try:
            _restored(self._lock_file, sole)
        except OSError as error:
            _unusable(error)


# What a run holds on this host, which is what decides whether its pass may
# act and what it has to do first. Three answers and no more: the host, a
# presence on it, or nothing.
HostClaim = UnclaimedHost | ExclusiveHost | SharedHost


@contextlib.contextmanager
def polling_presence() -> Iterator[HostClaim]:
    """Say that a live polling process owns this host, for the whole run.

    Waited for rather than attempted: a run starting while a pass holds the
    host has nothing to lose by waiting -- it has submitted nothing yet -- and
    everything to lose by going ahead, since its first tick would create
    checkouts in a directory being torn down.
    """
    lock_file = _opened()
    if lock_file is None:
        yield UnclaimedHost()
        return
    with lock_file:
        try:
            _waited(lock_file, fcntl.LOCK_SH)
        except OSError as error:
            _unusable(error)
            yield UnclaimedHost()
            return
        try:
            yield SharedHost(lock_file)
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


@contextlib.contextmanager
def artifact_exclusivity() -> Iterator[HostClaim]:
    """Take this host's artifacts for one run, or say somebody else has them.

    Not waited for. A refusal means a process that may be running work for an
    issue is live here, and no length of waiting makes acting safe -- a polling
    run holds its presence for as long as it runs. So the run defers whole,
    which costs one interval of a finished issue's disk.
    """
    lock_file = _opened()
    if lock_file is None:
        yield UnclaimedHost()
        return
    with lock_file:
        try:
            sole = _taken(lock_file, fcntl.LOCK_EX)
        except OSError as error:
            _unusable(error)
            yield UnclaimedHost()
            return
        if not sole:
            log.info(
                "another orchestrator process holds this host's artifacts; "
                "deferring the whole maintenance pass",
            )
            yield UnclaimedHost()
            return
        try:
            yield ExclusiveHost()
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
