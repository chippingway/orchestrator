# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Analytics recording owners.

Destination for the append side of the analytics sink: the record each event
family is built as and the JSONL persistence under it. Where that file is
written, and whether it is written at all, is answered by the ``config`` owner
beside this package rather than here -- the read path and the sync ask the same
owner, and a knob has one home.

Callers import the owner they need, so this initializer binds nothing. This
is the one analytics path the orchestrator process itself runs, and it runs
fail-open inside a tracked agent run, so it stays free of the query, sync,
and page graphs above it.
"""
