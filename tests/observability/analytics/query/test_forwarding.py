# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What the temporary read facade still answers for on the connection side."""
from __future__ import annotations

import unittest
from importlib import import_module
from types import MappingProxyType

from orchestrator.observability.analytics.query.execution import ReadQuery

_READ_FACADE = "orchestrator.analytics.read"

_CONNECTIONS = "orchestrator.observability.analytics.query.connections"

_CONNECTION_CACHE = "orchestrator.observability.analytics.query.connection_cache"

# The historical facade name a caller already imports, and the owner attribute
# it now resolves to. The underscored ones are the sharper half: a private name
# a caller reached through the facade is still a name it reached, so it has to
# keep answering -- with the owner's object, not a copy the facade kept.
_FORWARDED = MappingProxyType({
    "AnalyticsReadError": (_CONNECTIONS, "AnalyticsReadError"),
    "_close_quietly": (_CONNECTIONS, "close_quietly"),
    "_default_connect": (_CONNECTIONS, "default_connect"),
    "_default_persistent_connect": (_CONNECTIONS, "default_persistent_connect"),
    "_is_broken_connection_exc": (_CONNECTIONS, "is_broken_connection_exc"),
    "_thread_local": (_CONNECTION_CACHE, "thread_local"),
    "analytics_connection": (_CONNECTION_CACHE, "analytics_connection"),
    "close_thread_local_connection": (
        _CONNECTION_CACHE, "close_thread_local_connection",
    ),
})

_REQUEST_BINDER = "orchestrator.analytics.read_request"


class ForwardedConnectionSurfaceTest(unittest.TestCase):
    """Every connection name the read facade publishes is the owner's object."""

    def test_each_name_resolves_to_the_owner(self) -> None:
        facade = import_module(_READ_FACADE)
        for name, (owner_name, attribute) in _FORWARDED.items():
            with self.subTest(name=name):
                self.assertIs(
                    getattr(facade, name),
                    getattr(import_module(owner_name), attribute),
                )

    def test_the_facade_still_publishes_them(self) -> None:
        # The resolver answers `__all__` off its own inventory, so a name
        # dropped from the manifest would keep resolving by attribute access
        # while disappearing from a wildcard import.
        facade = import_module(_READ_FACADE)
        self.assertTrue(frozenset(_FORWARDED).issubset(facade.__all__))


class ForwardedQueryInputsTest(unittest.TestCase):
    """The read families build the owner's request object, not one of their own."""

    def test_the_binder_resolves_the_owner_s_query(self) -> None:
        binder = import_module(_REQUEST_BINDER)
        request = binder.bind_read_request(binder.SOURCE_READ_SIGNATURE, (), {})
        self.assertIsInstance(binder.resolve_read_query(request), ReadQuery)


if __name__ == "__main__":
    unittest.main()
