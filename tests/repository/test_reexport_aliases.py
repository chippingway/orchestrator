# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Which modules may declare a re-export by aliasing a name to itself.

`F401` reads an import nothing below it reads as dead, and the way a module
says otherwise is to spell the name twice: `from owner import X as X` is a
re-export both Ruff and a reader can see. `PLC0414` reads that same spelling as
an alias that renames nothing, so the two rules disagree wherever the
convention is used, and the disagreement is settled one path at a time under
`[tool.ruff.lint.per-file-ignores]` rather than tree-wide.

A tree-wide waiver would cover every module written after it, so the narrow
form is the one kept -- and it stays honest only while both of its halves are
read off the tree. A module that carries the exemption has to need it -- every
name it aliases to itself is one it never reads, so dropping the alias would
cost that name to `F401` -- and a module that does not carry it has to alias
nothing, which is what keeps an alias on a name its own module already reads
from passing as a re-export.

Initializers are outside all of it, on Ruff's own terms: `PLC0414` never
reports one, because the alias there is the conventional way a package marks
what it publishes. A waiver for an `__init__.py` would waive nothing, so the
scope read below is every module the trees carry except those.
"""
from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

from tests.repository.import_test_support import loaded_names, same_name_aliases
from tests.repository.layout_test_support import (
    PACKAGE_ROOT,
    TESTS_ROOT,
    python_files,
)

_REPO_ROOT = PACKAGE_ROOT.parent

_RULE = "PLC0414"

# Ruff matches a per-file key as a glob, so these are what separates a path
# naming one audited module from a pattern waiving the rule for files nobody
# has read -- the ones written after the entry landed above all.
_GLOB_CHARACTERS = "*?[]"

_INITIALIZER = "__init__.py"


def _audited_modules() -> tuple[Path, ...]:
    """Every module the two linted trees carry, bar the initializers."""
    return tuple(
        module
        for root in (PACKAGE_ROOT, TESTS_ROOT)
        for module in python_files(root)
        if module.name != _INITIALIZER
    )


def _repository_path(path: Path) -> str:
    """The spelling a per-file entry names the module by."""
    return path.relative_to(_REPO_ROOT).as_posix()


def _waived_paths() -> frozenset[str]:
    """The paths the rule is waived for, read off the Ruff config itself."""
    ruff_lint = tomllib.loads(
        (_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"),
    )["tool"]["ruff"]["lint"]
    return frozenset(
        pattern
        for pattern, rules in ruff_lint["per-file-ignores"].items()
        if _RULE in rules
    )


class ReexportAliasTest(unittest.TestCase):
    """The convention is used only where the rule is waived for it."""

    def test_only_a_waived_module_self_aliases(self) -> None:
        aliasing = frozenset(
            _repository_path(module)
            for module in _audited_modules()
            if same_name_aliases(module)
        )

        self.assertEqual(aliasing, _waived_paths())

    def test_a_waived_alias_is_unread_by_its_module(self) -> None:
        for module in _audited_modules():
            path = _repository_path(module)
            if path not in _waived_paths():
                continue
            read_here = same_name_aliases(module) & loaded_names(module)
            with self.subTest(module=path):
                self.assertEqual(
                    sorted(read_here),
                    [],
                    "a name the module reads needs no alias to survive F401",
                )

    def test_each_waiver_names_one_module_that_exists(self) -> None:
        for pattern in _waived_paths():
            with self.subTest(pattern=pattern):
                globbed = [
                    character
                    for character in _GLOB_CHARACTERS
                    if character in pattern
                ]
                self.assertEqual(
                    globbed,
                    [],
                    "a per-file waiver names an exact path, never a glob",
                )
                self.assertTrue((_REPO_ROOT / pattern).is_file())


if __name__ == "__main__":
    unittest.main()
