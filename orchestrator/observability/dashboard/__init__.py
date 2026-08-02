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
with. ``fanout`` runs one wave of that page's readers the way the knob said,
on the calling thread or across a pool capped at the count beside it, and each
of those readers goes through ``scoped_reads`` for the connection it runs on,
``filter_binding`` for the filters its cache key is read back as, and --
before any of them, because it is what a window can be picked at all from --
``static_metadata`` for the extent and filter vocabulary a page opens on. The
readers themselves arrive with the panels they are drawn for, starting with
``breakdowns`` for the six a comparison section is built from.

Callers import the owner they need, so this initializer binds nothing.
Streamlit and Plotly live in the optional ``dashboard`` dependency group, so
an owner here imports them inside the function that renders with them rather
than at module scope: an ordinary import must keep working in the default
install, which has neither, and the data an owner shapes stays testable
without them.
"""
