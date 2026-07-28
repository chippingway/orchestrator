# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Analytics dashboard owners.

Destination for the Streamlit page rendered over the operator's Postgres
target: the filter state a run of it carries, the read plans it issues, the
KPI, chart, table, and drilldown components, and the theme tokens they share.

Callers import the owner they need, so this initializer binds nothing.
Streamlit and Plotly live in the optional ``dashboard`` dependency group, so
an owner here imports them inside the function that renders with them rather
than at module scope: an ordinary import must keep working in the default
install, which has neither, and the data an owner shapes stays testable
without them.
"""
