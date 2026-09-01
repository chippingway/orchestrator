# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Submission binding and normalization owned by the scheduler models."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from orchestrator.scheduler import models

_REPO_SLUG = "owner/repo"
_ISSUE_NUMBER = 7
_DEFAULT_PER_REPO_CAP = 3
_RAISED_CAP = 5
_REJECTED_TYPED_CALLS = (
    ((), {"family": True}, "keyword field 'family'"),
    (("extra",), {}, "additional positional fields"),
)
_COERCED_CAPS = (("2", 2), (0, 1), (-4, 1))


def _request(**overrides: object) -> models.SubmissionRequest:
    fields = {
        "repo_slug": _REPO_SLUG,
        "issue_number": _ISSUE_NUMBER,
        "fn": MagicMock(),
    }
    fields.update(overrides)
    return models.SubmissionRequest(**fields)


class BindSubmissionRequestTest(unittest.TestCase):
    def test_positional_call_applies_defaults(self) -> None:
        worker = MagicMock()

        request = models.bind_submission_request(
            (_REPO_SLUG, _ISSUE_NUMBER, worker),
            {},
        )

        self.assertEqual(
            (request.repo_slug, request.issue_number, request.fn),
            (_REPO_SLUG, _ISSUE_NUMBER, worker),
        )
        self.assertEqual(
            (request.family, request.cap_exempt, request.per_repo_cap),
            (False, False, None),
        )

    def test_keyword_only_fields_bind(self) -> None:
        request = models.bind_submission_request(
            (_REPO_SLUG, _ISSUE_NUMBER, MagicMock()),
            {"family": True, "cap_exempt": True, "per_repo_cap": _RAISED_CAP},
        )

        self.assertEqual(
            (request.family, request.cap_exempt, request.per_repo_cap),
            (True, True, _RAISED_CAP),
        )

    def test_typed_request_is_passed_through(self) -> None:
        request = _request()

        self.assertIs(models.bind_submission_request((request,), {}), request)

    def test_missing_required_field_raises(self) -> None:
        with self.assertRaises(TypeError):
            models.bind_submission_request((_REPO_SLUG, _ISSUE_NUMBER), {})

    def test_typed_request_rejection_names_extra(self) -> None:
        request = _request()
        for extra_positional, extra_keywords, detail in _REJECTED_TYPED_CALLS:
            with self.subTest(detail=detail), self.assertRaisesRegex(TypeError, detail):
                models.bind_submission_request(
                    (request, *extra_positional),
                    extra_keywords,
                )


class NormalizeSubmissionTest(unittest.TestCase):
    def test_absent_override_takes_the_default_cap(self) -> None:
        submission = models.normalize_submission(
            _request(),
            _DEFAULT_PER_REPO_CAP,
        )

        self.assertEqual(submission.per_repo_cap, _DEFAULT_PER_REPO_CAP)

    def test_override_is_coerced_and_floored(self) -> None:
        for override, expected_cap in _COERCED_CAPS:
            with self.subTest(override=override):
                submission = models.normalize_submission(
                    _request(per_repo_cap=override),
                    _DEFAULT_PER_REPO_CAP,
                )
                self.assertEqual(submission.per_repo_cap, expected_cap)

    def test_issue_number_is_coerced_for_the_key(self) -> None:
        submission = models.normalize_submission(
            _request(issue_number=str(_ISSUE_NUMBER)),
            _DEFAULT_PER_REPO_CAP,
        )

        self.assertEqual(submission.issue_number, _ISSUE_NUMBER)
        self.assertEqual(submission.key, (_REPO_SLUG, _ISSUE_NUMBER))

    def test_routing_flags_and_worker_carry_over(self) -> None:
        request = _request(family=True, cap_exempt=True)

        submission = models.normalize_submission(request, _DEFAULT_PER_REPO_CAP)

        self.assertEqual(
            (submission.family, submission.cap_exempt),
            (True, True),
        )
        self.assertIs(submission.fn, request.fn)


if __name__ == "__main__":
    unittest.main()
