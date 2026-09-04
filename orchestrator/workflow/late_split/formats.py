# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a late value has to look like before anything reads or records it.

Three questions the domain asks of a raw value, in the one place that answers
them, because both ends need the same answer: the reader that types a pinned
field, and the gate that decides whether a record may be written. A rule
spelled twice would let the pinned comment accept what the sink refuses, or
the sink emit what the state could never have held.

`bounded_line` is the same rule read the other way round, and it is here for
that reason rather than beside any one emitter: it shapes a raw diagnostic
into exactly what `is_bounded_text` would accept, so the one field this domain
records free text in is bounded by the predicate that guards it instead of by
a caller's own idea of the limit.

`whole_number` is deliberately narrower than `int(...)`. A bool is an `int` in
Python, `2.9` truncates to 2, a float can be infinity, and a numeric string
converts -- and every one of those, taken as a count, is a number nothing
wrote: a cycle identity of 1 minted out of `True`, a lineage depth of 2 out of
2.9, an `OverflowError` out of a JSON number decoded as infinity. Only a real
integer is a count here, and everything else is absent.

`InvalidLateValue` is here for the same reason the predicates are: an owner
that decides a value is unusable has to say so in a way every other owner
recognizes, and this is the module all of them already name. It is what the
event contract, the pinned transforms, and the record boundary all raise, so a
caller catches one exception rather than one per layer.

`is_hex_of` is what keeps a commit field a commit and a fingerprint a
fingerprint. The SHAs a late generation freezes are the evidence a
reconciliation acts on and the fields an analysis joins on, so a value that is
not spelled like the thing it claims to be is not one -- which is also what
stops prose reaching a sink through a field named for a SHA.

The lengths are exact, and each field says which it wants, because "hex of
some length" is not a contract. A frozen commit is a whole object id, in
either hash git writes; a local fingerprint is a whole SHA-256 digest. An
abbreviation is not a commit this domain froze -- nothing here ever writes
one, so one in a pinned comment came from somewhere else and cannot be
reconciled against -- and a truncated digest is not a hash of anything, so
comparing content against it would answer "changed" forever.
"""
from __future__ import annotations

import re
from typing import Any

# A whole git object id, in either hash git writes: SHA-1 or SHA-256. Nothing
# here ever records an abbreviation, so nothing here reads one back.
COMMIT_LENGTHS = frozenset((40, 64))

# A whole SHA-256 digest, which is what the local fingerprints are.
DIGEST_LENGTHS = frozenset((64,))

_HEX_ONLY = re.compile(r"\A[0-9a-f]+\Z")


# What a refusal names in place of a value it could not vouch for. A refusal
# is raised about values that just failed to prove themselves, so the one
# thing it may not do is repeat them: an exception message is read by a log,
# and a log is the same surface one step over from the sinks the refusal was
# protecting.
UNNAMED = "?"


class InvalidLateValue(Exception):
    """A late value is not something this domain may hold, write, or record."""


def whole_number(given: Any) -> bool:
    """Whether a value is a real integer -- not a bool, float, or string."""
    return isinstance(given, int) and not isinstance(given, bool)


def is_hex_of(given: Any, lengths: frozenset) -> bool:
    """Whether a value is hex of exactly one of the lengths asked for."""
    if not isinstance(given, str) or len(given) not in lengths:
        return False
    return _HEX_ONLY.match(given) is not None


def is_bounded_text(given: Any, limit: int) -> bool:
    """Whether a value is one bounded, single-line, untrimmed-free string.

    What a resource target has to satisfy to be usable as an identifier: it is
    never recorded, but it is digested into one, and a value carrying line
    breaks or unbounded length is not a ref, a branch, or an issue number. It
    is what a recorded diagnostic has to satisfy too, where "one line" is the
    whole of the bound rather than half of it.

    Single-line is asked as `splitlines` rather than as a search for one
    newline character, because the readers on the far side of these fields
    break on more than that one: a lone carriage return, a form feed, and the
    two Unicode separators each start a new line in a terminal, an editor, a
    `jq` rendering, and a Postgres value read back. A value that displays as
    two lines is two lines, whichever character made it so, so the answer here
    is the same one the reducer beside this takes.
    """
    if not isinstance(given, str) or not given:
        return False
    if len(given) > limit or given != given.strip():
        return False
    return len(given.splitlines()) == 1


def bounded_line(given: Any, limit: int) -> str | None:
    """Return what one free-text diagnostic may be recorded as, or None.

    The reducer `is_bounded_text` is the predicate for. What a failed step
    wrote is the only account of WHY it failed, and it arrives as whatever the
    process that wrote it produced: the first line that says anything is the
    diagnostic, and what follows it is advice, hints, and the remote's banner.
    A line past the limit is cut rather than dropped, because the head of
    "fatal: could not read Username" locates the fault and nothing at all
    locates nothing.

    None where there is nothing to carry -- an absent value, one that is not
    text, and a value whose every line is blank -- so an emitter never offers
    a field it has no diagnostic for.

    What it answers with always satisfies `is_bounded_text`, which is the
    point of the two sitting together: `splitlines` breaks on every separator
    that predicate refuses, so a line taken from it carries none of them.
    """
    if not isinstance(given, str):
        return None
    for line in given.splitlines():
        reported = line.strip()
        if reported:
            return reported[:limit].rstrip()
    return None


def optional_count(given: Any) -> bool:
    """Whether a value is an absent or a real, non-negative count."""
    if given is None:
        return True
    return whole_number(given) and given >= 0


def optional_commit_id(given: Any) -> bool:
    """Whether a value is an unset or a whole git object id."""
    if given is None or given == "":
        return True
    return is_hex_of(given, COMMIT_LENGTHS)
