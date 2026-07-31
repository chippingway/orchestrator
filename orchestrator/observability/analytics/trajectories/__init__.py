# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Trajectory sink owners.

Home of the opt-in, default-off per-run reasoning sink. The owners divide by
what one record passes through on its way to disk: the caps it is measured
against and the two models it is charged as (``models``), the redaction and
head/tail truncation every free-text field is put through (``sanitize``), the
shape those fields are assembled into and the order the variable arrays are
drawn from the budget in (``serialize``), the gate, the parse, the Codex
backfill, and the fail-open guard around the whole write (``persistence``),
and the bare append a caller outside a tracked run reaches (``api``). The
lock that append and the by-age prune both take is minted by the recording
``io`` owner, which is loaded once per process, so it survives the rebuild
``api`` is put through for each analytics package instance.

Callers import the owner they need, so this initializer binds nothing. The
write is entered from inside a tracked agent run, so it stays free of the
query and viewer graphs that later read the sink back. Everything from
``persistence`` down is also free of the recording package that composes it --
an `agent_exit` reaches this owner, not the reverse -- while ``api`` sits
above those recorders, since resolving where a bare append lands is what the
settings holder they capture answers.
"""
