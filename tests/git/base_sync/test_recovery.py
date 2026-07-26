# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The order an interrupted rebase is routed in, on the `recovery` owner."""

from __future__ import annotations

import contextlib
import dataclasses
import unittest
from types import MappingProxyType
from unittest.mock import MagicMock, patch

from orchestrator.git import authentication
from orchestrator.git.base_sync import (
    outcomes,
    persistence,
    recovery,
    snapshot,
)
from orchestrator.git.verification import probes as verification_probes

from tests.git.base_sync import base_sync_helpers as fixtures

FETCH_SNAPSHOT = "_fetch_recovery_snapshot"

COMPLETE_SNAPSHOT = "_complete_recovery_snapshot"

CLEAR_INELIGIBLE = "_clear_ineligible_recovery"

CLEAR_UNCHANGED = "_clear_unchanged_recovery"

ROUTE_SNAPSHOT = "_route_recovery_snapshot"

RETRY_PUSH = "_retry_recovery_push"

FINALIZE_HELPER = "_finalize_recovered_rebase"

PUSH_BRANCH = "_push_branch"

DIRTY_FILES = "_worktree_dirty_files"

PUSHED_METHOD = "crash_recovery_pushed"

LEFTOVERS = ("scratch.txt",)

ALREADY_PUBLISHED = "_finalize_already_published_recovery"

UNKNOWN_COMPARISON = "_reject_unknown_recovery_comparison"

DIVERGED = "_park_diverged_recovery"

# Every answer a completed comparison can resolve into, and the owner it is
# selected on.
ANSWERS = (
    (outcomes, ALREADY_PUBLISHED),
    (outcomes, UNKNOWN_COMPARISON),
    (outcomes, DIVERGED),
    (recovery, RETRY_PUSH),
)

# Each completed comparison and the single answer it selects. The ahead-only
# row is the only one that reaches a push, which is what keeps a force-push
# off every head the tick could not prove is ahead of the remote it read.
ROUTE_CASES = (
    (
        fixtures._snapshot(remote_head=fixtures.RECOVERED_SHA),
        ALREADY_PUBLISHED,
    ),
    (fixtures._snapshot(), UNKNOWN_COMPARISON),
    (fixtures._snapshot(ahead=1, behind=2), DIVERGED),
    (fixtures._snapshot(ahead=1), RETRY_PUSH),
)

_OWNERS = MappingProxyType(
    {
        CLEAR_INELIGIBLE: snapshot,
        CLEAR_UNCHANGED: snapshot,
        COMPLETE_SNAPSHOT: snapshot,
        FETCH_SNAPSHOT: snapshot,
        ROUTE_SNAPSHOT: recovery,
    },
)


def _handled() -> MagicMock:
    """A collaborator stub that reports the tick as handled."""
    return MagicMock(return_value=True)


@contextlib.contextmanager
def _routed(**collaborators):
    """Patch the named recovery collaborators on the owner they live on."""
    with contextlib.ExitStack() as stack:
        for name, replacement in collaborators.items():
            stack.enter_context(
                patch.object(_OWNERS[name], name, replacement),
            )
        yield


@contextlib.contextmanager
def _every_answer(selected: dict):
    """Patch every answer the route can select, recording them by name."""
    with contextlib.ExitStack() as stack:
        for owner, name in ANSWERS:
            selected[name] = _handled()
            stack.enter_context(patch.object(owner, name, selected[name]))
        yield


class RecoveryRouteTest(unittest.TestCase):
    """Every question is asked before the one it would make unsafe."""

    def test_ineligible_label_clears_before_any_fetch(self) -> None:
        context = fixtures._recovery_context()
        cleared = _handled()
        fetch = MagicMock()

        with _routed(
            **{CLEAR_INELIGIBLE: cleared, FETCH_SNAPSHOT: fetch},
        ):
            recovered = recovery._recover_pending_auto_base_rebase_context(
                self._relabelled(context),
            )

        self.assertTrue(recovered)
        cleared.assert_called_once()
        # An issue nobody is refreshing any more is not worth a network hop.
        fetch.assert_not_called()

    def test_unreadable_snapshot_owns_the_tick(self) -> None:
        # The fetch already reset and parked, so returning True is what stops
        # the caller from rebasing against a head it could not verify.
        route = MagicMock()

        with _routed(
            **{
                FETCH_SNAPSHOT: MagicMock(return_value=None),
                ROUTE_SNAPSHOT: route,
            },
        ):
            recovered = recovery._recover_pending_auto_base_rebase_context(
                fixtures._recovery_context(),
            )

        self.assertTrue(recovered)
        route.assert_not_called()

    def test_unmoved_head_falls_back(self) -> None:
        unchanged = fixtures._snapshot(local_head=fixtures.PRE_REBASE_SHA)
        cleared = MagicMock(return_value=False)
        route = MagicMock()

        with _routed(
            **{
                FETCH_SNAPSHOT: MagicMock(return_value=unchanged),
                CLEAR_UNCHANGED: cleared,
                ROUTE_SNAPSHOT: route,
            },
        ):
            recovered = recovery._recover_pending_auto_base_rebase_context(
                fixtures._recovery_context(),
            )

        # Nothing was rewritten, so there is nothing to compare and the same
        # tick continues into the normal rebase flow.
        self.assertFalse(recovered)
        cleared.assert_called_once()
        route.assert_not_called()

    def test_moved_head_is_routed_from_its_comparison(self) -> None:
        moved = fixtures._snapshot()
        route = _handled()

        with _routed(
            **{
                FETCH_SNAPSHOT: MagicMock(return_value=moved),
                ROUTE_SNAPSHOT: route,
            },
        ):
            recovery._recover_pending_auto_base_rebase_context(
                fixtures._recovery_context(),
            )

        self.assertIs(route.call_args.args[1], moved)

    def _relabelled(self, context):
        return dataclasses.replace(context, label="implementing")


