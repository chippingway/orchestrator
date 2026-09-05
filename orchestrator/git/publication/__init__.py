# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Branch-publication domain owners.

Branch inspection -- ahead/behind counts, commit-subject reads, and the
subject-shape predicates they feed -- lives in ``probes``; prefix inference
and PR-title selection live in ``titles``; the preconditions a squash is
planned from, the commit count among them, live in ``planning``; the reset,
commit, force-push, and rollback that spend that plan live in ``rewrite``;
what a squash an earlier tick did not finish is owed lives in ``resume``;
the record every one of them hands back lives in ``models``; and ``squash``
composes them into the entry point stage handlers call. Callers import the
owner they need directly, so this initializer binds nothing and importing
``probes`` never drags the rewrite path in.

``resume`` is the one owner with no fresh squash behind it. A rewrite
destroys the evidence of what it was about, so the terms go onto the pinned
comment before the reset and that record is what a later tick reads back --
told apart from a branch with nothing to squash, proved against the objects
it names, and either finished through the same leased publication the
interrupted tick owed or left exactly where it was found. It reaches the size
gate through ``rewrite``'s own call-time hop rather than a second one, which
is why the workflow layer above is named in one place here.

No facade of this domain's own sits beside the package, and nothing above it
republishes these names either, so each answers on the owner that defines it
and a test intercepting one targets that owner -- ``probes`` for base sync's
divergence check, for the ahead/behind reads the documenting, conflicts, and
validating stages take, and for the first-commit subject behind a fresh dev
PR, ``titles`` for the two helpers that PR falls back to, and ``squash`` for
validating's squash. ``orchestrator.branch_publication`` names only the logger
``rewrite`` reports on -- an operator's filter prefix rather than a module path.
"""
