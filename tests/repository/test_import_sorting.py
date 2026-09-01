# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The two linted trees keep the import order Ruff sorts them into.

`I001` sits outside the set the Ruff run selects, so the audit that opts into
it -- `ruff check orchestrator tests --select=I001` -- is the whole of what
holds that order, and running it from here is what puts it in front of a
change rather than behind one.

The order is Ruff's own answer rather than one a first-party reader could
reproduce. Which section a module lands in is what `src` resolves it to, and
how the members one module is read for are spelled is what
`[tool.ruff.lint.isort]` says: Ruff's default hands an aliased member a
statement of its own, and the modules here read most of their neighbours under
an alias, so `combine-as-imports` is what keeps one read spelled as one
statement -- and every file it names under the import ceiling WPS201 holds it
to.
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest

from tests.repository.layout_test_support import PACKAGE_ROOT, TESTS_ROOT

_REPO_ROOT = PACKAGE_ROOT.parent

_RULE = "I001"

# Ruff separates "nothing to report" from "reported something" by exit code,
# and keeps everything else -- an unreadable config, a rule name it does not
# know -- above both, which is the failure this must not read as a sorted tree.
_LINT_EXIT_CODES = (0, 1)


def _ruff_run() -> subprocess.CompletedProcess[str]:
    """The audit itself, spelled the way the pre-push check runs it.

    From the repository root and by relative path so Ruff resolves
    `pyproject.toml` -- the isort settings above all -- and uncached so the
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
            f"--select={_RULE}",
            "--output-format=json",
            "--no-cache",
        ],
        capture_output=True,
        cwd=_REPO_ROOT,
        text=True,
        check=False,
    )


def _unsorted_blocks(completed: subprocess.CompletedProcess[str]) -> list[str]:
    """Where Ruff would rewrite an import block, as `<file>:<line>`."""
    located: list[str] = []
    for finding in json.loads(completed.stdout or "[]"):
        module = finding["filename"]
        row = finding["location"]["row"]
        located.append(f"{module}:{row}")
    return located


class ImportSortingTest(unittest.TestCase):
    """Nothing in either tree is left for the sorter to rewrite."""

    def test_no_module_reports_unsorted_imports(self) -> None:
        completed = _ruff_run()

        self.assertIn(completed.returncode, _LINT_EXIT_CODES, completed.stderr)
        self.assertEqual(_unsorted_blocks(completed), [])


if __name__ == "__main__":
    unittest.main()
