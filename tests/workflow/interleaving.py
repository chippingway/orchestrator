# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What happened between two of one tick's own steps, and nobody told it.

The window a fixture cannot otherwise reach. A guard reads the world, the
effect it guards runs some time later, and everything in between -- a remote
read, a diff, a worktree probe -- is time a poll on another thread can change
what that guard answered. A case about such a window has to put its event
INSIDE the window rather than before the tick, which means hanging it on the
step that opens it.

A reading that stops answering is the same shape one step over: the fact a
step established is still true, and asking again is a second chance to get a
different answer. A case about that puts the failure between the two readings.

Here rather than beside either caller because the packages that need these are
different ones, and a second copy would drift from whichever of them it was
not written for.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any


class _RacesTheStep:
    """One thing that happens the instant a step runs, just before it runs.

    Wraps the callable a case patches, so the step still does what it always
    did and the world it looks at is the one the race left. A class rather
    than a closure because a seam this repository patches is a value with a
    name, and one that reads back as a function of its own is the shape every
    other double here takes.
    """

    def __init__(self, wrapped: Callable, raced: Callable) -> None:
        self._wrapped = wrapped
        self._raced = raced

    def __call__(self, *called: Any, **options: Any) -> Any:
        self._raced()
        return self._wrapped(*called, **options)


class _RacesPastTheStep:
    """One thing that happens the instant a step returns, just after it runs.

    The other half of the window `_RacesTheStep` opens, for a case whose event
    has to land after the step did its work rather than before: a reply posted
    once a notice is on the thread and before the write that records how far
    the thread has been read.
    """

    def __init__(self, wrapped: Callable, raced: Callable) -> None:
        self._wrapped = wrapped
        self._raced = raced

    def __call__(self, *called: Any, **options: Any) -> Any:
        answered = self._wrapped(*called, **options)
        self._raced()
        return answered


class _AnswersOnce:
    """A seam that answers truthfully once and refuses every reading after.

    A store that stopped answering between two readings of one fact, which is
    what makes asking twice different from asking once. A case using it is
    pinning that the second reading never happens: the answer a decision was
    taken on is carried to whatever records it, rather than re-derived where a
    transient failure would quietly change what the record says.
    """

    def __init__(self, wrapped: Callable, refused: Any) -> None:
        self._wrapped = wrapped
        self._refused = refused
        self._spent = False

    def __call__(self, *called: Any, **options: Any) -> Any:
        if self._spent:
            return self._refused
        self._spent = True
        return self._wrapped(*called, **options)
