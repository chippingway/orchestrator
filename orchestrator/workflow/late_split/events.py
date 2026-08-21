# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What one late event is, and what its family is allowed to say.

Seven families describe a late generation's whole life -- what a candidate
measured, what the adjudication decided, which typed step failed, what happened
to a snapshot, what a cleanup reconciled, that the owner was cancelled, and
that a restart was taken. Each carries the generation's own correlation, plus
only the detail its family owns, and the record enforces that rather than
trusting the emitter: `_FAMILY_FIELDS` says which fields a family requires and
which it may carry, and anything else raises `InvalidLateValue` where the event
is built. What that refusal says is bounded too -- it names the family only
when the family is a member, because the message is read by a log and a value
refused from both sinks may not arrive there instead. A measurement that
arrives claiming a verdict, or a verdict with no verdict on it, is a bug in an
emitter -- refusing it at construction is what keeps a record that means
nothing out of both sinks and out of every analysis over them.

The type of each detail is checked, not merely annotated. A `StrEnum` member
and the string that spells it compare equal, so `verdict="question"` would
satisfy every comparison here and be written verbatim -- and so would
`category="rationale: inspect /srv/private/key"`. Only an actual member is
accepted, which is what makes the closed vocabularies closed and leaves prose
no field to travel in. `check` re-runs the whole contract, so the record
builder can ask an event it did not construct.

The verdict's two companions are the same rule one level down, and they are
not symmetric because the questions they answer are not. A child count
describes a split and only a split. A category explains where an adjudication
landed: it is required of a `question`, because a question that cannot say
what it is asking about is not analyzable, and it is optional on the other two
-- which is what makes the artifact-dominated `single` verdict a thing
telemetry can count rather than a claim nobody can check.

`category` is a closed vocabulary, not a label an agent writes. The late
decomposer's answer is mapped onto these members by `verdict_category`, which
answers `UNKNOWN` for everything it does not recognize, so an adjudication's
rationale -- the sentences, the file names in them -- has no path into a record
at all. That is deliberate: the vocabulary can be widened here, in a review,
and cannot be widened by what an agent happened to write.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Optional

from orchestrator.workflow.late_split import formats as _formats
from orchestrator.workflow.late_split.models import (
    MAX_RESOURCE_TARGET,
    LateFailure,
    LateResource,
    LateResourceKind,
    LateResourceState,
    LateVerdict,
)

_REQUIRES = "requires"
_NOT_CARRIED = "does not carry"
_NOT_TYPED = "was not given a member for"

_FAMILY = "family"
_VERDICT = "verdict"
_CATEGORY = "category"
_CHILD_COUNT = "child_count"
_FAILURE = "failure"
_RESOURCE = "resource"
_RESTART_STEP = "restart_step"

# Every detail field a family can own, in the order a refusal reports them.
_DETAIL_FIELDS = (
    _VERDICT,
    _CATEGORY,
    _CHILD_COUNT,
    _FAILURE,
    _RESOURCE,
    _RESTART_STEP,
)


class LateEventFamily(StrEnum):
    """The event kind each family is written to both sinks under."""

    MEASUREMENT = "late_measurement"
    VERDICT = "late_verdict"
    FAILURE = "late_failure"
    SNAPSHOT = "late_snapshot"
    CLEANUP = "late_cleanup"
    CANCELLATION = "late_cancellation"
    RESTART = "late_restart"


class LateVerdictCategory(StrEnum):
    """What an adjudication says about where it landed.

    Closed on purpose: these are the answers telemetry can group by -- how
    often a repository's oversized candidates turn out to be dominated by
    generated artifacts, and what the questions humans are asked are about --
    and a category outside them is `UNKNOWN` rather than a new label an agent
    introduced into the record.
    """

    GENERATED_ARTIFACTS = "generated_artifacts"
    SCOPE_AMBIGUOUS = "scope_ambiguous"
    UNSAFE_SPLIT = "unsafe_split"
    LINEAGE_BOUND = "lineage_bound"
    UNKNOWN = "unknown"


class LateRestartStep(StrEnum):
    """Which half of the two-phase restart a record describes."""

    PENDING = "pending"
    RECONCILED = "reconciled"


# Per family: what it requires, and what it may also carry. A family with
# neither says everything about its generation and nothing of its own.
_FAMILY_FIELDS = MappingProxyType({
    LateEventFamily.MEASUREMENT: ((), ()),
    LateEventFamily.VERDICT: ((_VERDICT,), (_CATEGORY, _CHILD_COUNT)),
    LateEventFamily.FAILURE: ((_FAILURE,), ()),
    LateEventFamily.SNAPSHOT: ((_RESOURCE,), ()),
    LateEventFamily.CLEANUP: ((_RESOURCE,), ()),
    LateEventFamily.CANCELLATION: ((), ()),
    LateEventFamily.RESTART: ((_RESTART_STEP,), ()),
})

# What each detail field has to be a member (or a real count) of.
_DETAIL_TYPES = MappingProxyType({
    _VERDICT: LateVerdict,
    _CATEGORY: LateVerdictCategory,
    _CHILD_COUNT: int,
    _FAILURE: LateFailure,
    _RESOURCE: LateResource,
    _RESTART_STEP: LateRestartStep,
})

