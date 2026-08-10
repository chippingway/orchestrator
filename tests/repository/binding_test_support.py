# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Static reader for the names a module binds in its own namespace.

Reading the source rather than the imported module is what lets the check
answer for every file in the tree, including the ones an in-process import
would charge the suite for.

Module scope here is what the interpreter writes into the module namespace on
the import, which is one statement wider than the import reader's and one
narrower. Wider: a name installed inside an `if`, a `try`, or any other
module-level block belongs to the module, so the walk follows those bodies, and
so does the part of a `def` or `class` that is evaluated where it is written --
a decorator, a default, an annotation, a base list. Narrower: what a class body
or a call body binds belongs to the class or the call, so the walk stops at
both.

Which form installed the name does not matter either. A dynamic surface can
arrive as `def __getattr__`, as an assignment -- annotated, augmented, walrus,
or one tuple unpacking that installs both halves at once -- as a `for` or
`with` target, as a name a `match` pattern captures, or as a resolver imported
under that name, so a check that reads one of those forms is one spelling away
from missing the thing it exists to forbid.
"""
from __future__ import annotations

import ast
from pathlib import Path
from types import MappingProxyType

from tests.repository.layout_test_support import parsed

_DEFINITION_NODES = (ast.AsyncFunctionDef, ast.ClassDef, ast.FunctionDef)

_IMPORT_NODES = (ast.Import, ast.ImportFrom)

# The one field of a definition that runs on the call rather than where the
# definition is written. Everything else a `def` or `class` carries -- the
# decorators, the argument defaults and annotations, the return annotation, the
# base list and its keywords -- is evaluated in the namespace around it.
_DEFERRED_FIELD = "body"

# The writes that carry one target: an annotated or augmented assignment, a
# loop, and an assignment expression. Each binds its target in the namespace
# it runs in, exactly as a plain assignment does -- a walrus in a module-level
# condition or comprehension included, since that one binds outside the
# comprehension that spells it.
_SINGLE_TARGET_NODES = (
    ast.AnnAssign, ast.AsyncFor, ast.AugAssign, ast.For, ast.NamedExpr,
)

_CONTEXT_NODES = (ast.AsyncWith, ast.With)

# Where a match pattern keeps the name it captures. A sequence element, a
# mapping value, a class keyword, and an `as` alias all bind through `MatchAs`
# or `MatchStar`; a mapping's `**rest` binds on the mapping pattern itself.
_CAPTURE_FIELDS = MappingProxyType({
    ast.MatchAs: "name",
    ast.MatchMapping: "rest",
    ast.MatchStar: "name",
})


def _write_targets(node: ast.stmt) -> tuple[ast.expr, ...]:
    """What one write lands its value in.

    A loop, a context manager, and an assignment expression each write their
    target in the namespace they run in, exactly as an assignment does, so all
    of them are read the same way.
    """
    if isinstance(node, ast.Assign):
        return tuple(node.targets)
    if isinstance(node, _SINGLE_TARGET_NODES):
        return (node.target,)
    if isinstance(node, _CONTEXT_NODES):
        return tuple(
            entry.optional_vars
            for entry in node.items
            if entry.optional_vars
        )
    return ()


def _written_names(node: ast.stmt) -> tuple[str, ...]:
    """Every name one write statement binds.

    Unpacking is followed through: `__getattr__, __dir__ = resolve, listing`
    installs both halves of a lazy surface in one statement, and reading only
    the plain-name form would leave that spelling unseen.
    """
    pending = list(_write_targets(node))
    written = []
    while pending:
        target = pending.pop()
        if isinstance(target, ast.Name):
            written.append(target.id)
        elif isinstance(target, ast.Starred):
            pending.append(target.value)
        elif isinstance(target, (ast.List, ast.Tuple)):
            pending.extend(target.elts)
    return tuple(written)


def _bound_names(node: ast.stmt) -> tuple[str, ...]:
    """The names one statement or pattern binds in the namespace around it."""
    if isinstance(node, _DEFINITION_NODES):
        return (node.name,)
    if isinstance(node, _IMPORT_NODES):
        return tuple(
            alias.asname or alias.name.partition(".")[0]
            for alias in node.names
        )
    capture_field = _CAPTURE_FIELDS.get(type(node))
    if capture_field is not None:
        captured = getattr(node, capture_field)
        return (captured,) if captured else ()
    return _written_names(node)


def _outside_the_body(node: ast.stmt) -> tuple[ast.AST, ...]:
    """The parts of a definition evaluated where the definition is written.

    A default, a decorator, an annotation, and a base list all run in the
    namespace around the `def` or `class`, so a walrus in one installs a
    module-level name from what looks like a signature.
    """
    signature: list[ast.AST] = []
    for field, carried in ast.iter_fields(node):
        if field == _DEFERRED_FIELD:
            continue
        held = carried if isinstance(carried, list) else [carried]
        signature.extend(
            child for child in held if isinstance(child, ast.AST)
        )
    return tuple(signature)


def module_level_names(
    path: Path, *, from_imports: bool | None = None,
) -> frozenset[str]:
    """The names a module binds in its own namespace at import.

    Every block the interpreter runs on the way is followed -- a `try` and its
    handlers, an `if` and its branches, a loop, a `with` -- because a name
    installed in one of them lands in the module namespace just as a top-level
    statement's does, and a fallback surface behind an `ImportError` handler is
    exactly where one would be installed unseen. A `def` and a `class` are
    followed as far as their signature, and stop at their body: what the body
    binds belongs to the call or the class.

    `from_imports` selects by how a name arrived: `True` for the ones an import
    statement brought in, `False` for the ones the module writes itself, and
    the default `None` for both. The split is what tells a helper a publisher
    imported for its own use from a surface it defined and never declared.
    """
    pending: list[ast.AST] = list(parsed(path).body)
    found: set[str] = set()
    while pending:
        node = pending.pop()
        selected = (
            from_imports is None
            or isinstance(node, _IMPORT_NODES) is from_imports
        )
        if selected:
            found.update(_bound_names(node))
        if isinstance(node, _DEFINITION_NODES):
            pending.extend(_outside_the_body(node))
        else:
            pending.extend(ast.iter_child_nodes(node))
    return frozenset(found)
