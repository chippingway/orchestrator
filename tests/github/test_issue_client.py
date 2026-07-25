# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Real-client issue polling and child creation on the `issues` owner mixin."""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from github import GithubException

from orchestrator.github.client import GitHubClient

_STATE_OPEN = "open"
_STATE_CLOSED = "closed"
_SWEPT_LABEL_COUNT = 7
_HTTP_NOT_FOUND = 404
_PARENT_ISSUE_NUMBER = 42


def _closed_sweep_fixture():
    """Return a bare client whose repo resolves each swept label by name."""
    # Bypass the networked __init__; wire only what the poll generator reads.
    client = GitHubClient.__new__(GitHubClient)
    client.repo = MagicMock()
    client._pollable_calls = 0
    client._label_cache = {}
    client.repo.get_issues.return_value = iter([])
    sweep_labels = SimpleNamespace(
        implementing=MagicMock(name="implementing_label"),
        documenting=MagicMock(name="documenting_label"),
        validating=MagicMock(name="validating_label"),
        in_review=MagicMock(name="in_review_label"),
        fixing=MagicMock(name="fixing_label"),
        resolving_conflict=MagicMock(name="resolving_conflict_label"),
        question=MagicMock(name="question_label"),
    )
    client.repo.get_label.side_effect = sweep_labels.__dict__.__getitem__
    return client, sweep_labels


def _assert_closed_sweeps(test_case, client, sweep_labels) -> None:
    calls = SimpleNamespace(
        looked_up={
            call.args[0]
            for call in client.repo.get_label.call_args_list
        },
        closed=[
            call
            for call in client.repo.get_issues.call_args_list
            if call.kwargs.get("state") == _STATE_CLOSED
        ],
    )
    test_case.assertEqual(calls.looked_up, set(sweep_labels.__dict__))
    test_case.assertEqual(len(calls.closed), _SWEPT_LABEL_COUNT)
    labels_passed = [call.kwargs["labels"] for call in calls.closed]
    for expected_label in sweep_labels.__dict__.values():
        test_case.assertIn([expected_label], labels_passed)


class ClosedIssueSweepLabelTest(unittest.TestCase):
    """The closed-issue sweep queries with Label objects, never label names.

    Real PyGithub's `Repository.get_issues(labels=...)` reads `label.name`, so
    a raw string list raises a TypeError before the generator yields anything.
    That exception escapes the per-issue try/except in `tick()`, so every tick
    would fail once the open issues were processed and externally-merged
    in_review issues would never finalize to `done`. Poking the real client
    against a mocked Repository is what pins the argument type down.
    """

    def test_closed_sweep_uses_label_object(self) -> None:
        client, sweep_labels = _closed_sweep_fixture()

        list(client.list_pollable_issues())

        _assert_closed_sweeps(self, client, sweep_labels)

    def test_missing_label_skips_closed_sweep(self) -> None:
        # If `get_label` raises (under-scoped PAT, label not yet bootstrapped)
        # the generator must complete the open-issue sweep AND swallow the
        # closed-issue branch -- otherwise `tick()` aborts mid-loop.
        client, _ = _closed_sweep_fixture()
        client.repo.get_label.side_effect = GithubException(
            _HTTP_NOT_FOUND,
            {"message": "Not Found"},
            None,
        )

        polled = list(client.list_pollable_issues())

        self.assertEqual(polled, [])
        states = [
            call.kwargs.get("state")
            for call in client.repo.get_issues.call_args_list
        ]
        self.assertEqual(states, [_STATE_OPEN])


class CreateChildIssueAlwaysUsesParentRepoTest(unittest.TestCase):
    """`create_child_issue` is structurally bound to `self.repo` so a
    misuse cannot accidentally file a child against a different repo
    than the parent. Worth a regression test anyway.
    """

    def test_creates_child_in_repo_with_parent_link(self) -> None:
        client = GitHubClient.__new__(GitHubClient)
        client.repo = MagicMock()
        sentinel = MagicMock(name="created_issue")
        client.repo.create_issue.return_value = sentinel

        created = client.create_child_issue(
            title="A",
            body="do A",
            parent_number=_PARENT_ISSUE_NUMBER,
            labels=["ready"],
        )

        self.assertIs(created, sentinel)
        client.repo.create_issue.assert_called_once()
        create_kwargs = client.repo.create_issue.call_args.kwargs
        self.assertEqual(create_kwargs["title"], "A")
        self.assertEqual(create_kwargs["labels"], ["ready"])
        # Parent link prepended via the helper (not by the caller) so the
        # workflow code can hand the agent's raw body straight in.
        self.assertIn(
            f"Parent: #{_PARENT_ISSUE_NUMBER}",
            create_kwargs["body"],
        )


if __name__ == "__main__":
    unittest.main()
