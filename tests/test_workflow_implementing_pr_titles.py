# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Tests for implementing pr titles behavior."""

from __future__ import annotations

import unittest

from tests import implementing_pr_test_support as support

CONVENTIONAL_ISSUE = support.CONVENTIONAL_ISSUE
DEV_SESSION = support.DEV_SESSION
DONE_MESSAGE = support.DONE_MESSAGE
INFERRED_PREFIX_ISSUE = support.INFERRED_PREFIX_ISSUE
SPARKLY_COMMIT_SUBJECT = support.SPARKLY_COMMIT_SUBJECT
_ConventionalTitleFixtureMixin = support._ConventionalTitleFixtureMixin
_agent = support._agent


class ConventionalPrTitleTest(
    unittest.TestCase,
    _ConventionalTitleFixtureMixin,
):
    """`_on_commits` opens the PR with the title the publication owner picks
    from the agent's first commit subject and the inferred repo prefix, and
    keeps traceability in the body."""

    def test_uses_selected_title_and_links_the_issue(self) -> None:
        gh, issue = self._seeded(issue_number=CONVENTIONAL_ISSUE)

        self._run_implementing(
            gh,
            issue,
            run_agent=_agent(session_id=DEV_SESSION, last_message=DONE_MESSAGE),
            has_new_commits=[False, True],
            dirty_files=(),
            push_branch=True,
            first_commit_subject=SPARKLY_COMMIT_SUBJECT,
        )

        self.assertEqual(len(gh.opened_prs), 1)
        pr = gh.opened_prs[0]
        # First-commit subject is preserved verbatim, no extra prefix.
        self.assertEqual(pr.title, SPARKLY_COMMIT_SUBJECT)
        # Traceability still in body.
        self.assertIn(f"Resolves #{issue.number}", pr.body)

    def test_inferred_repo_prefix_reaches_the_title(self) -> None:
        # First commit subject is unprefixed, so the handler must thread the
        # prefix `_infer_subject_prefix` read from base history into the
        # synthesized title instead of defaulting to `feat:`.
        gh, issue = self._seeded(issue_number=INFERRED_PREFIX_ISSUE)

        self._run_implementing(
            gh,
            issue,
            run_agent=_agent(session_id=DEV_SESSION, last_message=DONE_MESSAGE),
            has_new_commits=[False, True],
            dirty_files=(),
            push_branch=True,
            first_commit_subject="updated the listings",
            fallback_prefix="career",
        )

        self.assertEqual(gh.opened_prs[0].title, "career: add a sparkly thing")
