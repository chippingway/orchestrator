# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""One fenced block at the end of a LATE reply, or a reason it is not one.

An additive mode beside the initial parser, on its own fence and with its own
decision vocabulary, so that what a missing or malformed initial manifest
means is exactly what it always meant. The two fences cannot be mistaken for
each other -- `orchestrator-manifest` is not a substring of
`orchestrator-late-manifest` and the patterns are anchored on the whole name
-- so an initial reply cannot be read as a late one or the other way round.

The envelope is the same and is asked once, on the owner beside this one: one
block, and nothing after it. What differs is what a reply with NO block means.
The initial contract treats it as the decomposer asking a question, because
there its question has nowhere else to go; the late contract gives a question
its own structured decision, complete with the category telemetry counts, so a
reply with no block is a protocol failure and is parked for a human rather
than read as an answer.

`split` is validated by the initial mode's own split validator rather than by
a second copy of it. The child cap, the shape of a child, and the acyclicity
of the graph they declare are properties of a manifest that is about to become
GitHub issues, and that is the same manifest either mode produces -- so a rule
tightened there tightens here, and the number the late prompt states is still
the number the reply is judged against.

What this owner does NOT decide is whether a `split` is allowed at all. The
lineage bound is the record's invariant and is enforced where the generation
is: a structurally perfect split proposed at the bound parses cleanly here and
is refused one layer up, which is what keeps "the agent got the format wrong"
apart from "the agent proposed something the lineage forbids".
"""
from __future__ import annotations

import re
from typing import Any, Tuple

from orchestrator.workflow.late_split import events as _events
from orchestrator.workflow.late_split.events import LateVerdictCategory
from orchestrator.workflow.late_split.models import LateVerdict
from orchestrator.workflow.stages.decomposition import manifest as _manifest
from orchestrator.workflow.stages.decomposition import validation as _validation
from orchestrator.workflow.stages.decomposition.late_models import (
    _LateAdjudication,
)

_LATE_BLOCK = "orchestrator-late-manifest"

_LATE_MANIFEST_RE = re.compile(
    r"```orchestrator-late-manifest\s*\n(.*?)\n```",
    re.DOTALL,
)

_DECISION = "decision"
_CATEGORY = "category"
_QUESTION = "question"

_SINGLE_DECISION = "single"
_SPLIT_DECISION = "split"

_DECISIONS = (_SINGLE_DECISION, _SPLIT_DECISION, _QUESTION)

_NO_BLOCK = (
    f"expected one {_LATE_BLOCK} block; the late contract has no outcome "
    "that is prose"
)

_BAD_DECISION = "decision must be 'single', 'split', or 'question'"

_NO_QUESTION = "question decision requires a non-empty question"


def _parse_late_reply(
    last_message: str,
) -> Tuple[_LateAdjudication | None, str | None]:
    """Parse a fenced `orchestrator-late-manifest` block.

    Returns `(adjudication, None)` for a reply that decided something, and
    `(None, error)` -- a short human-readable reason, used in the park
    message -- for every reply that did not. There is deliberately no third
    answer: unlike the initial mode, a late reply with no block has not asked
    a question, it has failed to answer one.
    """
    payload, envelope_error = _manifest._fenced_payload(
        last_message, _LATE_MANIFEST_RE, _LATE_BLOCK,
    )
    if payload is None:
        return None, envelope_error or _NO_BLOCK
    late_manifest, decode_error = _manifest._decode_manifest(payload)
    if late_manifest is None:
        return None, decode_error
    return _adjudication(late_manifest)


def _adjudication(
    late_manifest: dict,
) -> Tuple[_LateAdjudication | None, str | None]:
    """Route one decoded late manifest onto the verdict it declares."""
    decision = late_manifest.get(_DECISION)
    if decision not in _DECISIONS:
        return None, _BAD_DECISION
    if decision == _SPLIT_DECISION:
        return _split_adjudication(late_manifest)
    if decision == _QUESTION:
        return _question_adjudication(late_manifest)
    return _LateAdjudication(
        verdict=LateVerdict.SINGLE,
        category=_category(late_manifest, required=False),
        rationale=_text(late_manifest, "rationale"),
    ), None


def _split_adjudication(
    late_manifest: dict,
) -> Tuple[_LateAdjudication | None, str | None]:
    """Validate a late split against the initial mode's own split rules."""
    split_error = _validation._split_manifest_error(late_manifest)
    if split_error is not None:
        return None, split_error
    return _LateAdjudication(
        verdict=LateVerdict.SPLIT,
        category=_category(late_manifest, required=False),
        rationale=_text(late_manifest, "rationale"),
        children=tuple(late_manifest.get("children") or ()),
    ), None


def _question_adjudication(
    late_manifest: dict,
) -> Tuple[_LateAdjudication | None, str | None]:
    """Require a question to say what it is asking before it may park one."""
    asked = _text(late_manifest, _QUESTION)
    if not asked:
        return None, _NO_QUESTION
    return _LateAdjudication(
        verdict=LateVerdict.QUESTION,
        category=_category(late_manifest, required=True),
        question=asked,
    ), None


def _category(
    late_manifest: dict, *, required: bool,
) -> LateVerdictCategory | None:
    """Map a declared category onto the closed vocabulary, or leave it out.

    Mapped rather than trusted, so an agent's own spelling records as
    `unknown` and never widens the field. Absent is a real answer on the two
    verdicts that do not require one, which is what keeps `unknown` meaning
    "a category this binary does not know" rather than "no category given".
    """
    asked = late_manifest.get(_CATEGORY)
    if asked is None and not required:
        return None
    return _events.verdict_category(asked)


def _text(late_manifest: dict, field_name: str) -> str:
    """Return one stripped optional text field, or an empty string."""
    written: Any = late_manifest.get(field_name)
    return written.strip() if isinstance(written, str) else ""
