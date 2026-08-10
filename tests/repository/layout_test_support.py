# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Readers the repository-wide architecture checks find their subjects with.

Each reader walks a tree on disk rather than an inventory kept beside it, so a
module added anywhere under `orchestrator/` or `tests/` is a subject the day it
lands rather than the day someone remembers to list it. Directories are read
two ways for that reason: the packages an initializer declares, and the
directories a module actually sits in or under. Where those two disagree is a
namespace directory nobody declared, which is exactly what a check has to see.
"""
from __future__ import annotations

import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]

PACKAGE = "orchestrator"

PACKAGE_ROOT = _REPO_ROOT / PACKAGE

TESTS_ROOT = _REPO_ROOT / "tests"

_ENCODING = "utf-8"


def parsed(path: Path) -> ast.Module:
    """The module's syntax tree, which both source readers walk."""
    return ast.parse(path.read_text(encoding=_ENCODING))


def dotted_name(path: Path, root: Path) -> str:
    """The import path the module file answers on."""
    parts = list(path.relative_to(root.parent).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def module_path(name: str, root: Path) -> Path:
    """Where a dotted module name sits on disk."""
    under_root = name.split(".")[1:]
    return root.joinpath(*under_root).with_suffix(".py")


def python_files(root: Path) -> tuple[Path, ...]:
    """Every module under a tree, the initializers included."""
    return tuple(sorted(root.rglob("*.py")))


def package_directories(root: Path) -> tuple[Path, ...]:
    """Every directory under a tree that an initializer makes a package."""
    return tuple(sorted(
        initializer.parent for initializer in root.rglob("__init__.py")
    ))


def module_directories(root: Path) -> tuple[Path, ...]:
    """Every directory a module sits in or under, the tree root included.

    A directory holding only subdirectories counts: it is on the import path of
    everything below it, so an initializer missing there is as much a namespace
    directory as one missing beside a module.
    """
    found: set[Path] = set()
    for module in python_files(root):
        found.update(
            parent
            for parent in (module.parent, *module.parent.parents)
            if parent == root or root in parent.parents
        )
    return tuple(sorted(found))