class RecoveryComparisonTest(unittest.TestCase):
    """One completed comparison resolves into exactly one answer."""

    def test_each_comparison_selects_its_answer(self) -> None:
        for completed, answer in ROUTE_CASES:
            with self.subTest(answer=answer):
                self._assert_selects(completed, answer)

    def test_unverified_comparison_owns_the_tick(self) -> None:
        # `_complete_recovery_snapshot` already parked; no answer applies.
        with _routed(
            **{COMPLETE_SNAPSHOT: MagicMock(return_value=None)},
        ):
            routed = recovery._route_recovery_snapshot(
                fixtures._recovery_context(), fixtures._snapshot(),
            )

        self.assertTrue(routed)

    def _assert_selects(self, completed, answer: str) -> None:
        selected = {}

        with _every_answer(selected):
            with _routed(
                **{COMPLETE_SNAPSHOT: MagicMock(return_value=completed)},
            ):
                self.assertTrue(
                    recovery._route_recovery_snapshot(
                        fixtures._recovery_context(), fixtures._snapshot(),
                    ),
                )

        self.assertIs(selected.pop(answer).call_args.args[1], completed)
        for unselected in selected.values():
            unselected.assert_not_called()


class RetryRecoveryPushTest(unittest.TestCase):
    """The reissued push is guarded, leased, and finalized as its own method."""

    def test_ahead_head_is_pushed_under_lease(self) -> None:
        context = fixtures._recovery_context()
        push = _handled()
        finalize = _handled()

        with self._push_patches(push=push, finalize=finalize):
            pushed = recovery._retry_recovery_push(
                context, fixtures._snapshot(ahead=1),
            )

        self.assertTrue(pushed)
        self.assertEqual(
            push.call_args.args,
            (context.spec, fixtures.WORKTREE, fixtures.BRANCH),
        )
        # The lease pins the remote to the pre-rebase anchor, so a PR head
        # that moved out of band rejects the push instead of being clobbered.
        self.assertEqual(
            push.call_args.kwargs.get("force_with_lease"),
            fixtures.PRE_REBASE_SHA,
        )
        self.assertEqual(
            finalize.call_args.kwargs.get("method"), PUSHED_METHOD,
        )
        self.assertEqual(
            finalize.call_args.kwargs.get("local_head"),
            fixtures.RECOVERED_SHA,
        )

    def test_dirty_worktree_parks_without_pushing(self) -> None:
        push = MagicMock()
        park = _handled()

        with self._push_patches(push=push, dirty=LEFTOVERS):
            with patch.object(outcomes, "_park_dirty_recovery", park):
                parked = recovery._retry_recovery_push(
                    fixtures._recovery_context(), fixtures._snapshot(ahead=1),
                )

        # Uncommitted edits mean the recovered head is not what a push would
        # publish, so the leftovers are reported before anything leaves.
        self.assertTrue(parked)
        self.assertEqual(park.call_args.args[2], list(LEFTOVERS))
        push.assert_not_called()

    def test_rejected_push_parks(self) -> None:
        finalize = MagicMock()
        park = _handled()

        with self._push_patches(
            push=MagicMock(return_value=False), finalize=finalize,
        ):
            with patch.object(outcomes, "_park_failed_recovery_push", park):
                parked = recovery._retry_recovery_push(
                    fixtures._recovery_context(), fixtures._snapshot(ahead=1),
                )

        self.assertTrue(parked)
        park.assert_called_once()
        finalize.assert_not_called()

    @contextlib.contextmanager
    def _push_patches(self, *, push, finalize=None, dirty=()):
        with contextlib.ExitStack() as stack:
            stack.enter_context(
                patch.object(
                    verification_probes,
                    DIRTY_FILES,
                    MagicMock(return_value=list(dirty)),
                ),
            )
            stack.enter_context(
                patch.object(authentication, PUSH_BRANCH, push),
            )
            stack.enter_context(
                patch.object(
                    persistence,
                    FINALIZE_HELPER,
                    finalize or _handled(),
                ),
            )
            yield


if __name__ == "__main__":
    unittest.main()
