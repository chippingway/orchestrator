# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Which rules an inline `# noqa` in the two linted trees may name.

The run is Ruff's own default rule set plus `E501`, and `RUF100` -- which that
set enables -- reads a directive naming a rule the run has not enabled as dead
and offers to delete it. One rule is answered a line at a time outside the run
instead: `N802`, on the one test double that mimics a third-party method name.
On the default run its directive is exactly that kind of directive, and
`lint.external` in `pyproject.toml` is what says so. The handlers that must
catch blind need no entry beside it, because the default set selects `BLE001`
itself.

That declaration stays honest only while both of its halves are held, and only
one of them can be read off the tree. Which rules a selector enables is Ruff's
own answer and nobody else's -- `F` covers `F401` and not `FLY002`, and a
prefix test here would wave both through -- so the directives are checked by
running Ruff under this repository's configured selectors plus `RUF100`, and a
directive naming a rule that is neither selected nor declared fails there. The
half Ruff has no reading of is the stale entry: a code `lint.external` lists
that no directive carries suppresses nothing, and is read off the tree below.

Under both halves sits the reading neither of them makes: that a directive
names any rule at all. One that names none suppresses whatever its line
reports now and whatever the next edit to that line makes it report, and the
file-wide `# ruff: noqa` spelling does the same for everything under it. Ruff
honours both and reports neither, so a blanket waiver is the one suppression
nothing above would notice, and the last check below is what keeps either
spelling out of the two trees.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tokenize
import tomllib
import unittest
from collections.abc import Iterator
from pathlib import Path

from tests.repository.layout_test_support import (
    PACKAGE_ROOT,
    TESTS_ROOT,
    python_files,
)

_REPO_ROOT = PACKAGE_ROOT.parent

# The codes a directive lists, up to the ` - <reason>` the convention ends on.
_DIRECTIVE = re.compile(r"#\s*noqa\s*:\s*([A-Z]+[0-9]+(?:\s*,\s*[A-Z]+[0-9]+)*)")

# A comment that opens a suppression, line-level or file-wide, and the codes it
# has to go on to name for that suppression to be one somebody chose.
_SUPPRESSION = re.compile(r"^#\s*(?:ruff\s*:\s*|flake8\s*:\s*)?noqa\b", re.IGNORECASE)
_NAMES_A_RULE = re.compile(r"noqa\s*:\s*[A-Z]+[0-9]+", re.IGNORECASE)

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


def _blanket_lines(module: Path) -> Iterator[str]:
    """Where a comment in one module waives every rule at once.

    Tokenizing rather than scanning the text is what keeps a prose mention of
    a directive -- this module's own docstring above all -- from reading as
    one.
    """
    with module.open("rb") as module_file:
        for token in tokenize.tokenize(module_file.readline):
            if token.type != tokenize.COMMENT:
                continue
            opens = _SUPPRESSION.match(token.string)
            if opens and not _NAMES_A_RULE.search(token.string):
                yield f"{module}:{token.start[0]}"


def _blanket_suppressions() -> list[str]:
    """Every line in the two linted trees a blanket waiver sits on."""
    located: list[str] = []
    for root in (PACKAGE_ROOT, TESTS_ROOT):
        for module in python_files(root):
            located.extend(_blanket_lines(module))
    return located


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

    def test_no_suppression_is_blanket(self) -> None:
        self.assertEqual(_blanket_suppressions(), [])


if __name__ == "__main__":
    unittest.main()
