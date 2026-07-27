# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Runtime identity and wildcard inventory for the lazy facades."""
from __future__ import annotations

import unittest

from tests.reexport_test_facades import LAZY_FACADES
from tests.reexport_test_support import lazy_targets, resolve_target


class ReexportRuntimeTest(unittest.TestCase):
    def test_targets_preserve_identity_and_import(self) -> None:
        for module, manifest in LAZY_FACADES:
            for name, target in lazy_targets(manifest).items():
                with self.subTest(module=module.__name__, name=name):
                    resolved = resolve_target(module, name, target)
                    self.assertIs(resolved.direct, resolved.expected)
                    self.assertIs(resolved.imported, resolved.expected)

    def test_wildcard_inventory_resolves(self) -> None:
        for module, _manifest in LAZY_FACADES:
            with self.subTest(module=module.__name__):
                namespace = {
                    name: getattr(module, name)
                    for name in module.__all__
                }
                self.assertEqual(set(namespace), set(module.__all__))
                self.assertTrue(all(
                    exported is getattr(module, name)
                    for name, exported in namespace.items()
                ))
