# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Analytics query owners.

Destination for the read side of the operator's Postgres target: the typed
filters and connection inputs one request carries, the query families built
from them, and the read models a page renders.

The connection half is here already. ``connections`` owns what a read dials
with -- the lazily imported driver, the two connect factories, and the one
exception every driver failure is wrapped in; ``connection_cache`` owns the
persistent socket a thread reuses across many reads and the two events that
evict it; and ``execution`` owns one SELECT: whose connection it runs on and
whether that connection is closed afterwards.

So is what a read is asked for. ``requests`` owns the keyword vocabulary every
public read is called by and the bind of one such call into the typed parts
``request_models`` declares; ``filters`` owns the selection those parts project
onto and the builder a predicate and its bindings accumulate in together;
``predicates`` owns the `WHERE` clause that selection becomes against each of
the three tables it can be scanned on; and ``conditions`` owns the splice of a
table's own required condition into it, plus the probe that decides whether an
event filter leaves a view-backed read any rows at all.

Callers import the owner they need, so this initializer binds nothing, and the
connection stays under the owner that opens it -- a read model is a plain
dataclass, and importing one must not reach a database.
"""
