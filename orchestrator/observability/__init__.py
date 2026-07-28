# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Observation-only domain owners.

Destination for the four surfaces that watch a run without steering it: the
project-local analytics sink and everything downstream of it (``analytics``),
the provider-payload parser that turns one finished agent run into tokens and
cost (``usage``), the Streamlit page rendered over the operator's Postgres
target (``dashboard``), and the file-backed trajectory viewer beside it
(``trajectory_viewer``). Each arrives under its own subpackage; the flat
``analytics`` package and the ``usage``, ``dashboard*``, ``trajectory_reader``,
and ``trajectory_dashboard`` modules beside it stay the import site every
historical caller names until the responsibility they hold has an owner here.

Callers import the owner they need, so this initializer binds nothing, and
nothing under it carries an export manifest or a resolver hook -- a name is
imported from the module that defines it, and a patch targets that module.
Two constraints hold for every owner that lands here. Nothing observed is on
the workflow's decision path, so no owner may import the workflow engine, a
stage, or an application entrypoint: the dependency runs one way, and the
pages compose these owners rather than the reverse. And Streamlit and Plotly
live in an optional dependency group, so an owner reaches them inside the
function that renders with them rather than at module scope -- importing
anything here has to work in the default install, which has neither.
"""
