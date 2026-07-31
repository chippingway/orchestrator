# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Analytics domain owners.

Destination for the project-local JSONL sink and everything downstream of it.
``recording`` owns the append side -- the event families a tick, a stage
evaluation, and a tracked agent run write; ``query`` owns the read models the
pages ask the operator's Postgres target for; ``sync`` owns the ingestion that
fills that target from the JSONL; and ``trajectories`` owns the opt-in
per-run reasoning sink beside the analytics one. Two are here already:
``config``, the environment knobs all four are configured by, which is why it
sits beside them rather than inside any one of them, and ``recording``, the
only one of them the orchestrator process itself runs. The retention owner
they share arrives beside them.

Callers import the owner they need, so this initializer binds nothing: the
recording path runs inside every tracked agent run, and a binding here would
put ``psycopg`` and the whole read-model graph behind that import.
"""
