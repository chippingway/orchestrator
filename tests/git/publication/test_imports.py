# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Clean-process import checks and owner boundaries for the publication package."""

from __future__ import annotations

import subprocess
import sys
import unittest
from importlib import import_module
from importlib.util import find_spec
from pathlib import Path
from types import MappingProxyType

from orchestrator.git import publication as _publication_package

_PACKAGE = "orchestrator.git.publication"

_OWNERS = ("planning", "probes", "rewrite", "squash", "titles")

_MODULES = (_PACKAGE, *(f"{_PACKAGE}.{owner}" for owner in _OWNERS))

# Bound at module scope, so collecting this file is what plants every owner in
# `sys.modules` rather than whichever publication test happened to run first.
_OWNER_MODULES = MappingProxyType({
    owner: import_module(f"{_PACKAGE}.{owner}") for owner in _OWNERS
})

# The divergence probe, named once because it recurs in the owner surface
# below and in the facade slice under it.
_AHEAD_BEHIND = "_branch_ahead_behind"

# What each owner defines: the whole publication surface, split by the module a
# patch aimed at one of these names has to land on.
_DEFINED = MappingProxyType({
    "planning": (
        "_SquashPlan",
        "_SquashPreparationError",
        "_prepare_squash",
        "_squash_base_sha",
        "_squash_message",
        "_squash_subjects",
    ),
    "probes": (
        "_CONVENTIONAL_RE",
        "_CONVENTIONAL_TYPES",
        "_CONVENTIONAL_TYPES_ALT",
        "_PREFIXED_RE",
        "_PREFIX_TOKEN_RE",
        _AHEAD_BEHIND,
        "_first_commit_subject",
        "_is_conventional_subject",
        "_is_prefixed_subject",
        "_parse_ahead_behind",
        "_recent_base_subjects",
        "_subject_prefix",
    ),
    "rewrite": (
        "_create_squash_commit",
        "_rewrite_squash",
        "_rollback_squash",
        "_squash_commit_env",
        "_squash_failure",
        "log",
    ),
    "squash": ("_squash_and_force_push",),
    "titles": (
        "_infer_subject_prefix",
        "_pr_title_from_commit_or_issue",
    ),
})

# The functions and classes among those, which carry the module that defines
# them; the rest are the subject vocabulary, the compiled patterns, and the
# logger, none of which report one.
_DEFINED_CALLABLES = MappingProxyType({
    owner: tuple(
        name for name in names
        if callable(getattr(_OWNER_MODULES[owner], name))
    )
    for owner, names in _DEFINED.items()
})

# The owner each name is defined on, which the initializer and every sibling
# owe an `AttributeError` for.
_OWNER_OF = MappingProxyType({
    name: owner for owner, names in _DEFINED.items() for name in names
})

# Each name paired with a sibling owner that must not answer for it.
_FOREIGN_LOOKUPS = tuple(
    (sibling, name)
    for name, owner in _OWNER_OF.items()
    for sibling in _OWNERS
    if sibling != owner
)

# The one aggregate facade above the package, and the slice of these names it
# answers for: seven. Every other name is the owner's alone, so this is the
# whole set of second sites one of them can be patched at.
_FACADE = "orchestrator.workflow"

_FACADE_PUBLISHED = (
    _AHEAD_BEHIND,
    "_first_commit_subject",
    "_infer_subject_prefix",
    "_is_conventional_subject",
    "_is_prefixed_subject",
    "_pr_title_from_commit_or_issue",
    "_squash_and_force_push",
)

# Every flat spelling a publication helper could be reached through beside the
# package.
_FLAT_MODULE_PATTERNS = ("branch_publication.py", "_branch_publication_*.py")

# The module paths a second aggregate over the git domains would take: the
# spelling itself, and the inventory and resolver hooks one would be built
# from.
_ABSENT_MODULES = (
    "orchestrator._worktrees_export_manifest",
    "orchestrator._worktrees_exports",
    "orchestrator.worktrees",
)

# The channel operators filter a squash on. It is a name rather than a module
# path, so no module answers at the spelling it reads like.
_LOGGER_NAME = "orchestrator.branch_publication"

_LOGGER_OWNER = "rewrite"


def _defined_here(owner: str) -> tuple:
    """The functions and classes the owner's own module defines."""
    module = _OWNER_MODULES[owner]
    return tuple(sorted(
        name for name, member in module.__dict__.items()
        if getattr(member, "__module__", None) == f"{_PACKAGE}.{owner}"
    ))


