# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The late-split domain: one generation's frozen record and its telemetry.

Home of what a late generation IS, apart from anything that drives one. A
generation is the record an oversized committed candidate is adjudicated
under -- its identities, the commits frozen for it, what it measured, which
phase its reconciliation reached, the fingerprints it re-reads human content
against, the pull request it holds, the external resources it still owes the
remote, whether it was cancelled, and whether a restart is half-written. The
owners divide by what a reader is asking about it: what any late value has to
look like (``formats``), the vocabularies and the frozen record itself
(``models``), the identities it is keyed by (``identity``), what a hand-edited
or older pinned comment reads back as (``payloads``), the pinned fields it
round-trips through (``state``), the one commit an accepted candidate is let
past the gate on, which deliberately outlives them (``exemption``), the
two-phase restart marker over them
(``restart``), what one event of its life may say (``events``), what a
generation has to prove before any of it may be recorded (``validation``), the
bounded record both observability sinks carry (``records``), and the dual
emission that writes them (``telemetry``).

Callers import the owner they need, so this initializer binds nothing: the
state round-trip costs the GitHub pinned-state model and the telemetry costs
the analytics recorders, and neither should be charged to a caller that wants
the other.
"""
