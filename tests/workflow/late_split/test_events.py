# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What each family may say, and the closed vocabulary a verdict says it in."""
from __future__ import annotations

import unittest

from orchestrator.workflow.late_split import events as _events
from orchestrator.workflow.late_split import formats as _formats
from orchestrator.workflow.late_split.models import (
    LateFailure,
    LateResource,
    LateResourceKind,
    LateResourceState,
    LateVerdict,
)

from tests.workflow.late_split import generation_test_support as _support

_FAMILY = _events.LateEventFamily
_FAMILY_KEY = "family"
_CATEGORY = _events.LateVerdictCategory
_REFUSED = _formats.InvalidLateValue
# A category that arrives as something other than text at all, which the
# mapper has to answer for rather than raise on.
_NOT_TEXT = ("generated_artifacts",)
# What an agent's own words look like when they reach a field: prose, a path,
# and a quoted secret, none of which may become a record.
_PROSE = "rationale: inspect /srv/private/key before splitting"
_MULTILINE = f"{_PROSE}\n"


class FamilySchemaTest(unittest.TestCase):
    """A family carries what it owns, all of it, and nothing else."""

    def test_every_family_builds_with_its_own_fields(self) -> None:
        for event in _support.family_cases():
            with self.subTest(family=str(event.family)):
                self.assertIsInstance(event, _events.LateEvent)

    def test_a_field_the_family_lacks_is_refused(self) -> None:
        # A measurement claiming a verdict, a failure claiming a resource, a
        # cancellation claiming a restart step: each would be a record whose
        # fields describe a step that did not happen.
        unowned = (
            {_FAMILY_KEY: _FAMILY.MEASUREMENT, "verdict": LateVerdict.SINGLE},
            {
                _FAMILY_KEY: _FAMILY.FAILURE,
                "failure": LateFailure.SNAPSHOT_FAILED,
                "resource": _support.SNAPSHOT,
            },
            {
                _FAMILY_KEY: _FAMILY.CANCELLATION,
                "restart_step": _events.LateRestartStep.PENDING,
            },
        )
        for fields in unowned:
            with self.subTest(family=str(fields[_FAMILY_KEY])), self.assertRaises(_REFUSED):
                _events.LateEvent(**fields)

    def test_a_missing_required_field_is_refused(self) -> None:
        for family in (
            _FAMILY.VERDICT, _FAMILY.FAILURE, _FAMILY.SNAPSHOT,
            _FAMILY.CLEANUP, _FAMILY.RESTART,
        ):
            with self.subTest(family=str(family)), self.assertRaises(_REFUSED):
                _events.LateEvent(family=family)

    def test_a_family_that_is_not_a_member_is_refused(self) -> None:
        with self.assertRaises(_REFUSED):
            _events.LateEvent(family="late_measurement")

    def test_the_refusal_names_the_family_and_field(self) -> None:
        with self.assertRaisesRegex(_REFUSED, "late_measurement.*failure"):
            _events.LateEvent(
                family=_FAMILY.MEASUREMENT, failure=LateFailure.RESTART_FAILED,
            )


class VerdictCompanionTest(unittest.TestCase):
    """A category explains a verdict; a child count belongs to one verdict."""

    def test_a_single_verdict_may_explain_itself(self) -> None:
        # The artifact-dominated `single` is the signal the telemetry exists
        # to count, so the verdict that produces it has to be recordable.
        explained = _support.verdict_event(
            verdict=LateVerdict.SINGLE,
            category=_CATEGORY.GENERATED_ARTIFACTS,
        )
        self.assertIs(explained.category, _CATEGORY.GENERATED_ARTIFACTS)

    def test_a_verdict_needs_no_category(self) -> None:
        self.assertIsNone(
            _support.verdict_event(verdict=LateVerdict.SINGLE).category,
        )

    def test_a_question_must_say_what_it_asks_about(self) -> None:
        # The one verdict a category is required of: a question nobody can
        # group is a question nobody can act on.
        with self.assertRaises(_REFUSED):
            _support.verdict_event(verdict=LateVerdict.QUESTION)

    def test_a_child_count_pairs_only_with_a_split(self) -> None:
        with self.assertRaises(_REFUSED):
            _support.verdict_event(
                verdict=LateVerdict.QUESTION,
                category=_CATEGORY.UNSAFE_SPLIT,
                child_count=_support.CHILD_COUNT,
            )
        with self.assertRaises(_REFUSED):
            _support.verdict_event(verdict=LateVerdict.SPLIT)