# The verdict a child count belongs to and only to, and the one a category is
# required of. Nothing forbids a category elsewhere: a `single` verdict
# explaining itself is the artifact-dominated signal the telemetry exists for.
_COUNTED_VERDICT = LateVerdict.SPLIT

_CATEGORIZED_VERDICT = LateVerdict.QUESTION


@dataclass(frozen=True)
class LateEvent:
    """One family, plus the little that family adds to its generation.

    Everything else a record carries is read off the generation, so an emitter
    cannot describe a step in terms the pinned state does not agree with.
    """

    family: LateEventFamily
    verdict: Optional[LateVerdict] = None
    category: Optional[LateVerdictCategory] = None
    child_count: Optional[int] = None
    failure: Optional[LateFailure] = None
    resource: Optional[LateResource] = None
    restart_step: Optional[LateRestartStep] = None

    def __post_init__(self) -> None:
        self.check()

    def check(self) -> None:
        """Refuse an event whose fields do not describe its family.

        Published so the record builder can ask the same question of an event
        it did not construct: the boundary a payload crosses is the last place
        anything can still refuse, and it does not get to assume the object
        reaching it came through this constructor.
        """
        self._check_family()
        self._check_verdict()
        self._check_types()

    def _check_family(self) -> None:
        """Refuse a field this family does not own, or one it is missing."""
        if not isinstance(self.family, LateEventFamily):
            self._refuse({_FAMILY}, _NOT_TYPED)
        required, optional = _FAMILY_FIELDS[self.family]
        supplied = self._supplied_fields()
        self._refuse(supplied - set(required) - set(optional), _NOT_CARRIED)
        self._refuse(set(required) - supplied, _REQUIRES)

    def _check_verdict(self) -> None:
        """Refuse a companion field paired with the wrong verdict.

        A child count is a split's and nobody else's, in both directions. A
        category is required of a question and allowed of any verdict, because
        why a candidate stayed one change is exactly as worth counting as why
        a human was asked.
        """
        supplied = self._supplied_fields()
        if self.verdict == _COUNTED_VERDICT:
            self._refuse({_CHILD_COUNT} - supplied, _REQUIRES)
        else:
            self._refuse({_CHILD_COUNT} & supplied, _NOT_CARRIED)
        if self.verdict == _CATEGORIZED_VERDICT:
            self._refuse({_CATEGORY} - supplied, _REQUIRES)

    def _check_types(self) -> None:
        """Refuse a detail that is a lookalike rather than a member."""
        for name, wanted in _DETAIL_TYPES.items():
            given = getattr(self, name)
            if given is not None and not _is_typed(given, wanted):
                self._refuse({name}, _NOT_TYPED)

    def _supplied_fields(self) -> set[str]:
        """The detail fields this event actually carries."""
        return {
            name for name in _DETAIL_FIELDS
            if getattr(self, name) is not None
        }

    def _refuse(self, names: set[str], reason: str) -> None:
        """Raise for a non-empty set of fields, naming the family and them.

        The family is named only when it IS one. An event refused for having
        a family that is not a member is refused over exactly the value that
        must not be repeated -- the message ends up in a log, and prose
        offered as a family would reach it there having been kept out of both
        sinks. The field names beside it are this module's own literals.
        """
        if names:
            listed = ", ".join(sorted(names))
            named = self.family
            if not isinstance(named, LateEventFamily):
                named = _formats.UNNAMED
            raise _formats.InvalidLateValue(f"{named!s} {reason}: {listed}")


def verdict_category(asked: Optional[str]) -> LateVerdictCategory:
    """Map a parsed adjudication category onto the closed vocabulary.

    Never answers None, so the emitter always has the category a `question`
    verdict requires, and never answers anything the vocabulary does not
    already contain, so what the agent wrote cannot become the record. A
    spelling this binary does not know -- an agent's own words, a category a
    newer prompt introduced -- is `UNKNOWN`, which groups those together
    visibly instead of silently widening the field.
    """
    try:
        recognized = asked.strip().lower().replace(" ", "_")
    except AttributeError:
        return LateVerdictCategory.UNKNOWN
    try:
        return LateVerdictCategory(recognized)
    except ValueError:
        return LateVerdictCategory.UNKNOWN


def _is_typed(given: Any, wanted: type) -> bool:
    """Whether one detail is the member, count, or resource it claims to be.

    A resource is checked through to its own fields, because the kind is what
    a record reports: a `LateResource` built with a string for its kind would
    otherwise put that string in the payload under the field named for the
    vocabulary.
    """
    if wanted is int:
        return _formats.whole_number(given) and given >= 0
    if not isinstance(given, wanted):
        return False
    if wanted is not LateResource:
        return True
    return (
        isinstance(given.kind, LateResourceKind)
        and isinstance(given.resource_state, LateResourceState)
        and _formats.is_bounded_text(given.target, MAX_RESOURCE_TARGET)
    )
