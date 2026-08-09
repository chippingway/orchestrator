# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Analytics domain owners.

Destination for the project-local JSONL sink and everything downstream of it.
``recording`` owns the append side -- the event families a tick, a stage
evaluation, and a tracked agent run write; ``query`` owns the read models the
pages ask the operator's Postgres target for; ``sync`` owns the ingestion that
fills that target from the JSONL; and ``trajectories`` owns the opt-in
per-run reasoning sink beside the analytics one. ``recording`` and
``trajectories`` are here in full, the pair the orchestrator process itself
runs, and ``query`` holds the connection half: what a read dials with, the
socket a thread reuses, and the single SELECT run over it. Beside them sit the
owners neither sink may answer separately: ``sink``, the record envelope, the
JSONL line, both files' locks, and the log channel a refused write is reported
on; ``config``, the parse of the six environment knobs, over ``settings``,
where those parsed values are bound and where a caller patches one; and
``retention`` over ``retention_scan`` / ``retention_rewrite``, the by-age
prune that bounds both JSONL files -- each on its own path, retention knob,
and lock, but through one scan and one rewrite, so the two cannot disagree
about what an expired or malformed record costs.

``sink`` and ``settings`` are what keep the two write packages acyclic:
``recording`` composes the trajectory write, so the trajectory owners reach
the envelope, the line, and the knobs on these owners rather than back through
the recorders that called them.

Callers import the owner they need, so this initializer binds nothing: the
recording path runs inside every tracked agent run, and a binding here would
put ``psycopg`` and the whole read-model graph behind that import.
"""
