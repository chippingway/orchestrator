# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The owners the question stage borrows from, and the boundary each one pins.

The stage owns its own session, but nothing else it runs: the tracked spawn, the
park, the prompt builders, the trusted conversation text, and the stderr
diagnostics all belong to `workflow/engine/`, and the worktree teardown that
keeps the stage read-only belongs to `git/worktrees/terminal.py`. Each is
imported from that owner rather than read off the `orchestrator.workflow`
facade, so a patch that has to intercept one lands on the owner. Every case
patches BOTH -- the owner mock has to answer and the facade guard has to stay
untouched -- which is what fails if a call site drifts back to `_wf`.
"""
from __future__ import annotations

import contextlib
import unittest
from unittest.mock import patch

from orchestrator import workflow
from orchestrator.git.worktrees import terminal as _worktree_terminal
from orchestrator.workflow.engine import (
    comments as _comments,
    guards as _guards,
    messages as _messages,
    prompts as _prompts,
    usage as _usage,
)
from orchestrator.workflow.stages.question import (
    handler as _question,
    models as _models,
    outcomes as _outcomes,
    run as _run,
    session as _session,
    state as _state,
)

from tests.fakes import FakeGitHubClient, make_issue
from tests.workflow_helpers import _FAKE_WT, _TEST_SPEC, _agent

BOUNDARY_ISSUE = 910
BOUNDARY_BRANCH = "orchestrator/geserdugarov__agent-orchestrator/issue-910"
BOUNDARY_SESSION = "q-sess-boundary"
BOUNDARY_PROMPT = "answer the standing question"
BOUNDARY_THREAD = "@alice asked something"
BOUNDARY_ANSWER = "it lives in src/x.py"
BOUNDARY_DIAGNOSTICS = "\n\nstderr tail"
LABEL_DONE = "done"

CLEANUP_QUESTION_WORKTREE = "_cleanup_question_worktree"
PARK_AWAITING_HUMAN = "_park_awaiting_human"
RUN_AGENT_TRACKED = "_run_agent_tracked"
BUILD_QUESTION_PROMPT = "_build_question_prompt"
RECENT_COMMENTS_TEXT = "_recent_comments_text"
FORMAT_STDERR_DIAGNOSTICS = "_format_stderr_diagnostics"
RESOLVE_BRANCH_NAME = "_resolve_branch_name"
ENSURE_WORKTREE = "_ensure_worktree"


def _question_run(*, closed: bool = False) -> _models._QuestionRun:
    """One question tick over an open or manually closed issue."""
    gh = FakeGitHubClient()
    issue = make_issue(BOUNDARY_ISSUE, label="question")
    issue.closed = closed
    gh.add_issue(issue)
    return _models._QuestionRun.start(gh, _TEST_SPEC, issue)


class _OwnerBoundaryMixin:
    """Assert a block reached no borrowed helper through the facade."""

    @contextlib.contextmanager
    def _facade_out_of_the_path(self, export_name, returns=None):
        # The guard returns the shape its caller consumes, so a regression
        # fails on the assertion below rather than on a bare mock downstream.
        with contextlib.ExitStack() as stack:
            guard = stack.enter_context(
                patch.object(workflow, export_name, return_value=returns),
            )
            yield
        self.assertFalse(
            guard.called, f"{export_name} was read off the workflow facade",
        )

    @contextlib.contextmanager
    def _worktree_on_the_facade(self):
        """Hold the worktree seams the stage does not own to fixed answers."""
        with (
            patch.object(
                workflow, RESOLVE_BRANCH_NAME, lambda *args: BOUNDARY_BRANCH,
            ),
            patch.object(
                workflow, ENSURE_WORKTREE, lambda spec, number, **_: _FAKE_WT,
            ),
        ):
            yield


class WorktreeTeardownBoundaryTest(unittest.TestCase, _OwnerBoundaryMixin):
    """Both teardowns land on the worktree terminal owner.

    `_cleanup_question_worktree` resolves on `workflow` and `worktrees` too, so
    a mock left on the facade would silently let a real teardown run.
    """

    def test_safe_exit_tears_down_on_owner(self) -> None:
        run = _question_run()
        with (
            self._facade_out_of_the_path(CLEANUP_QUESTION_WORKTREE),
            self._worktree_on_the_facade(),
            patch.object(
                _worktree_terminal, CLEANUP_QUESTION_WORKTREE,
            ) as cleanup,
        ):
            _question._cleanup_question_run(run)
            cleanup.assert_called_once()

    def test_closed_finalize_tears_down_on_owner(self) -> None:
        run = _question_run(closed=True)
        with (
            self._facade_out_of_the_path(CLEANUP_QUESTION_WORKTREE),
            self._worktree_on_the_facade(),
            patch.object(
                _worktree_terminal, CLEANUP_QUESTION_WORKTREE,
            ) as cleanup,
        ):
            self.assertTrue(_question._finalize_closed_question(run))
            cleanup.assert_called_once()
        self.assertIn((BOUNDARY_ISSUE, LABEL_DONE), run.gh.label_history)


class EngineRunBoundaryTest(unittest.TestCase, _OwnerBoundaryMixin):
    """The tracked spawn and the park land on their engine owners."""

    def test_prompt_execution_lands_on_usage_owner(self) -> None:
        run = _question_run()
        session = _models._QuestionSession(
            agent_spec="claude",
            backend="claude",
            extra_args=(),
            session_id=None,
        )
        with (
            self._facade_out_of_the_path(RUN_AGENT_TRACKED, returns=_agent()),
            patch.object(
                _usage,
                RUN_AGENT_TRACKED,
                return_value=_agent(session_id=BOUNDARY_SESSION),
            ) as spawn,
        ):
            _run._execute_question_prompt(
                run, session, BOUNDARY_PROMPT, _FAKE_WT,
            )
            spawn.assert_called_once()
        # The session id a run hands back is retained by this owner, not by
        # whichever caller started the run.
        self.assertEqual(
            run.state.get(_state._QUESTION_SESSION_KEY), BOUNDARY_SESSION,
        )

    def test_park_funnel_lands_on_guard_owner(self) -> None:
        run = _question_run()
        with (
            self._facade_out_of_the_path(PARK_AWAITING_HUMAN),
            patch.object(_guards, PARK_AWAITING_HUMAN) as park,
        ):
            _run._park_question(
                run, BOUNDARY_ANSWER, reason=_state._QUESTION_ANSWER,
            )
            park.assert_called_once()
        # The shared helper clears `park_reason`; the stage-specific one is
        # restored here, and the implementing relabel guard reads it back.
        self.assertEqual(run.state.get("park_reason"), _state._QUESTION_ANSWER)


class EnginePromptBoundaryTest(unittest.TestCase, _OwnerBoundaryMixin):
    """The question prompt and the thread it quotes land on their owners."""

    def test_fresh_spawn_builds_on_owners(self) -> None:
        run = _question_run()
        with (
            self._facade_out_of_the_path(
                BUILD_QUESTION_PROMPT, returns=BOUNDARY_PROMPT,
            ),
            self._facade_out_of_the_path(
                RECENT_COMMENTS_TEXT, returns=BOUNDARY_THREAD,
            ),
            self._worktree_on_the_facade(),
            patch.object(
                _comments, RECENT_COMMENTS_TEXT, return_value=BOUNDARY_THREAD,
            ) as thread,
            patch.object(
                _prompts, BUILD_QUESTION_PROMPT, return_value=BOUNDARY_PROMPT,
            ) as build,
            patch.object(
                _usage, RUN_AGENT_TRACKED, return_value=_agent(),
            ) as spawn,
        ):
            _run._spawn_fresh_question(run)
            thread.assert_called_once()
            build.assert_called_once()
            self.assertEqual(
                spawn.call_args.kwargs["prompt"], BOUNDARY_PROMPT,
            )

    def test_sessionless_resume_uses_first_round(self) -> None:
        with (
            self._facade_out_of_the_path(
                BUILD_QUESTION_PROMPT, returns=BOUNDARY_PROMPT,
            ),
            patch.object(_comments, RECENT_COMMENTS_TEXT, return_value=""),
            patch.object(
                _prompts, BUILD_QUESTION_PROMPT, return_value=BOUNDARY_PROMPT,
            ) as build,
        ):
            prompt = _session._build_question_resume_prompt(
                _TEST_SPEC, make_issue(BOUNDARY_ISSUE), [], None,
            )
            build.assert_called_once()
        self.assertEqual(prompt, BOUNDARY_PROMPT)


class EngineDiagnosticsBoundaryTest(unittest.TestCase, _OwnerBoundaryMixin):
    """The silent park's stderr block lands on the engine message owner."""

    def test_silent_park_reads_diagnostics_off_owner(self) -> None:
        run = _question_run()
        with (
            self._facade_out_of_the_path(
                FORMAT_STDERR_DIAGNOSTICS, returns=BOUNDARY_DIAGNOSTICS,
            ),
            patch.object(
                _messages,
                FORMAT_STDERR_DIAGNOSTICS,
                return_value=BOUNDARY_DIAGNOSTICS,
            ) as diagnostics,
        ):
            _outcomes._park_silent_question(run, _agent())
            diagnostics.assert_called_once()
        park_comment = run.gh.posted_comments[-1][1]
        self.assertIn(BOUNDARY_DIAGNOSTICS.strip(), park_comment)


if __name__ == "__main__":
    unittest.main()
