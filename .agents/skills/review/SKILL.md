---
name: review
description: >-
  Review checklist for reviewer agents on agent-orchestrator PRs. Use when
  evaluating a developer-produced branch before approval or change-requests.
---

# Reviewer skill — agent-orchestrator

## CI / lint

Reject (or request fixes) if any of these are red:

- `ruff check orchestrator tests`. Common offenders to look for explicitly:
  - **F401** — unused import on a package initializer. If the import is intended as a re-export, it must
    be aliased `from X import Y as Y` or listed in that initializer's `__all__`. A bare import will not
    survive ruff.
  - **F541** — f-strings without placeholders, typically in newly-added test files.
  - **F841** — unused local in tests.
  - **E402** — import after non-import code.
- `uv run flake8 orchestrator tests --select=WPS`. All WPS naming, complexity, consistency, bug-prevention,
  refactoring, and OOP findings are rejection criteria.
- `git diff --check origin/main...HEAD` — trailing whitespace and blank lines at EOF. Check it even
  if everything else looks clean.
- Full `pytest` run is referenced in the PR description and passes end-to-end. Reject "known failure"
  hand-waves; if the PR claims a baseline failure, the description must include a reproduction on
  `origin/main` at the branch point. Otherwise the developer must fix it.
- Every source file the PR adds (`*.py`, `*.sh`, `pyproject.toml`) opens with the `# Copyright 2026 Geser Dugarov` /
  `# SPDX-License-Identifier: Apache-2.0` header pair.

## Behavior preservation

For any refactor:

- Workflow labels, pinned-state JSON keys, comment marker text, watermark fields, and event-emission
  shape must match `main` exactly. Issues already in flight depend on these — a rename is a migration,
  not a refactor.
- Spot-check that moved code still routes through the same auth / fetch / push / retry helpers. A
  refactor is not allowed to silently change side effects.
- Squash-on-approval, the in_review HITL ready-ping gates (mergeable + approved + no standing
  CHANGES_REQUESTED), retry budgets, and stale-session detection are easy to break by accident during
  a move; verify their call paths survive intact.

## Module boundaries

`orchestrator/workflow/__init__.py` is a narrow explicit API — the label vocabularies, the transition guard
and the predicate under it, the illegal-write exception, and the per-repo `tick`. Confirm:

- Nothing new is published there. A helper another module reaches for is imported from the owner that
  defines it, and a stage-private helper (used inside one stage module — `_bump_in_review_watermarks`,
  `_seed_legacy_in_review_watermarks`, `_emit_conflict_round_incremented`, etc.) stays private to it.
- The initializer binds no engine or stage module at import. The GitHub and git layers import
  `workflow/state.py` beside it, so an engine import there is an import cycle, not a convenience.
- Stage modules import the owner they borrow from at module scope and call through that alias; flag any
  reintroduced call-time hop through the package initializer.
- Test patches target the module the call site names. Flag a test that patches anything else — including
  the workflow package — since a mock left there intercepts nothing.

## Test economy and assertion quality

- Identify newly added tests that duplicate existing tests or each other; request merging into
  `pytest.mark.parametrize` cases or a small named loop when the only difference is fixture values or
  branch selection.
- Verify each added test fails against the old behavior or directly protects a changed contract.
- For resource-usage fixes (over-fetching, redundant API calls, retained state), reject tests that
  only assert the final result; require at least one assertion at the helper/producer level.
- Prefer fewer tests with clear distinct coverage over many narrowly overlapping regression tests.
- Check placement: tests mirror the runtime layout, so a module under `orchestrator/<package>/` is covered by
  `tests/<package>/` and stage handlers by `tests/workflow/stages/<stage>/`. Flag a new omnibus module added beside
  an existing per-behavior split, a test parked away from the owner it exercises, and a stage reaching into a
  sibling stage's `*_test_support.py` for fixtures.

## Documentation drift

After any handler or helper move, grep the PR for stale pointers and request fixes in:

- `docs/architecture.md` — the module-by-module inventory lives here and nowhere else
- `docs/state-machine.md`
- `docs/workflow.md`
- module docstrings at the top of the owners the symbol moved between, and of the package initializers
  above them that describe where a name answers

`AGENTS.md` (and its `CLAUDE.md` symlink) is deliberately off that list, and the inverse is what to flag: it is
loaded into every agent session and carries no module, owner, or test inventory. Reject a PR that answers a routine
symbol or module move by editing it, or that grows an inventory back into it. It changes only when repository-wide
agent instructions, safety rules, or documentation routing change.

Treat blanket statements about what a package publishes — "every helper is re-exported", "the hub answers for
these names" — with suspicion; verify literally against the code, since an attribute that no longer exists raises
`AttributeError` rather than reading as stale prose.

## Comment hygiene

- Flag diff-relative comments — "previously", "the old retry cap", "instead of a dict", "now uses" —
  in code and test docstrings alike. A comment must read correctly to someone who never saw the
  change; the before/after story belongs in the commit message or PR description.
- Flag comments that paraphrase an already-readable line or the assert below them instead of stating
  a why (invariant, non-local consumer, prevented failure). Ask for the reason or for deletion. Do
  not flag plain-language summaries above genuinely dense code (tricky offset math, multi-step
  comprehension chains) — a comment that is faster to understand than the code it heads earns its
  place.

## `plans/` references

- `plans/` holds human working notes, not spec. Flag any code, comment, docstring, or test that cites
  a `plans/` document — or a numbered "Proposal N" from one — as authoritative; the change must stand
  on its own once that note is revised or deleted. Ask for the reference to be reworded to describe the
  behavior directly.
- A developer should not edit or remove files under `plans/` unless the issue explicitly asked. Flag
  unrequested `plans/` changes.

## Commit hygiene

- Conventional Commits: `<type>: <subject>` only. Reject any commit with a body, a `Co-Authored-By`
  trailer, or a non-imperative subject. Type must be one of `feat`, `fix`, `chore`, `docs`,
  `refactor`, `test`.

## Out of scope — push back

- Dependencies outside the issue's stated scope.
- Reformatting of files outside the change's blast radius.
- Abstractions or generality added for hypothetical future features. The issue's stated scope is the source of truth.
