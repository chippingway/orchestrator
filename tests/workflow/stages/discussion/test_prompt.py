# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The contract the opening discussion prompt makes with its agent.

Each clause here is one the stage would be pointless without: an agent that
asks a human for facts `git log` answers burns a round, one that returns a
single answer instead of a tree hides the decision, one that asks about naming
crowds out the architecture, one that asks everything at once asks for
decisions its own earlier answers may moot, and one that starts implementing
has taken the confirmation this stage exists to wait for.
"""

from __future__ import annotations

import unittest

from orchestrator.workflow.engine import prompts as _prompts

from tests.support.fakes import make_issue
from tests.workflow.fixtures import _TEST_SPEC

_PROMPT_ISSUE_NUMBER = 950
_ISSUE_TITLE = "give the sink its own schema"
_ISSUE_BODY = "the writer and the sink disagree about who owns the columns"
_THREAD_TEXT = "@alice: this decides the migration story too"

# One clause per thing the round has to do, quoted from the prompt so a
# rewrite that drops the behavior fails here rather than in production.
_REQUIRED_CLAUSES = (
    # Research the repository rather than interviewing the human about it.
    "Research the repository yourself first",
    "Do NOT ask a human for a fact you can read",
    # Explore openly, including the option the code does not suggest, and
    # name the research that would change the answer.
    "as a tree rather than as a single answer",
    "at least one unconventional option",
    "Name any research worth doing",
    # Architecture decisions, not implementation trivia.
    "Keep it at the architecture level",
    "implementation trivia",
    # A numbered, currently-answerable frontier with recommendations.
    "NUMBERED list of the questions that can be answered right",
    "does not depend on another question you are also asking",
    "your own recommended answer",
    # Nothing happens until a human says so.
    "MUST NOT modify, create, delete, commit, or push any file",
    "MUST NOT start implementing",
    "Wait for a human to confirm the decisions explicitly",
)


class DiscussionPromptTest(unittest.TestCase):

    def setUp(self) -> None:
        self.prompt = _prompts._build_discussion_prompt(
            _TEST_SPEC,
            make_issue(
                _PROMPT_ISSUE_NUMBER, title=_ISSUE_TITLE, body=_ISSUE_BODY,
            ),
            _THREAD_TEXT,
            [_TEST_SPEC],
        )

    def test_every_clause_reaches_the_agent(self) -> None:
        for clause in _REQUIRED_CLAUSES:
            with self.subTest(clause=clause):
                self.assertIn(clause, self.prompt)

    def test_round_is_framed_as_a_discussion(self) -> None:
        self.assertIn(
            f"architecture discussion on GitHub issue #{_PROMPT_ISSUE_NUMBER}",
            self.prompt,
        )
        self.assertIn(_ISSUE_TITLE, self.prompt)
        self.assertIn("Nobody has asked you to implement anything", self.prompt)


if __name__ == "__main__":
    unittest.main()
