# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What the temporary flat read modules still answer for on the query side."""
from __future__ import annotations

import unittest
from importlib import import_module
from types import MappingProxyType

_READ_FACADE = "orchestrator.analytics.read"

_CONNECTIONS = "orchestrator.observability.analytics.query.connections"

_CONNECTION_CACHE = "orchestrator.observability.analytics.query.connection_cache"

_CONDITIONS = "orchestrator.observability.analytics.query.conditions"

_FILTERS = "orchestrator.observability.analytics.query.filters"

_PREDICATES = "orchestrator.observability.analytics.query.predicates"

_REQUEST_MODELS = "orchestrator.observability.analytics.query.request_models"

_REQUESTS = "orchestrator.observability.analytics.query.requests"

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

# The names each flat leaf publishes, grouped by the owner that defines them.
# The hub above the leaves publishes the union of the three, so a caller
# reaching either a leaf or the hub lands on the same object.
_CONDITION_NAMES = (
    ("_agent_event_excluded", _CONDITIONS, "agent_event_excluded"),
    ("_append_where_condition", _CONDITIONS, "append_where_condition"),
    ("_prepend_where_condition", _CONDITIONS, "prepend_where_condition"),
)

_FILTER_NAMES = (
    ("_WhereBuilder", _FILTERS, "WhereBuilder"),
    ("_WindowFilters", _FILTERS, "WindowFilters"),
)

_PREDICATE_NAMES = (
    ("_DAILY_ROLLUP_VIEW", _PREDICATES, "DAILY_ROLLUP_VIEW"),
    ("_build_rollup_window_where", _PREDICATES, "build_rollup_window_where"),
    ("_build_view_window_where", _PREDICATES, "build_view_window_where"),
    ("_build_where", _PREDICATES, "build_where"),
    ("_build_window_where", _PREDICATES, "build_window_where"),
    ("_day_bound", _PREDICATES, "day_bound"),
)

# The flat modules a caller reaches the input half through, and what each name
# they publish resolves to. Same contract as the facade above: the predicate a
# caller builds here has to be the one the read families build, or a filter
# fixed under `query` would reach only half of the callers.
_FORWARDED_INPUTS = MappingProxyType({
    "orchestrator.analytics.predicates": (
        *_CONDITION_NAMES,
        *_FILTER_NAMES,
        *_PREDICATE_NAMES,
    ),
    "orchestrator.analytics._predicate_conditions": _CONDITION_NAMES,
    "orchestrator.analytics._predicate_models": _FILTER_NAMES,
    "orchestrator.analytics._predicate_where": _PREDICATE_NAMES,
    "orchestrator.analytics.read_request": (
        ("FILTERED_READ_SIGNATURE", _REQUESTS, "FILTERED_READ_SIGNATURE"),
        ("HEATMAP_SIGNATURE", _REQUESTS, "HEATMAP_SIGNATURE"),
        ("ISSUE_EVENTS_SIGNATURE", _REQUESTS, "ISSUE_EVENTS_SIGNATURE"),
        ("ISSUES_SIGNATURE", _REQUESTS, "ISSUES_SIGNATURE"),
        ("LIMIT_FIELD", _REQUESTS, "LIMIT_FIELD"),
        ("LIMITED_READ_SIGNATURE", _REQUESTS, "LIMITED_READ_SIGNATURE"),
        ("RECENT_EXIT_LIMIT", _REQUESTS, "RECENT_EXIT_LIMIT"),
        ("RECENT_EXITS_SIGNATURE", _REQUESTS, "RECENT_EXITS_SIGNATURE"),
        ("SOURCE_READ_SIGNATURE", _REQUESTS, "SOURCE_READ_SIGNATURE"),
        ("bind_read_request", _REQUESTS, "bind_read_request"),
        ("resolve_read_query", _REQUESTS, "resolve_read_query"),
        ("window_filters", _REQUESTS, "window_filters"),
    ),
    "orchestrator.analytics.read_request_models": (
        ("ReadConnection", _REQUEST_MODELS, "ReadConnection"),
        ("ReadFilters", _REQUEST_MODELS, "ReadFilters"),
        ("ReadOptions", _REQUEST_MODELS, "ReadOptions"),
        ("ReadRequest", _REQUEST_MODELS, "ReadRequest"),
    ),
})


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
    """Every filter and request name the flat modules publish is the owner's."""

    def test_each_name_resolves_to_the_owner(self) -> None:
        for module_name, forwarded in _FORWARDED_INPUTS.items():
            for name, owner_name, attribute in forwarded:
                with self.subTest(module=module_name, name=name):
                    self.assertIs(
                        getattr(import_module(module_name), name),
                        getattr(import_module(owner_name), attribute),
                    )

    def test_no_flat_module_defines_one_itself(self) -> None:
        # What keeps the forwarding thin: a module that defined a name of its
        # own would be a second implementation the check above cannot see,
        # because it only compares the names the module was asked for.
        for module_name in _FORWARDED_INPUTS:
            defined = tuple(
                name
                for name, member in import_module(module_name).__dict__.items()
                if getattr(member, "__module__", None) == module_name
            )
            with self.subTest(module=module_name):
                self.assertEqual(defined, ())


if __name__ == "__main__":
    unittest.main()
