# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The shapes one filter request is made of, and the values it is offered.

A request is spelled two ways because both are historical and a caller picks
either: ``RunFilterOptions`` is the object it may be handed as, and
``RunFilterOptionFields`` the keywords the same call may be driven by, field
for field. ``RunFilters`` is what whichever of them arrived becomes once every
multi-value selection has been narrowed to a set and the free-text needle
folded and stripped, so a run is walked against values that were normalized
once for the whole read rather than once per run.

``FilterOptions`` is the other direction: the distinct values a page may offer,
collected off the runs it already read rather than declared, so a dropdown only
ever holds a value some run actually carries.

The two a caller holds report ``orchestrator.trajectory_reader`` as their
module: that is the import site the filter API is published from, so a repr, a
pickle, and a reader following ``__module__`` all still land where it is
documented.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, TypedDict


ORIGIN_MODULE = "orchestrator.trajectory_reader"


class RunFilterOptionFields(TypedDict, total=False):
    repo: Optional[str]
    backends: Optional[Sequence[str]]
    agent_roles: Optional[Sequence[str]]
    stages: Optional[Sequence[str]]
    issue: Optional[int]
    query: Optional[str]
    exclude_fixtures: bool


@dataclass(frozen=True)
class RunFilters:
    repo: Optional[str]
    backends: Optional[frozenset[str]]
    agent_roles: Optional[frozenset[str]]
    stages: Optional[frozenset[str]]
    issue: Optional[int]
    query: Optional[str]
    exclude_fixtures: bool


@dataclass(frozen=True)
class FilterOptions:
    """Distinct filter values across a set of runs, each sorted."""

    repos: tuple[str, ...] = ()
    backends: tuple[str, ...] = ()
    agent_roles: tuple[str, ...] = ()
    stages: tuple[str, ...] = ()


@dataclass(frozen=True)
class RunFilterOptions:
    """Raw optional constraints accepted by :func:`filter_runs`."""

    repo: Optional[str] = None
    backends: Optional[Sequence[str]] = None
    agent_roles: Optional[Sequence[str]] = None
    stages: Optional[Sequence[str]] = None
    issue: Optional[int] = None
    query: Optional[str] = None
    exclude_fixtures: bool = False


FilterOptions.__module__ = ORIGIN_MODULE
RunFilterOptions.__module__ = ORIGIN_MODULE
