# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Which rules an inline `# noqa` in the two linted trees may name.

`RUF100` reads a directive for a rule the run has not enabled as dead and
offers to delete it. Two rules are answered a line at a time here rather than
by the selected set -- `BLE001` on the handlers that must catch blind, `N802`
on the one test double that mimics a third-party method name -- so on the
default run they are exactly that kind of directive, and `lint.external` in
`pyproject.toml` is what says so.

The declaration stays honest only while both of its halves are held, and only
one of them can be read off the tree. Which rules a selector enables is Ruff's
own answer and nobody else's -- `F` covers `F401` and not `FLY002`, and a
prefix test here would wave both through -- so the directives are checked by
running Ruff under this repository's configured selectors plus `RUF100`, and a
directive naming a rule that is neither selected nor declared fails there. The
half Ruff has no reading of is the stale entry: a code `lint.external` lists
that no directive carries suppresses nothing, and is read off the tree below.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tomllib
import unittest

from tests.repository.layout_test_support import (
    PACKAGE_ROOT,
    TESTS_ROOT,
    python_files,
)

_REPO_ROOT = PACKAGE_ROOT.parent

# The codes a directive lists, up to the ` - <reason>` the convention ends on.
_DIRECTIVE = re.compile(r"#\s*noqa\s*:\s*([A-Z]+[0-9]+(?:\s*,\s*[A-Z]+[0-9]+)*)")

_ENCODING = "utf-8"

_UNUSED_DIRECTIVE = "RUF100"

# Ruff separates "nothing to report" from "reported something" by exit code,
# and keeps everything else -- an unreadable config, a rule name it does not
# know -- above both, which is the failure this must not read as a clean tree.
_LINT_EXIT_CODES = (0, 1)


def _declared_external() -> frozenset[str]:
    """The rules `pyproject.toml` hands to an audit instead of to the run."""
    lint = tomllib.loads(
        (_REPO_ROOT / "pyproject.toml").read_text(encoding=_ENCODING),
    )["tool"]["ruff"]["lint"]
    return frozenset(lint.get("external", ()))


def _carried_codes() -> frozenset[str]:
    """Every rule an inline directive in the two linted trees names."""
    listed: set[str] = set()
    for root in (PACKAGE_ROOT, TESTS_ROOT):
        for module in python_files(root):
            for codes in _DIRECTIVE.findall(module.read_text(encoding=_ENCODING)):
                listed.update(code.strip() for code in codes.split(","))
    return frozenset(listed)


def _ruff_run() -> subprocess.CompletedProcess[str]:
    """Ruff over the linted trees, its own configuration plus `RUF100`.

    Run from the repository root and by relative path so Ruff resolves
    `pyproject.toml` the way the pre-push check does, and uncached so the
    reading is taken off the tree as it stands rather than off whatever an
    earlier run with other selectors left in `.ruff_cache/`.
    """
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            PACKAGE_ROOT.name,
            TESTS_ROOT.name,
            f"--extend-select={_UNUSED_DIRECTIVE}",
            "--output-format=json",
            "--no-cache",
        ],
        capture_output=True,
        cwd=_REPO_ROOT,
        text=True,
        check=False,
    )


def _dead_directives(completed: subprocess.CompletedProcess[str]) -> list[str]:
    """Where Ruff would strip a directive, as `<file>:<line>` for the failure."""
    located: list[str] = []
    for finding in json.loads(completed.stdout or "[]"):
        if finding["code"] != _UNUSED_DIRECTIVE:
            continue
        module = finding["filename"]
        row = finding["location"]["row"]
        located.append(f"{module}:{row}")
    return located


class NoqaDirectiveTest(unittest.TestCase):
    """The declaration and the directives name the same rules."""

    def test_a_declared_rule_has_a_directive(self) -> None:
        self.assertEqual(sorted(_declared_external() - _carried_codes()), [])

    def test_no_directive_reads_as_dead(self) -> None:
        completed = _ruff_run()

        self.assertIn(completed.returncode, _LINT_EXIT_CODES, completed.stderr)
        self.assertEqual(_dead_directives(completed), [])


if __name__ == "__main__":
    unittest.main()
