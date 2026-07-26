# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The prompt owner's shared parts, and the facades still forwarding it.

What every builder has in common is what this module pins: the header that
carries the issue body and the thread text (with placeholders when either is
empty), the two notes a prompt that can end in a commit has to spell out, and
the bounded rendering the conflict listing falls back on. Per-stage contracts
that only one prompt promises are pinned beside the stage that reads the
answer back.
"""
from __future__ import annotations

import unittest

from orchestrator import workflow, workflow_drift, workflow_messages
from orchestrator.workflow.engine import prompts

from tests.fakes import FakeComment, FakeUser, make_issue
from tests.workflow_helpers import _TEST_SPEC


_PROMPT_ISSUE_NUMBER = 67200
_ISSUE_TITLE = "add a foo flag"
_ISSUE_BODY = "users want a foo flag"
_THREAD_TEXT = "@alice: please cover it in tests"
_BASE_REF = "origin/main"
_OVERFLOW_FILES = 23
_FEEDBACK_COMMENT_ID = 42
# Subject prefixes the repo-local instruction must NOT enumerate: the
# orchestrator runs against arbitrary repos, so a closed Conventional-Commits
# list would teach the wrong style everywhere else.
_FORBIDDEN_PREFIXES = ("feat:", "chore:", "refactor:", "test:")
_FOREGROUND_MARKER = "NEVER start a background job"

# Every builder that opens on the shared issue-body + conversation header.
_HEADER_BUILDERS = (
    ("implement", prompts._build_implement_prompt),
    ("respawn_preamble", prompts._build_fresh_respawn_preamble),
    ("review", prompts._build_review_prompt),
    ("documentation", prompts._build_documentation_prompt),
    ("question", prompts._build_question_prompt),
    ("decompose", prompts._build_decompose_prompt),
)

# Every name each historical facade still has to answer for, and the facade it
# answers on. Live issues and external operator scripts reach the owner through
# these, so a forward that stops resolving is a break, not a rename.
_FACADE_FORWARDS = (
    (workflow, (
        "_CONTINUE_RETRY_PROMPT",
        "_FOREGROUND_ONLY_NOTE",
        "_build_conflict_resolution_prompt",
        "_build_decompose_prompt",
        "_build_documentation_prompt",
        "_build_fix_prompt",
        "_build_fresh_respawn_preamble",
        "_build_implement_prompt",
        "_build_pr_comment_followup",
        "_build_question_followup_prompt",
        "_build_question_prompt",
        "_build_review_prompt",
        "_build_single_decision_comment",
    )),
    (workflow_messages, (
        "_COMMIT_STYLE_NOTE",
        "_CONTINUE_RETRY_PROMPT",
        "_FOREGROUND_ONLY_NOTE",
        "_MAX_FILES_SHOWN",
        "_NO_BODY",
        "_NO_PRIOR_COMMENTS",
        "_build_conflict_resolution_prompt",
        "_build_decompose_prompt",
        "_build_documentation_prompt",
        "_build_fix_prompt",
        "_build_fresh_respawn_preamble",
        "_build_implement_prompt",
        "_build_pr_comment_followup",
        "_build_question_followup_prompt",
        "_build_question_prompt",
        "_build_review_prompt",
        "_build_single_decision_comment",
        "_single_manifest_files",
        "_single_manifest_text",
    )),
    (workflow_drift, ("_COMMIT_STYLE_NOTE", "_FOREGROUND_ONLY_NOTE")),
)


# The conflict prompt is the one commit-producing prompt with no style note:
# its agent finishes an in-progress rebase (`git rebase --continue`) and
# authors no subject of its own.
_NO_STYLE_NOTE_PROMPTS = frozenset(("conflict",))


def _commit_producing_prompts() -> dict[str, str]:
    """Every prompt whose agent may end its turn with a commit.

    `_build_user_content_change_prompt` is owned by the drift routes, but it
    appends the same two notes, so it belongs in this sweep -- the contract is
    the note's, not the builder's.
    """
    issue = make_issue(
        _PROMPT_ISSUE_NUMBER, title=_ISSUE_TITLE, body=_ISSUE_BODY,
    )
    comments = [
        FakeComment(
            id=_FEEDBACK_COMMENT_ID,
            body="please rename foo to bar",
            user=FakeUser("alice"),
        ),
    ]
    return {
        "implement": prompts._build_implement_prompt(
            _TEST_SPEC, issue, comments_text="", specs=[_TEST_SPEC],
        ),
        "fix": prompts._build_fix_prompt("please fix the typo"),
        "pr_comment_followup": prompts._build_pr_comment_followup(comments),
        "documentation": prompts._build_documentation_prompt(
            _TEST_SPEC, issue, comments_text="", specs=[_TEST_SPEC],
        ),
        "conflict": prompts._build_conflict_resolution_prompt(
            _BASE_REF, ["a.rs"],
        ),
        "user_content_change": workflow_drift._build_user_content_change_prompt(
            issue, comments_text="",
        ),
    }


class SharedPromptHeaderTest(unittest.TestCase):
    """One header feeds every conversation-carrying builder, so the issue body
    and the (already trust-filtered) thread text reach all of them -- and an
    empty one reads as an explicit placeholder rather than a blank section the
    agent could mistake for a truncated prompt."""

    def test_body_and_thread_reach_every_prompt(self) -> None:
        issue = make_issue(
            _PROMPT_ISSUE_NUMBER, title=_ISSUE_TITLE, body=_ISSUE_BODY,
        )
        for name, builder in _HEADER_BUILDERS:
            with self.subTest(builder=name):
                prompt = builder(
                    _TEST_SPEC, issue, _THREAD_TEXT, [_TEST_SPEC],
                )
                self.assertIn(_ISSUE_BODY, prompt)
                self.assertIn(_THREAD_TEXT, prompt)
                self.assertNotIn(prompts._NO_BODY, prompt)
                self.assertNotIn(prompts._NO_PRIOR_COMMENTS, prompt)

    def test_empty_body_and_thread_get_placeholders(self) -> None:
        issue = make_issue(_PROMPT_ISSUE_NUMBER, title=_ISSUE_TITLE, body="")
        for name, builder in _HEADER_BUILDERS:
            with self.subTest(builder=name):
                prompt = builder(_TEST_SPEC, issue, "", [_TEST_SPEC])
                self.assertIn(prompts._NO_BODY, prompt)
                self.assertIn(prompts._NO_PRIOR_COMMENTS, prompt)


class CommitProducingNotesTest(unittest.TestCase):
    """The two notes every commit-producing prompt carries.

    The style note points the agent at the repo's OWN recent history rather
    than a hardcoded prefix list, because the orchestrator runs against
    arbitrary configured repos. The foreground note spells out the one-shot
    execution model: a backgrounded build ("Miri is running, I'll continue
    when it completes") outlives no session, so its result is never observed
    and the issue parks forever.
    """

    def test_authoring_prompts_teach_local_style(self) -> None:
        for name, prompt in _commit_producing_prompts().items():
            if name in _NO_STYLE_NOTE_PROMPTS:
                continue
            with self.subTest(prompt=name):
                self.assertIn("git log", prompt)
                self.assertIn("repository-local", prompt)
                self.assertIn("event:", prompt)
                self.assertIn("career:", prompt)
                self.assertNotIn("Conventional", prompt)
                for prefix in _FORBIDDEN_PREFIXES:
                    self.assertNotIn(prefix, prompt)
                self.assertIn("subject line only", prompt)
                self.assertIn("Co-Authored-By", prompt)

    def test_every_prompt_has_the_foreground_note(self) -> None:
        for name, prompt in _commit_producing_prompts().items():
            with self.subTest(prompt=name):
                self.assertIn(_FOREGROUND_MARKER, prompt)


class ConflictResolutionPromptTest(unittest.TestCase):
    """The conflicted-path listing is bounded: a rebase across a large base
    can conflict in far more files than belong in a prompt, so the list is
    capped while the count that frames the work stays exact."""

    def test_lists_every_path_below_the_cap(self) -> None:
        prompt = prompts._build_conflict_resolution_prompt(
            _BASE_REF, ["a.rs", "b/c.rs"],
        )
        self.assertIn(f"`git rebase {_BASE_REF}` left 2 conflicted", prompt)
        self.assertIn("- `a.rs`", prompt)
        self.assertIn("- `b/c.rs`", prompt)
        self.assertNotIn("more)", prompt)

    def test_overflow_elides_with_remainder_count(self) -> None:
        shown = prompts._MAX_FILES_SHOWN
        last_shown = shown - 1
        elided = _OVERFLOW_FILES - shown
        prompt = prompts._build_conflict_resolution_prompt(
            _BASE_REF, [f"f{index}.rs" for index in range(_OVERFLOW_FILES)],
        )
        self.assertIn(f"left {_OVERFLOW_FILES} conflicted", prompt)
        self.assertIn(f"- `f{last_shown}.rs`", prompt)
        self.assertNotIn(f"- `f{shown}.rs`", prompt)
        self.assertIn(f"- ... ({elided} more)", prompt)


class FixPromptTest(unittest.TestCase):

    def test_empty_feedback_still_names_the_reviewer(self) -> None:
        # A changes-requested verdict with nothing above the marker leaves the
        # feedback blank. The prompt still has to say what the agent is being
        # asked to do rather than quote an empty block.
        prompt = prompts._build_fix_prompt("   ")
        self.assertIn("(reviewer left no detail)", prompt)


class PromptFacadeForwardTest(unittest.TestCase):
    """Each historical facade resolves to the owner's exact object."""

    def test_facades_forward_the_owner_objects(self) -> None:
        for facade, forwarded_names in _FACADE_FORWARDS:
            for forwarded_name in forwarded_names:
                with self.subTest(facade=facade.__name__, name=forwarded_name):
                    self.assertIs(
                        getattr(facade, forwarded_name),
                        getattr(prompts, forwarded_name),
                    )


if __name__ == "__main__":
    unittest.main()
