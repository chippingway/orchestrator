# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The suite collects from nested packages without a name collision.

Tests mirror the runtime layout, so the same short module name recurs once per
domain -- one `test_imports.py` per package, one `test_handler.py` per stage.
Under pytest's default import mode a module's name is its path down from the
first directory above it without an `__init__.py`, so those names are only
distinct while every directory on the way is a package. Drop the initializer
beside one and it collects as the top-level module `test_imports`; drop one
higher up and everything below it is renamed to its path from there. Either way
the next copy reached aborts the run with a duplicate-basename error, and which
one that is depends on collection order. `find_spec` is no help on its own: a
directory without an initializer still resolves, as a namespace package.

The root of the tree is the other half: a module parked there is one no domain
owns, and a support module there is one every domain can reach for. Both belong
beside the owner they cover.
"""
from __future__ import annotations

import unittest
from importlib.util import find_spec

from tests.repository.layout_test_support import (
    TESTS_ROOT,
    dotted_name,
    module_directories,
    python_files,
)

# What the tests root itself carries: the initializer making the tree a package
# and the suite-wide fixtures. Everything else lives under the package covering
# the owner it exercises, `tests/support/` for a helper spanning domains, and
# `tests/repository/` for a check on the repository's own files.
_ROOT_LEAVES = ("__init__.py", "conftest.py")


def _recurring_names() -> dict[str, tuple[str, ...]]:
    """The dotted names of every module whose basename is not unique."""
    grouped: dict[str, list[str]] = {}
    for module in python_files(TESTS_ROOT):
        grouped.setdefault(module.stem, []).append(
            dotted_name(module, TESTS_ROOT),
        )
    return {
        basename: tuple(names)
        for basename, names in grouped.items()
        if len(names) > 1
    }


class NestedPackageTest(unittest.TestCase):
    """Every directory the suite collects from is an importable package."""

    def test_every_test_directory_is_a_package(self) -> None:
        # Every directory on the way down, not just the one a module sits in:
        # a package whose children are all packages still names the segment
        # between them, and dropping its initializer renames everything below.
        for directory in module_directories(TESTS_ROOT):
            with self.subTest(directory=str(directory)):
                self.assertTrue((directory / "__init__.py").is_file())

    def test_a_recurring_name_answers_on_its_own_path(self) -> None:
        # The names at risk are the ones the mirror makes recur -- one
        # `test_imports.py` per package, one `test_handler.py` per stage. Each
        # has to resolve on the path its own packages give it, which is what
        # the collection has instead of a rename per copy.
        for basename, names in _recurring_names().items():
            with self.subTest(basename=basename):
                self.assertEqual(len(names), len(set(names)))
                for name in names:
                    self.assertIsNotNone(find_spec(name))


class SuiteRootTest(unittest.TestCase):
    """The root holds the initializer and the shared fixtures, nothing else."""

    def test_the_root_holds_no_test_or_support_module(self) -> None:
        found = tuple(sorted(
            leaf.name for leaf in TESTS_ROOT.iterdir() if leaf.is_file()
        ))
        self.assertEqual(found, tuple(sorted(_ROOT_LEAVES)))


if __name__ == "__main__":
    unittest.main()
