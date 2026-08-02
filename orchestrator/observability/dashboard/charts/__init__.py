# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Figure builders for the analytics dashboard.

Destination for the Plotly figures the page's panels are drawn as, one owner
per chart family. ``primitives`` is the one every family reaches: the
placeholder a window with no rows is answered with, the money, monospace, and
two-line-tick labels a bar is annotated by, and the height and legend a
horizontal-bar panel is laid out with. It sits under the families rather than
beside them so the dependency runs one way -- a family names this owner, and
this owner names none of them -- which is what keeps a direct import of any
single chart module cycle-free. ``heatmap`` is the first family to arrive
above it: the 7x24 weekday-by-hour grid a window's token volume is read off,
and the cells, labels, and squared-off layout it is built from.

Callers import the owner they need, so this initializer binds nothing. Plotly
lives in the optional ``dashboard`` dependency group, so an owner here imports
it inside the function that builds a figure rather than at module scope:
importing anything under ``observability`` must keep working in the default
install, which does not carry it.
"""
