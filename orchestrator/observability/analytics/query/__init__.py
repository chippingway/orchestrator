# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Analytics query owners.

Destination for the read side of the operator's Postgres target: the typed
filters and connection inputs one request carries, the query families built
from them, and the read models a page renders.

Callers import the owner they need, so this initializer binds nothing, and
the connection stays under the owner that opens it -- a read model is a
plain dataclass, and importing one must not reach a database.
"""
