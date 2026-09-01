# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Static readers for what a module imports.

Reading the source rather than the imported module is what lets the checks
answer for every file in the tree, including the ones an in-process import
would charge the suite for, and what separates the two questions a layering
rule asks: what a module costs to load, and what it reaches inside a call.

Module scope is everything the interpreter runs on the import, which includes
a class body -- a class is built by executing its body at the point the
statement is reached, so an import there is paid for exactly like one at the
top of the file. Only a function body is deferred, methods included.

A target is reported as written, absolute or relative. A relative one names its
module by position rather than by owner, so no check can place it in a layer;
keeping its dots is what makes it visible as such rather than passing for a
target outside the package.
"""
from __future__ import annotations

import ast
from pathlib import Path

from tests.repository.layout_test_support import parsed

_DEFERRED_SCOPES = (ast.AsyncFunctionDef, ast.FunctionDef)

_IMPORT_NODES = (ast.Import, ast.ImportFrom)


def _imported_targets(node: ast.stmt) -> tuple[str, ...]:
    """The dotted targets one import statement names.

    A `from` import is reported at the depth it reaches -- `orchestrator.git`
    plus the name taken out of it -- so a prefix test tells a submodule import
    apart from an import of the package above it.

    A relative one keeps its leading dots: `from ..workflow import engine` is
    `..workflow.engine`, which names no module a check could place and matches
    no absolute prefix. Reporting it as `workflow.engine` would make it look
    like a target outside the package, and every rule keyed on the package
    prefix would wave it through.
    """
    if isinstance(node, ast.Import):
        return tuple(alias.name for alias in node.names)
    root = "".join(("." * node.level, node.module or ""))
    separator = "" if root.endswith(".") else "."
    return tuple(
        f"{root}{separator}{alias.name}" for alias in node.names
    )


def module_scope_imports(path: Path) -> frozenset[str]:
    """The dotted targets a module names at import time.

    Conditional, guarded, and class bodies all count: a `TYPE_CHECKING` block,
    a `try`-wrapped import, and an import inside a class statement are each run
    when the module is loaded, and reading one as deferred would let a binding
    the layering forbids hide inside it.
    """
    pending = list(parsed(path).body)
    found: set[str] = set()
    while pending:
        node = pending.pop()
        if isinstance(node, _IMPORT_NODES):
            found.update(_imported_targets(node))
        elif not isinstance(node, _DEFERRED_SCOPES):
            pending.extend(ast.iter_child_nodes(node))
    return frozenset(found)


def every_import(path: Path) -> frozenset[str]:
    """The dotted targets a module names at any scope."""
    return frozenset(
        target
        for node in ast.walk(parsed(path))
        if isinstance(node, _IMPORT_NODES)
        for target in _imported_targets(node)
    )


def same_name_aliases(path: Path) -> frozenset[str]:
    """The names a module imports under their own spelling.

    `from owner import X as X` is how a module declares an import nothing
    below it reads to be a re-export rather than a leftover: the alias is what
    `F401` reads as deliberate, and what `PLC0414` reads as redundant.
    """
    return frozenset(
        alias.name
        for node in ast.walk(parsed(path))
        if isinstance(node, _IMPORT_NODES)
        for alias in node.names
        if alias.asname == alias.name
    )


def loaded_names(path: Path) -> frozenset[str]:
    """Every bare name the module's own code reads.

    An imported name missing from this set is one the module binds for
    somebody else, which is the reading that costs it to `F401` the moment the
    alias declaring it comes off. A name only assigned to is not a read: the
    import binding it stays unused however many times something rebinds it.
    """
    return frozenset(
        node.id
        for node in ast.walk(parsed(path))
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    )
