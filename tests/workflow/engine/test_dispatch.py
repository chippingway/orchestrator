# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The dispatch owner's stage lookup, and the facade still forwarding it."""
from __future__ import annotations

import importlib
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from orchestrator import _workflow_export_manifest, workflow
from orchestrator.workflow.engine import dispatch

from tests.reexport_test_support import lazy_targets


# Every name the workflow facade answers for, and nothing besides. Callers
# outside the package reach the owner through it, so a forward that stops
# resolving is a break rather than a rename -- and a name added to it is a new
# public export that outlives whatever refactor introduced it, which is why
# `_STAGE_HANDLER_TARGETS` is absent: the facade publishes the historical
# `_ISSUE_HANDLER_NAMES` view of that table instead.
_FACADE_FORWARDS = (
    "_CAP_EXEMPT_FAMILY_LABELS",
    "_FAMILY_AWARE_LABELS",
    "_FAMILY_BUCKET_ISSUE",
    "_ISSUE_HANDLER_NAMES",
    "_PollablePartition",
    "_PollablePartitionBuilder",
    "_classify_pollable_issue",
    "_dispatch_via_scheduler",
    "_drain_scheduler_family_bucket",
    "_family_bucket_cap_exempt",
    "_issue_is_closed",
    "_partition_pollable_issues",
    "_process_issue",
    "_read_issue_routing",
    "_refetch_and_process",
    "_route_issue_to_handler",
    "_scheduler_per_repo_cap",
    "_submit_scheduler_family_bucket",
    "_submit_scheduler_fanout_issues",
)

_ISSUE_NUMBER = 17
_READY_LABEL = "ready"


class StageHandlerLookupTest(unittest.TestCase):
    """Each label resolves to a handler its stage facade owns, per call."""

    def test_every_target_names_an_importable_handler(self) -> None:
        # The table is the only place a label and its owning module are
        # paired, and nothing imports those modules at module scope, so a
        # module renamed out from under an entry would surface as a routing
        # failure on a live issue rather than at import.
        for label, (module_name, handler_name) in dispatch._STAGE_HANDLER_TARGETS.items():
            with self.subTest(label=label):
                owner = importlib.import_module(module_name)
                self.assertTrue(callable(getattr(owner, handler_name)))

    def test_handler_names_view_covers_every_target(self) -> None:
        # `_ISSUE_HANDLER_NAMES` is the label -> handler-name half of the same
        # table, published for callers outside the package. A label routed by
        # one and absent from the other would hand such a caller a partial
        # dispatch map that still looks complete.
        self.assertEqual(
            dispatch._ISSUE_HANDLER_NAMES,
            {
                label: handler_name
                for label, (_module, handler_name)
                in dispatch._STAGE_HANDLER_TARGETS.items()
            },
        )

    def test_handler_is_resolved_at_dispatch_time(self) -> None:
        # The handler is read off its owner per call rather than bound when
        # this module imports, so a patch installed after import intercepts
        # the dispatch -- which is what every stage's routing test relies on.
        module_name, handler_name = dispatch._STAGE_HANDLER_TARGETS[_READY_LABEL]
        issue = SimpleNamespace(number=_ISSUE_NUMBER)
        spec = SimpleNamespace(slug="owner/repo")
        ready_handler = Mock()
        with patch.object(
            importlib.import_module(module_name), handler_name, ready_handler,
        ):
            dispatch._route_issue_to_handler(None, spec, issue, _READY_LABEL)
        ready_handler.assert_called_once_with(None, spec, issue)


class DispatchFacadeForwardTest(unittest.TestCase):
    """The workflow facade resolves each name to the owner's exact object."""

    def test_facade_forwards_the_owner_objects(self) -> None:
        for forwarded_name in _FACADE_FORWARDS:
            with self.subTest(name=forwarded_name):
                self.assertIs(
                    getattr(workflow, forwarded_name),
                    getattr(dispatch, forwarded_name),
                )

    def test_facade_inventory_is_the_historical_names(self) -> None:
        # The manifest is the compatibility surface, not a mirror of the owner:
        # a helper introduced while the owner is assembled must not become a
        # facade export on the way in. Comparing both directions is what keeps
        # an addition as visible as a dropped forward.
        self.assertEqual(
            {
                export_name
                for export_name, target in lazy_targets(_workflow_export_manifest).items()
                if target.module_name == dispatch.__name__
            },
            set(_FACADE_FORWARDS),
        )


if __name__ == "__main__":
    unittest.main()
