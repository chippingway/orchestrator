# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What another worker did while this tick was between two of its own steps.

The window a fixture cannot otherwise reach. A guard reads the world, the
effect it guards runs some time later, and everything in between -- a remote
read, a diff, a worktree probe -- is time a poll on another thread can change
what that guard answered. A case about such a window has to put its event
INSIDE the window rather than before the tick, which means hanging it on the
step that opens it.

Here rather than beside either caller because the packages that need it are
different ones, and a second copy would drift from whichever of the two it was
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
