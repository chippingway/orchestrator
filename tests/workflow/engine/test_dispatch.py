# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The dispatch owner's stage lookup."""
from __future__ import annotations

import importlib
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from orchestrator.workflow.engine import dispatch

_ISSUE_NUMBER = 17
_READY_LABEL = "ready"


class StageHandlerLookupTest(unittest.TestCase):
    """Each label resolves to a handler its stage owner holds, per call."""

    def test_every_target_names_an_importable_handler(self) -> None:
        # The table is the only place a label and its owning module are
        # paired, and nothing imports those modules at module scope, so a
        # module renamed out from under an entry would surface as a routing
        # failure on a live issue rather than at import.
        for label, (module_name, handler_name) in dispatch._STAGE_HANDLER_TARGETS.items():
            with self.subTest(label=label):
                owner = importlib.import_module(module_name)
                self.assertTrue(callable(getattr(owner, handler_name)))

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


if __name__ == "__main__":
    unittest.main()
