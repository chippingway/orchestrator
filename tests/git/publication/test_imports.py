# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Clean-process import checks and package surface for the publication owners."""

from __future__ import annotations

import subprocess
import sys
import unittest

from orchestrator import branch_publication
from orchestrator.git import publication as _publication_package
from orchestrator.git.publication import planning, probes, titles

_MODULES = (
    "orchestrator.git.publication",
    "orchestrator.git.publication.planning",
    "orchestrator.git.publication.probes",
    "orchestrator.git.publication.titles",
)

# The initializer binds nothing, so each name stays reachable only through its
# owner or the historical `branch_publication` facade.
_OWNER_ONLY_NAMES = (
    "_branch_ahead_behind",
    "_first_commit_subject",
    "_infer_subject_prefix",
    "_pr_title_from_commit_or_issue",
    "_prepare_squash",
)

_FACADE_FORWARDS = (
    ("_CONVENTIONAL_RE", probes),
    ("_CONVENTIONAL_TYPES", probes),
    ("_SquashPlan", planning),
    ("_SquashPreparationError", planning),
    ("_branch_ahead_behind", probes),
    ("_first_commit_subject", probes),
    ("_infer_subject_prefix", titles),
    ("_is_conventional_subject", probes),
    ("_is_prefixed_subject", probes),
    ("_parse_ahead_behind", probes),
    ("_pr_title_from_commit_or_issue", titles),
    ("_prepare_squash", planning),
    ("_recent_base_subjects", probes),
    ("_squash_base_sha", planning),
    ("_squash_message", planning),
    ("_squash_subjects", planning),
    ("_subject_prefix", probes),
)


class CleanProcessImportTest(unittest.TestCase):
    """Each owner imports standalone in a fresh interpreter.

    `probes` depends only on the config and git command owners, `titles` only
    on `probes`, and `planning` on both of them plus the verification probes,
    so importing any one of them first must not need a name a half-run module
    has not defined yet. A subprocess per module gives each a clean
    `sys.modules` no other test has already populated, exposing an
    import-order cycle a facade-first suite run would mask.
    """

    def test_each_module_imports_standalone(self) -> None:
        for module in _MODULES:
            with self.subTest(module=module):
                completed = subprocess.run(
                    [sys.executable, "-c", f"import {module}"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, msg=completed.stderr)


class PackageSurfaceTest(unittest.TestCase):
    """The initializer carries no bindings; the publication facade forwards."""

    def test_initializer_exposes_no_owner_names(self) -> None:
        for owner_only_name in _OWNER_ONLY_NAMES:
            with self.subTest(name=owner_only_name):
                with self.assertRaises(AttributeError):
                    getattr(_publication_package, owner_only_name)

    def test_facade_resolves_owner_objects(self) -> None:
        # `branch_publication` keeps serving the historical names, and it
        # resolves them to the owners' definitions rather than to copies.
        for export_name, owner in _FACADE_FORWARDS:
            with self.subTest(name=export_name):
                self.assertIs(
                    getattr(branch_publication, export_name),
                    getattr(owner, export_name),
                )


if __name__ == "__main__":
    unittest.main()
