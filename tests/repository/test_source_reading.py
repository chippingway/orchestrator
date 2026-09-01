# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What the architecture checks count as an import, and as a binding.

The readers under these checks decide what the layering and resolver-hook rules
can see at all, so the two edges they turn on are pinned here against a sample
module rather than against the tree: a rule that quietly stops looking is a
green check that forbids nothing.

The first edge is what runs on an import. A class body does -- the statement is
executed where it stands to build the class -- so an import there costs the
loading module exactly what one at the top of the file costs, and reading it as
deferred would leave the layering blind to an upward import parked inside a
class. Only a function body waits for a call, methods included.

The second is what counts as installing a name. A lazy surface can arrive as a
`def`, as an assignment with or without an annotation, as a walrus inside the
signature a definition is written with, as a name a `match` pattern captures,
or as an import renamed to the hook, and a reader that knows one form forbids
one spelling.
"""
from __future__ import annotations

import unittest
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from tests.repository.binding_test_support import module_level_names
from tests.repository.import_test_support import (
    every_import,
    module_scope_imports,
)

# One sample carrying an import in each scope a module has -- the top level, a
# guarded block, a class body, a method, and a plain function -- plus the two
# relative spellings, whose targets have to stay tellable from the absolute
# ones they otherwise resemble.
_SAMPLE_IMPORTS = '''
from typing import TYPE_CHECKING

from orchestrator import config

from . import sibling
from ..agents import runner as relative_runner

if TYPE_CHECKING:
    from orchestrator.github import client


class Composed:
    from orchestrator.agents import runner

    def method(self):
        from orchestrator.workflow.engine import guards
        return guards


def called():
    from orchestrator.runtime import loop
    return loop
'''

# The same for every form a module-level name arrives in: at the top level, out
# of a guarded block and a branch, off a loop and a context manager, out of a
# condition that binds while it tests, off each shape a `match` pattern captures
# through, out of the decorator, defaults, annotations, and base list a
# definition is written with, and through an unpacking nested and starred deeply
# enough that the reader has to walk the target rather than read the top of it.
# The names below a `def` and a `class` -- a local, an attribute, and the
# parameters -- are the counterweight: they belong to the call and to the class,
# and must not be read as the module's.
_SAMPLE_BINDINGS = '''
from orchestrator.workflow.engine import tick as __getattr__

import orchestrator.config as settings


def defined():
    """A name a `def` binds."""
    local = 1
    return local


class Declared:
    """A name a `class` binds."""

    attribute = 2


try:
    from orchestrator.github import client as guarded
except ImportError:
    fallback = None

if settings:
    branched = 3

for iterated in (4, 5):
    pass

with settings as entered:
    pass

if (walrus := settings):
    pass

match settings:
    case [captured, *starred]:
        pass
    case {"key": mapped, **rest_map}:
        pass
    case _ as aliased:
        pass

@Declared((decorator_bound := 11))
def decorated(
    defaulted=(default_bound := 12),
    typed: (annotation_bound := int) = 13,
) -> (return_bound := int):
    """Names a signature binds where the definition is written."""
    signature_local = 14
    return signature_local


class Based((base_bound := Declared), metaclass=(meta_bound := type)):
    """A base list evaluated where the class is written."""

    based_attribute = 15


assigned = 6
annotated: int = 7
unpacked, [__dir__, *rest] = 8, (9, 10)
'''

_IMPORT_TIME = frozenset((
    "orchestrator.config",
    "orchestrator.github.client",
    "orchestrator.agents.runner",
))

_CALL_TIME = frozenset((
    "orchestrator.workflow.engine.guards",
    "orchestrator.runtime.loop",
))

# What the two relative spellings are reported as. The dots are the whole
# point: `agents.runner` without them is a target no rule keyed on the package
# prefix would look at twice.
_RELATIVE = frozenset((".sibling", "..agents.runner"))

_IMPORT_BOUND = frozenset(("__getattr__", "guarded", "settings"))

_SELF_BOUND = frozenset((
    "Based", "Declared", "__dir__", "aliased", "annotated", "annotation_bound",
    "assigned", "base_bound", "branched", "captured", "decorated",
    "decorator_bound", "default_bound", "defined", "entered", "fallback",
    "iterated", "mapped", "meta_bound", "rest", "rest_map", "return_bound",
    "starred", "unpacked", "walrus",
))


@contextmanager
def _sample(source: str) -> Iterator[Path]:
    """The sample source written where a reader can be pointed at it."""
    with TemporaryDirectory() as directory:
        module = Path(directory) / "sample.py"
        module.write_text(source, encoding="utf-8")
        yield module


class ImportScopeTest(unittest.TestCase):
    """An import is read at the scope the interpreter would run it in."""

    def test_module_scope_is_the_import_time_bodies(self) -> None:
        # The top level, the guarded block, and the class body are in; the
        # method and the function are out. The class body is the one a reader
        # is most likely to drop, and dropping it is what would let an upward
        # import park inside a class where the layering never looks.
        every_scope = _IMPORT_TIME | _CALL_TIME
        with _sample(_SAMPLE_IMPORTS) as module:
            reached = module_scope_imports(module)
        self.assertEqual(reached & every_scope, _IMPORT_TIME)

    def test_every_import_reaches_both_scopes(self) -> None:
        every_scope = _IMPORT_TIME | _CALL_TIME
        with _sample(_SAMPLE_IMPORTS) as module:
            reached = every_import(module)
        self.assertEqual(reached & every_scope, every_scope)

    def test_a_relative_import_keeps_its_level(self) -> None:
        # Dropping the level reports `..agents.runner` as `agents.runner`: a
        # module that is not the one imported, outside the package as far as
        # any prefix test can tell, and so waved through by the layering rule
        # the import was pointing the wrong way for.
        with _sample(_SAMPLE_IMPORTS) as module:
            reached = module_scope_imports(module)
        self.assertEqual(reached & _RELATIVE, _RELATIVE)


class BindingFormTest(unittest.TestCase):
    """A name is read whichever statement installed it, wherever it ran."""

    def test_every_binding_form_is_read(self) -> None:
        # Exact equality, so the block bodies are covered from both sides: a
        # name installed inside a `try` or an `if` is the module's and has to
        # appear, and the two under a `def` and a `class` are not and must not.
        with _sample(_SAMPLE_BINDINGS) as module:
            self.assertEqual(
                module_level_names(module), _IMPORT_BOUND | _SELF_BOUND,
            )

    def test_a_name_is_split_by_how_it_arrived(self) -> None:
        # What tells a helper an initializer imported for its own use from a
        # surface it defined and never declared, which is the difference the
        # publisher check reads a namespace with.
        with _sample(_SAMPLE_BINDINGS) as module:
            imported = module_level_names(module, from_imports=True)
            defined = module_level_names(module, from_imports=False)
        self.assertEqual(imported, _IMPORT_BOUND)
        self.assertEqual(defined, _SELF_BOUND)


if __name__ == "__main__":
    unittest.main()
