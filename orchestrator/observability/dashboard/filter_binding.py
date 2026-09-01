# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a cached read's key is read back as when that read is issued.

A page hashes one filter set into a key and stores every cached read under it,
so by the time a read runs its filters exist only as that key's positions. This
owner is the one place those positions are read back as the keyword vocabulary
the read model is bound by, because a key packed by the filter owner and
unpacked somewhere else is how a widget ends up reporting a window nobody asked
for -- the two spellings sit one import apart on purpose.

The sequence filters travel as tuples so the key stays hashable and reach a
read as lists, which keeps the three states the stage multiselect carries
apart: `None` is "no clause", and the empty list is the cleared selection that
must match nothing.
"""
from __future__ import annotations

from typing import Any, Callable, Sequence

from orchestrator.observability.dashboard import scoped_reads


def filter_list(
    filter_values: Sequence[str] | None,
) -> list[str] | None:
    """Read a cached filter tuple back as the read model's list argument."""
    if filter_values is None:
        return None
    return list(filter_values)


def read_filter_kwargs(key: tuple) -> dict[str, Any]:
    """Read one cache key back as the filters a read is bound by."""
    return {
        "start": key[0],
        "end": key[1],
        "repo": key[2],
        "events": filter_list(key[3]),
        "stages": filter_list(key[4]),
        "issue": key[5],
    }


def read_filtered(
    getter: Callable[..., Any],
    key: tuple,
    **extra_filters: Any,
) -> Any:
    """Issue one windowed read under the filters `key` was hashed from.

    A widget that narrows by something the key does not carry -- the display
    offset an activity heatmap buckets by, say -- passes it here rather than
    into the key, because it changes what a row is grouped into and not which
    rows the window holds.
    """
    filters = read_filter_kwargs(key)
    filters.update(extra_filters)
    return scoped_reads.scoped_read(getter, **filters)
