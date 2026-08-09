# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The agent-message contract.

Three behaviors carry the weight here. Agent stderr is redacted before it is
trimmed, so a secret straddling either budget cannot survive as a partial
value. A drift acknowledgement needs the explicit `ACK:` marker, so a
clarification question is never mistaken for agreement. And `/orchestrator
continue` is classified before it is obeyed, so a content-free nudge retries a
session failure but is refused on a park that is waiting for a real answer.
"""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from orchestrator.agents import AgentResult
from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.engine import messages

from tests.fakes import FakeComment, FakeGitHubClient, make_issue


_AGENT_SESSION_ID = "s"
_REDACTION_MARKER = "***"
_CONTINUE_COMMAND = "/orchestrator continue"
_REFUSAL_ISSUE_NUMBER = 1011
_WATERMARK_KEY = "last_action_comment_id"
def _agent_result(stderr: str) -> AgentResult:
    return AgentResult(
        session_id=_AGENT_SESSION_ID, last_message="", exit_code=1,
        timed_out=False, stdout="", stderr=stderr,
    )


class DiagnosticsRedactionTest(unittest.TestCase):
    """Agent stderr is redacted before it is trimmed for a park comment or
    a log line, so a secret cannot survive as a partial value on either
    side of the cut.
    """

    def test_diagnostics_redact_before_truncation(self) -> None:
        # Park comments cap the surfaced tail at 1KB. If we redacted after
        # slicing, a key that spans the cut would survive in the visible
        # tail. Pad noise so the secret would otherwise straddle the cap.
        secret = "sk-ant-spanningthecutboundary123"
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": secret}, clear=False):
            padding = "X" * (messages._STDERR_TAIL_BUDGET - 8)
            block = messages._format_stderr_diagnostics(
                _agent_result(f"{padding}{secret} trailing"), "Agent",
            )
        self.assertNotIn(secret, block)
        self.assertIn(_REDACTION_MARKER, block)
        # The tail budget is still honored on the *redacted* string.
        self.assertIn("trailing", block)

    def test_log_tail_redacts(self) -> None:
        with patch.dict(
            os.environ, {"OPENAI_API_KEY": "sk-proj-loglinevaluexyz"}, clear=False,
        ):
            tail = messages._stderr_log_tail(
                _agent_result("auth failed for sk-proj-loglinevaluexyz"),
            )
        self.assertNotIn("sk-proj-loglinevaluexyz", tail)

    def test_diagnostics_redact_multiline_eof_secret(self) -> None:
        # A multi-line secret whose env value itself ends in `\n` (e.g. a
        # PEM/SSH key) echoed at the end of stderr. If rstrip ran first,
        # the trailing newline would be eaten and `str.replace(value,
        # "***")` would no longer match the env value verbatim, leaking
        # the secret into the park comment.
        secret = "-----BEGIN PRIVATE KEY-----\nAAAABBBBCCCCDDDD\n-----END PRIVATE KEY-----\n"
        with patch.dict(os.environ, {"SSH_PRIVATE_KEY": secret}, clear=False):
            block = messages._format_stderr_diagnostics(
                _agent_result(f"boom: {secret}"), "Agent",
            )
        self.assertNotIn("AAAABBBBCCCCDDDD", block)
        self.assertIn(_REDACTION_MARKER, block)

    def test_log_tail_redacts_multiline_secret_at_eof(self) -> None:
        secret = "line1-of-secret-value\nline2-of-secret-value\n"
        with patch.dict(os.environ, {"API_TOKEN": secret}, clear=False):
            tail = messages._stderr_log_tail(_agent_result(f"leaked: {secret}"))
        self.assertNotIn("line2-of-secret-value", tail)


class DriftAckMarkerTest(unittest.TestCase):
    """A generic non-empty no-commit response is OFTEN a clarification
    question, not an ack. Only an explicit `ACK: ...` marker counts as
    acknowledgement; everything else leaves the caller on its park path."""

    def test_explicit_ack_marker_extracts_reason(self) -> None:
        msg = (
            "I reviewed the change.\n\n"
            "ACK: existing tests already cover the new requirement"
        )
        self.assertEqual(
            messages._drift_ack_reason(msg),
            "existing tests already cover the new requirement",
        )

    def test_ack_is_case_insensitive_and_last_wins(self) -> None:
        # Case insensitive (mirrors VERDICT parsing) and the LAST marker
        # wins so a sample/template `ACK:` quoted earlier in the message
        # doesn't override the agent's real concluding marker.
        msg = (
            "I considered ack: stale-template-text but on re-reading\n\n"
            "ack: real final justification"
        )
        self.assertEqual(
            messages._drift_ack_reason(msg), "real final justification",
        )

    def test_unmarked_prose_is_not_an_ack(self) -> None:
        for msg in (
            "Existing code already covers this; no change needed.",
            "Should I also handle the empty-input case?",
            "",
        ):
            with self.subTest(message=msg):
                self.assertIsNone(messages._drift_ack_reason(msg))


class ContinueCommandRecognitionTest(unittest.TestCase):
    """Which comments carry the operator command, and which of those carry
    nothing but the command."""

    def test_parser_matches_exact_continue_line(self) -> None:
        comments = [
            FakeComment(id=1, body=_CONTINUE_COMMAND),
            FakeComment(id=2, body="  /Orchestrator  Continue  "),
            FakeComment(id=3, body="/orchestrator continue\n"),
            FakeComment(id=4, body="please run `/orchestrator continue`"),
            FakeComment(id=5, body="please fix X\n/orchestrator continue"),
            FakeComment(id=6, body="/orchestrator continue\nthanks"),
            FakeComment(id=7, body="/orchestrator add-review-rounds 2"),
        ]

        matched = messages._parse_orchestrator_continue(comments)

        # Any comment carrying the command as an exact line matches -- including
        # one that also carries guidance (5, 6) -- so the command still fires
        # the replay. A prose mention in backticks (4) and a different command
        # (7) do not.
        matched_ids = [comment.id for comment in matched]
        self.assertEqual(matched_ids, [1, 2, 3, 5, 6])

    def test_bare_is_distinguished_from_guided(self) -> None:
        # `_is_bare_*` distinguishes a content-free nudge (whole body is the
        # command, whitespace ignored) from a comment that also carries
        # guidance -- the latter must not be refused/consumed as content-free.
        bare_bodies = (
            _CONTINUE_COMMAND,
            "  /Orchestrator  Continue  ",
            "/orchestrator continue\n",
        )
        guided_bodies = (
            "please fix X\n/orchestrator continue",
            "/orchestrator continue\nthanks",
            "please run `/orchestrator continue`",
        )
        for body in bare_bodies:
            with self.subTest(bare=body):
                self.assertTrue(
                    messages._is_bare_orchestrator_continue(
                        FakeComment(id=1, body=body),
                    ),
                )
        for body in guided_bodies:
            with self.subTest(guided=body):
                self.assertFalse(
                    messages._is_bare_orchestrator_continue(
                        FakeComment(id=1, body=body),
                    ),
                )


class ContinueCommandActionTest(unittest.TestCase):
    """`_continue_command_action` classifies an operator `/orchestrator
    continue` on a parked dev-session stage. Retryable session-failure parks
    with a content-free nudge retry; parks needing a real answer refuse;
    anything else (no command, or a command carrying guidance) passes through
    to the normal resume / drift path."""

    def test_retryable_park_bare_continue_retries(self) -> None:
        for reason in sorted(messages._CONTINUE_PARK_REASONS):
            with self.subTest(reason=reason):
                self.assertEqual(
                    messages._continue_command_action(
                        [FakeComment(id=1, body=_CONTINUE_COMMAND)], reason,
                    ),
                    "retry",
                )

    def test_non_retryable_park_bare_continue_refuses(self) -> None:
        for reason in (None, "dirty_worktree", "diverged_branch"):
            with self.subTest(reason=reason):
                self.assertEqual(
                    messages._continue_command_action(
                        [FakeComment(id=1, body=_CONTINUE_COMMAND)], reason,
                    ),
                    "refuse",
                )

    def test_guidance_or_no_command_passes_through(self) -> None:
        # With guidance alongside the command, the normal resume/drift path
        # has to feed that guidance to the dev instead of consuming the
        # comment as a bare nudge.
        for body in (f"{_CONTINUE_COMMAND}\nrename the flag", "just a normal reply"):
            with self.subTest(body=body):
                self.assertEqual(
                    messages._continue_command_action(
                        [FakeComment(id=1, body=body)], "agent_silent",
                    ),
                    "passthrough",
                )


class RefuseParkedContinueTest(unittest.TestCase):
    """The refusal has to consume the command it answers, or it re-fires and
    re-posts on every following tick."""

    def test_refusal_advances_the_watermark(self) -> None:
        gh = FakeGitHubClient()
        issue = make_issue(_REFUSAL_ISSUE_NUMBER)
        gh.add_issue(issue)
        issue.comments.append(FakeComment(id=1, body=_CONTINUE_COMMAND))
        state = PinnedState(state_data={})

        messages._refuse_parked_continue(gh, issue, state)

        _issue_number, posted_body = gh.posted_comments[-1]
        self.assertIn("needs your actual", posted_body)
        # Past BOTH the command and the refusal itself.
        self.assertEqual(state.get(_WATERMARK_KEY), gh.latest_comment_id(issue))


if __name__ == "__main__":
    unittest.main()
