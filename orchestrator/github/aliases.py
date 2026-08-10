# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Descriptor that binds a module function unchanged onto a client mixin.

Three owners in this package publish a stateless helper both as a module
function and as an attribute of the composed `GitHubClient`. Assigning the
function straight into a mixin body would turn it into an instance method and
feed the client itself as the first argument, so the read has to go through a
descriptor that hands the function back untouched -- the same object whether a
caller reaches it off the module, the class, or an instance.
"""
from __future__ import annotations

from typing import Any, Callable


class StaticMethodAlias:
    """Return one module function unchanged from class or instance access."""

    def __init__(self, function: Callable[..., Any]) -> None:
        self._function = function

    def __get__(
        self,
        instance: object,
        owner: type | None = None,
    ) -> Callable[..., Any]:
        return self._function
