# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Prompt builder for the documentation stage and the stderr/log diagnostic
blocks. The prompt teaches the agent the contract the verdict parser
enforces; the diagnostics run the shared redactor over agent stderr before
any of it is trimmed for a park comment or a log line."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from orchestrator import workflow
from orchestrator.agents import AgentResult

from tests.fakes import make_issue
from tests.workflow_helpers import _TEST_SPEC


_DOCUMENTATION_ISSUE_NUMBER = 67100
_REDACTION_MARKER = "***"
_AGENT_SESSION_ID = "s"


def _documentation_prompt() -> str:
    return workflow._build_documentation_prompt(
        _TEST_SPEC,
        make_issue(
            _DOCUMENTATION_ISSUE_NUMBER,
            title="add foo flag",
            body="users want a foo flag",
        ),
        comments_text="",
        specs=[_TEST_SPEC],
    )


def _patched_env(**env_values: str):
    return patch.dict(os.environ, env_values, clear=False)


class BuildDocumentationPromptTest(unittest.TestCase):
    """The documentation prompt is what teaches the agent the contract
    the parser relies on. Verify the contract is actually communicated:
    diff vs stable docs (README and `docs/` only -- the `plans/` tree
    and roadmap entries are working notes owned by humans and the
    prompt must steer the agent away from them), a repo-local (NOT
    forced `docs:`) commit subject for the update branch, explicit
    `DOCS: NO_CHANGE` marker for the no-update branch, and a refusal to
    accept ambiguous phrasing.
    """

    def test_instructs_diff_against_readme_and_docs(self) -> None:
        prompt = _documentation_prompt()
        self.assertIn("README.md", prompt)
        self.assertIn("docs/", prompt)
        base_ref = f"{_TEST_SPEC.remote_name}/{_TEST_SPEC.base_branch}"
        self.assertIn(f"git diff {base_ref}...HEAD", prompt)

    def test_steers_agent_away_from_plans_and_roadmap(self) -> None:
        # `plans/` and roadmap entries are working notes owned by
        # humans -- the final-docs pass must not target them. The prompt
        # has to call that out explicitly so the agent does not infer
        # `plans/` from convention.
        prompt = _documentation_prompt()
        self.assertIn("plans/", prompt)
        self.assertIn("roadmap", prompt)
        self.assertIn("out of scope", prompt)

    def test_updated_case_does_not_require_prefix(self) -> None:
        # The docs pass must no longer force the `docs:` Conventional-Commit
        # type: the agent mirrors the repo's own recent commit style, so a
        # project-specific prefix (`event:`, `career:`, ...) is allowed for a
        # documentation update just as for any other commit.
        prompt = _documentation_prompt()
        self.assertNotIn("docs:", prompt)
        self.assertNotIn('git commit -m "docs: <subject>"', prompt)
        # Repo-local style is taught instead, and the subject-only rule is
        # still enforced.
        self.assertIn("git log", prompt)
        self.assertIn("repository-local", prompt)
        self.assertIn("subject line only", prompt)

    def test_specifies_machine_no_change_marker(self) -> None:
        prompt = _documentation_prompt()
        self.assertIn("DOCS: NO_CHANGE", prompt)

    def test_warns_against_ambiguous_no_change_text(self) -> None:
        # The prompt itself must tell the agent that prose like
        # 'no changes needed' will be parked, mirroring the parser's
        # refusal to accept it.
        prompt = _documentation_prompt()
        self.assertIn("'no changes needed'", prompt)

    def test_includes_issue_title_and_number(self) -> None:
        prompt = _documentation_prompt()
        self.assertIn(f"#{_DOCUMENTATION_ISSUE_NUMBER}", prompt)
        self.assertIn("add foo flag", prompt)


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
        with _patched_env(ANTHROPIC_API_KEY=secret):
            padding = "X" * (workflow._STDERR_TAIL_BUDGET - 8)
            stderr = f"{padding}{secret} trailing"
            block = workflow._format_stderr_diagnostics(
                AgentResult(
                    session_id=_AGENT_SESSION_ID, last_message="", exit_code=1,
                    timed_out=False, stdout="", stderr=stderr,
                ),
                "Agent",
            )
        self.assertNotIn(secret, block)
        self.assertIn(_REDACTION_MARKER, block)
        # The tail budget is still honored on the *redacted* string.
        self.assertIn("trailing", block)

    def test_log_tail_redacts(self) -> None:
        with _patched_env(OPENAI_API_KEY="sk-proj-loglinevaluexyz"):
            tail = workflow._stderr_log_tail(
                AgentResult(
                    session_id=_AGENT_SESSION_ID, last_message="", exit_code=1,
                    timed_out=False, stdout="",
                    stderr="auth failed for sk-proj-loglinevaluexyz",
                ),
            )
        self.assertNotIn("sk-proj-loglinevaluexyz", tail)

    def test_diagnostics_redact_multiline_eof_secret(self) -> None:
        # Regression for the rstrip-before-redact ordering bug: a
        # multi-line secret whose env value itself ends in `\n` (e.g. a
        # PEM/SSH key) echoed at the end of stderr. If rstrip ran first,
        # the trailing newline would be eaten and `str.replace(value,
        # "***")` would no longer match the env value verbatim, leaking
        # the secret into the park comment.
        secret = "-----BEGIN PRIVATE KEY-----\nAAAABBBBCCCCDDDD\n-----END PRIVATE KEY-----\n"
        with _patched_env(SSH_PRIVATE_KEY=secret):
            block = workflow._format_stderr_diagnostics(
                AgentResult(
                    session_id=_AGENT_SESSION_ID, last_message="", exit_code=1,
                    timed_out=False, stdout="",
                    stderr=f"boom: {secret}",
                ),
                "Agent",
            )
        self.assertNotIn("AAAABBBBCCCCDDDD", block)
        self.assertIn(_REDACTION_MARKER, block)

    def test_log_tail_redacts_multiline_secret_at_eof(self) -> None:
        secret = "line1-of-secret-value\nline2-of-secret-value\n"
        with _patched_env(API_TOKEN=secret):
            tail = workflow._stderr_log_tail(
                AgentResult(
                    session_id=_AGENT_SESSION_ID, last_message="", exit_code=1,
                    timed_out=False, stdout="",
                    stderr=f"leaked: {secret}",
                ),
            )
        self.assertNotIn("line2-of-secret-value", tail)
