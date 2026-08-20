# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The wording a self-recovered park posts, and the assertion over it.

Neither stage owns this. The transient-park recovery lives under `validating`
and the parked `fixing` branch calls it, so both stage test packages assert the
same sentences -- which is why the leaf sits here rather than in either one's
support module.
"""

from __future__ import annotations

PUSH_FAILED = "push_failed"
AGENT_TIMEOUT = "agent_timeout"
REVIEWER_TIMEOUT = "reviewer_timeout"
REVIEWER_FAILED = "reviewer_failed"

OUTCOME_PUSHED = "pushed"
OUTCOME_CLEARED = "cleared"

LAST_ACTION_COMMENT_ID = "last_action_comment_id"

RECOVERED_PREFIX = "Recovered automatically:"
NO_ACTION_LINE = "No action needed."
PUSH_RETRIED_DETAIL = "the failed push was retried and succeeded"
TIMEOUT_PUSHED_DETAIL = "the commit the timed-out run had already made was pushed"
TIMEOUT_EMPTY_DETAIL = "the timed-out run had left nothing to publish"
REVIEWER_RESPAWN_DETAIL = "the reviewer is being re-spawned"


class _RecoveryFollowupAssertions:
    """Assert the one comment a self-healed park leaves behind."""

    def _assert_recovery_followup(self, github, detail: str) -> None:
        """One follow-up naming what healed, with nobody mentioned on it."""
        bodies = [body for _, body in github.posted_comments]
        self.assertEqual(len(bodies), 1)
        self.assertIn(RECOVERED_PREFIX, bodies[0])
        self.assertIn(detail, bodies[0])
        self.assertIn(NO_ACTION_LINE, bodies[0])
        self.assertNotIn("@", bodies[0])