class CleanProcessImportTest(unittest.TestCase):
    """Each owner imports standalone in a fresh interpreter.

    `probes` depends only on the config and git command owners, `titles` only
    on `probes`, `planning` on both of them plus the verification probes, and
    `rewrite` / `squash` layer on top, so importing any one of them first must
    not need a name a half-run module has not defined yet. A subprocess per
    module gives each a clean `sys.modules` no other test has already
    populated, exposing an import-order cycle a package-first suite run would
    mask.
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
    """The initializer carries no bindings of its own."""

    def test_initializer_exposes_no_owner_names(self) -> None:
        for owner_only_name in _OWNER_OF:
            with self.subTest(name=owner_only_name):
                with self.assertRaises(AttributeError):
                    getattr(_publication_package, owner_only_name)


class OwnerBoundaryTest(unittest.TestCase):
    """No facade of this domain's own, and no sibling, answers for a name.

    The workflow facade still answers for the slice below, so a caller reading
    a name there is patched there; what this class holds to is that nothing in
    the package's own layer, and no second aggregate above it, becomes a
    further site the same name resolves at.
    """

    def test_no_flat_module_sits_beside_the_package(self) -> None:
        # A module at the flat spelling would be a second import site for the
        # names these owners define -- and one a patch aimed at an owner would
        # not intercept.
        package_root = Path(import_module("orchestrator").__file__).parent
        for pattern in _FLAT_MODULE_PATTERNS:
            with self.subTest(pattern=pattern):
                self.assertEqual(list(package_root.glob(pattern)), [])

    def test_no_second_aggregate_sits_above(self) -> None:
        # An aggregate over the git domains would answer for a superset of the
        # slice below with the owners' own objects, so identity alone would
        # never show the extra surface a mock has to be aimed at. Resolving the
        # spec rather than stat-ing one path catches a copy planted anywhere
        # the interpreter would find it.
        for module in _ABSENT_MODULES:
            with self.subTest(module=module):
                self.assertIsNone(find_spec(module))

    def test_no_sibling_answers_for_a_foreign_name(self) -> None:
        # The owners reach each other by module rather than by name, so a
        # sibling never becomes a second binding site for a helper it only
        # calls.
        for sibling, name in _FOREIGN_LOOKUPS:
            with self.subTest(sibling=sibling, name=name):
                self.assertFalse(hasattr(_OWNER_MODULES[sibling], name))

    def test_defined_names_report_their_owner(self) -> None:
        # A helper lifted off a sibling would resolve here just as well, so the
        # defining module is what separates an owner from an importer of one --
        # and comparing both ways keeps the inventory above complete, so a
        # helper added to an owner is an edit here rather than a silent gap.
        for owner, names in _DEFINED_CALLABLES.items():
            with self.subTest(owner=owner):
                self.assertEqual(_defined_here(owner), tuple(sorted(names)))


class AggregateFacadeTest(unittest.TestCase):
    """The facade above answers for its declared slice and nothing more."""

    def test_the_facade_answers_for_its_slice_alone(self) -> None:
        # The facade hands back the owner's own object and caches it, so
        # patching there and patching the owner are two interceptions rather
        # than one -- which makes which names it carries the boundary a caller
        # has to be read against.
        for name in _OWNER_OF:
            with self.subTest(name=name):
                self._assert_facade_answer(name)

    def _assert_facade_answer(self, name: str) -> None:
        facade = import_module(_FACADE)
        owned = getattr(_OWNER_MODULES[_OWNER_OF[name]], name)
        if name in _FACADE_PUBLISHED:
            self.assertIs(getattr(facade, name), owned)
        else:
            # `log` is the case identity has to decide: the facade publishes a
            # logger of its own under that name, and it is not this one.
            self.assertIsNot(getattr(facade, name, None), owned)


class LoggerChannelTest(unittest.TestCase):
    """The squash reports on the domain's channel, not on a module path."""

    def test_logger_keeps_its_operator_facing_name(self) -> None:
        # Operators filter and attach handlers on this prefix, so it is a
        # published name that outranks the module layout beneath it.
        self.assertEqual(_OWNER_MODULES[_LOGGER_OWNER].log.name, _LOGGER_NAME)


if __name__ == "__main__":
    unittest.main()
