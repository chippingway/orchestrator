# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Analytics dashboard owners.

Destination for the Streamlit page rendered over the operator's Postgres
target: the filter state a run of it carries, the read plans it issues, the
KPI, chart, table, and drilldown components, and the theme tokens they share.
The state a run carries is the first to arrive -- ``windows`` for the date
span and the presets that name one, ``filters`` for the offset, issue, stage,
and cache key it is narrowed and displayed by, and ``read_mode`` for the knob
its reads are issued under and the message an unconfigured database is refused
with. ``read_plan`` is what that state is spent on: the two waves a load is
staged into, the cached task each entry is bound as, and the pair of keys --
this window and the one before it -- they are issued under. ``fanout`` runs
one of those waves the way the knob said, on the calling thread or across a
pool capped at the count beside it, and ``dispatch`` drives both of them in
turn: one spinner over the pair, the chrome rendered between them, a banner and
a stop when a read cannot reach the database, and one timing line when the load
comes back. Each
of those readers goes through ``scoped_reads`` for the connection it runs on,
``filter_binding`` for the filters its cache key is read back as, and --
before any of them, because it is what a window can be picked at all from --
``static_metadata`` for the extent and filter vocabulary a page opens on. The
readers themselves arrive with the panels they are drawn for: ``rollups`` for
the seven a headline or lifecycle section is built from, ``breakdowns`` for
the six a comparison section is, and ``skills`` for the three a skill section
is. Above all of them, ``insights`` holds the two observations a window is
worth interrupting a page for and the ratio each is raised at, and ``kpis``
the four numbers that window is summarized by beneath them. ``kpi_series`` and
``kpi_strip`` are how those numbers reach the page: the per-day spend, token,
and resolved lines a sparkline is drawn from, and the four display entries a
window's own aggregate, the one before it, and three of its first-wave reads
are assembled into. ``card_html`` is the markup the banners and the run-health
tiles among those numbers reach the browser as, together with the header every
panel below them is titled by and the hidden mark ``css`` selects a card's
container by, and ``tables`` is the markup beside it: the compact table the
four hand-rolled panels are listed in, with the stylesheet each scopes to its
own class, the header and body they are assembled from, and the bar width,
short repository name, missing count, and unpriced amount a cell reports.
What those reads
are then drawn as arrives under ``charts``, where ``primitives`` holds what
every figure family is built out of -- the placeholder a window holding no
rows is answered with, the labels a bar is annotated by, and the height and
legend a horizontal-bar panel is laid out with -- ``cost_layout`` the frame
the horizontal cost families are drawn in and the request one series of bars
is described by, ``cost_horizontal``, ``cost_repo``, ``cost_stage``,
``cost_review``, ``heatmap``, and ``throughput`` hold six families above the
two, the generic spend ranking, the per-repository one drawn through it, the
per-stage split of that spend into what the cache paid for, the per-review-round
split of it across the two roles a round is worked by, the 7x24 weekday-by-hour
grid, and the per-day resolved-issue strip, and
``usage_bands``, ``usage_series``, ``usage_axis``, ``usage_traces``, and
``usage`` hold the usage family: the four bands a day of usage is counted into
and the roll-up that counts them, the days that roll-up spans and the height
each stack over them reaches, the maxima those heights are rounded up to and
the layout the token and cost scales are assembled in, the bands and cost line
a window is drawn as, and the hero figure they are assembled into.

Callers import the owner they need, so this initializer binds nothing.
Streamlit and Plotly live in the optional ``dashboard`` dependency group, so
no owner here names them at module scope: one that renders or assembles a
figure imports them inside that call, and one that only shapes data for
another owner never imports them at all. An ordinary import must keep working
in the default install, which has neither, and the data an owner shapes stays
testable without them.
"""