class DetailTypeTest(unittest.TestCase):
    """A member is required where a member is declared, not a lookalike."""

    def test_a_lookalike_string_is_not_a_member(self) -> None:
        # `StrEnum` members compare equal to their own spelling, so a raw
        # string satisfies every comparison the schema makes -- and would be
        # written verbatim. Only the member itself is accepted.
        lookalikes = (
            {"verdict": "single"},
            {"verdict": LateVerdict.QUESTION, "category": "generated_artifacts"},
        )
        for fields in lookalikes:
            with self.subTest(fields=sorted(fields)), self.assertRaises(_REFUSED):
                _support.verdict_event(**fields)

    def test_prose_cannot_enter_through_a_typed_field(self) -> None:
        # The adversarial case the closed vocabulary exists for: an
        # adjudication's rationale, naming a path, offered as a category.
        with self.assertRaises(_REFUSED):
            _support.verdict_event(
                verdict=LateVerdict.QUESTION, category=_PROSE,
            )

    def test_a_count_must_be_a_real_count(self) -> None:
        for counted in (True, 2.5, "4", -1):
            with self.subTest(counted=counted), self.assertRaises(_REFUSED):
                _support.verdict_event(
                    verdict=LateVerdict.SPLIT, child_count=counted,
                )

    def test_a_resource_is_checked_through(self) -> None:
        # The kind is what a record reports, so a resource built with a string
        # for it would put that string in the payload under the field named
        # for the vocabulary.
        untyped = (
            LateResource(kind=_PROSE, target="x"),
            LateResource(
                kind=LateResourceKind.BRANCH, target="x", resource_state="gone",
            ),
            LateResource(kind=LateResourceKind.BRANCH, target=""),
            LateResource(kind=LateResourceKind.BRANCH, target=_MULTILINE),
        )
        for resource in untyped:
            with self.subTest(kind=str(resource.kind)), self.assertRaises(_REFUSED):
                _support.cleanup_event(resource)

    def test_a_typed_resource_is_accepted(self) -> None:
        recorded = _support.cleanup_event(
            LateResource(
                kind=LateResourceKind.BRANCH,
                target="orchestrator/issue-7",
                resource_state=LateResourceState.FAILED,
            ),
        )
        self.assertIs(recorded.resource.kind, LateResourceKind.BRANCH)


class VerdictCategoryTest(unittest.TestCase):
    """A category is chosen from the vocabulary, never written into it."""

    def test_a_known_category_maps_to_its_member(self) -> None:
        known = {
            "generated_artifacts": _CATEGORY.GENERATED_ARTIFACTS,
            "Generated Artifacts": _CATEGORY.GENERATED_ARTIFACTS,
            " UNSAFE_SPLIT ": _CATEGORY.UNSAFE_SPLIT,
        }
        for asked, member in known.items():
            with self.subTest(asked=asked):
                self.assertIs(_events.verdict_category(asked), member)

    def test_agent_prose_never_becomes_a_category(self) -> None:
        # The reason the vocabulary is closed: an adjudication's rationale
        # names files and quotes its own reasoning, and none of that may reach
        # a sink. Everything unrecognized groups under one member instead.
        prose = (
            "Generated Artifacts?! docs/architecture.md and "
            "orchestrator/cli.py look wrong to commit",
            _PROSE,
            "",
            None,
            _NOT_TEXT,
        )
        for asked in prose:
            with self.subTest(asked=asked):
                self.assertIs(_events.verdict_category(asked), _CATEGORY.UNKNOWN)

    def test_the_mapper_always_answers(self) -> None:
        # A `question` verdict requires a category, so the mapper answering
        # None would leave the emitter with a record it cannot legally build.
        self.assertIsNotNone(_events.verdict_category(None))


if __name__ == "__main__":
    unittest.main()
