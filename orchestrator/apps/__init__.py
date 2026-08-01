# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Application entrypoints.

The destination for the targets an operator starts something with, as opposed
to the domain owners those targets compose. An app names owners; no owner names
an app, which is the direction the observability tree's own layering check
enforces from the other side. The trajectory viewer's target is the one that
has an owner here so far -- the analytics page is still started at
``orchestrator/dashboard.py``, and the CLI at ``orchestrator/cli.py``.

``bootstrap`` is what every app here shares: the repo-root ``sys.path`` shim a
launcher that executes a file as a top-level script needs, since such a launch
puts only the file's own directory on the path and the absolute
``orchestrator.*`` imports beneath it would not resolve.

``trajectory_dashboard`` is the file-backed trajectory viewer's ``streamlit
run`` target. It composes the viewer owners inside the entry function rather
than at module scope, alongside Streamlit itself: the shim has to run before an
``orchestrator.*`` name is resolved at all under a script launch, so deferring
the composition is what keeps the two orderings the same one. Importing the
module therefore costs the shim and nothing else, which is what lets a caller
reach it in an install carrying no viewer dependencies.

Callers name the app they start, so this initializer binds nothing.
"""
