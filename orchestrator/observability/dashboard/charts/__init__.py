# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Figure builders for the analytics dashboard.

Destination for the Plotly figures the page's panels are drawn as, one owner
per chart family. ``primitives`` is the one every family reaches: the
placeholder a window with no rows is answered with, the money, monospace, and
two-line-tick labels a bar is annotated by, and the height and legend a
horizontal-bar panel is laid out with. ``cost_layout`` is shared the same way
by a narrower set: the frame the three horizontal cost families are drawn in --
the gutter, the ``USD`` axis, and the request one series of bars is described
by. The families that have arrived above the two sit beside each other:
``cost_horizontal``, the generic spend ranking, which is what the
per-repository adapter draws; ``cost_stage``, the per-stage split of that spend
into what the cache paid for and what it did not, which is also where the
shading a cache half is tinted with lives; ``heatmap``, the 7x24
weekday-by-hour grid a window's token volume is read off, with the cells,
labels, and squared-off layout it is built from; and ``throughput``, the
per-day strip a window's resolved issues are counted on, with the calendar its
quiet days are filled in from.

``cost_stage`` names ``cost_horizontal`` for one value, the height a cost panel
with nothing to draw comes to, so an empty split and an empty ranking are the
same size card. That is the only edge between two families here.

The usage family arrives as five owners rather than one, split by what a value
answers for: ``usage_bands`` for the four bands a day is counted into and the
roll-up of the series into one bucket per day, ``usage_series`` above it for
the day span a figure is drawn along, the shapes that span travels in, and the
height each stack over it reaches, then ``usage_axis`` for the maxima those
heights are rounded up to and the layout the token and cost scales are
assembled in, ``usage_traces`` for the window a figure is shaped from and the
bands and cost line stacked over it, and ``usage`` over all of them for the
hero figure they are assembled into.

The shared owners sit under the families rather than beside them so the
dependency runs one way -- a family names them, and they name no family --
which is what keeps a direct import of any single chart module cycle-free.

Callers import the owner they need, so this initializer binds nothing. Plotly
lives in the optional ``dashboard`` dependency group, so an owner here imports
it inside the function that builds a figure rather than at module scope:
importing anything under ``observability`` must keep working in the default
install, which does not carry it.
"""
