# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The squash of a commit a human adjudicated, against a real repository.

The one case the exemption cannot answer on its own. A `single` verdict
accepts an oversized candidate and names that exact commit; the reviewer then
approves the pull request and the squash collapses it into an object nobody
ruled on. Measured like any other candidate it is oversized again -- the same
lines, over the same base -- and the last push before the merge button would
route the work back into adjudication.

Every reading here is the real one: a real repository, a real squash, and the
canonical fingerprint taken over the actual objects on both sides of the
rewrite. Only the authenticated push is stood in for, and only the remote-side
base freeze, which these fixtures have no token to reach.

Both durable writes one transferring squash makes are read here, and they are
read at the moment each lands rather than once the tick is over: the grant
moves nothing and the receipt behind it is what carries the verdict over, so
a case that only looked at the end could not tell the two apart -- nor tell
either from a tick that lost one of them.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from orchestrator.git.measurement import fingerprint as _fingerprint
from orchestrator.workflow.late_split import (
    exemption as _exemption,
    rewrites as _rewrites,
)
from tests.git.publication import squash_git_support as squash_support
from tests.git.publication.squash_gate_support import (
    PublicationSeed,
    _squash_gate,
)

MAX_ADDED_LINES = "MAX_ADDED_LINES"

# The fixture's topic branch adds one line per commit over three commits, so
# a ceiling below that is what an adjudicated candidate was oversized against.
ADDED_LINES = 3
PAST_THE_CEILING = ADDED_LINES - 1

LABEL_DECOMPOSING = "workflow:decomposing"

KEY_CANDIDATE_SHA = "late_candidate_sha"
# The receipt a landed gated push leaves, which is what the settlement that
# carries the exemption over rides.
KEY_PUBLISHED_SHA = "implementing_published_sha"
# The debt the grant's own write carries beside the permission: the commit
# still owed a push, and the head that push is leased against.
KEY_APPROVED_SHA = "late_approved_sha"
KEY_APPROVED_LEASE = "late_approved_lease"

# A whole digest that is not the one the accepted contribution really takes,
# which is what a hand-edited or stale semantic record reads back as.
DIGEST_LENGTH = 64
UNRECORDED_DIGEST = "0" * DIGEST_LENGTH

# The client call every durable record of this tick goes through, which is
# what a case standing in for an outage replaces.
PINNED_WRITE = "write_pinned_state"


class _RecordsEachWrite:
    """What the pinned comment said at each durable write of one squash.

    The grant is the FIRST write a transferring squash makes, and what a crash
    could take is everything a later one would have added -- so the question a
    case has to be able to ask is what that write alone left behind, not what
    the comment says once the tick has finished.
    """

    def __init__(self, gate) -> None:
        self.durable: list[dict] = []
        self._gate = gate
        self._writes = gate.gh.write_pinned_state

    def __call__(self, issue, state):
        written = self._writes(issue, state)
        self.durable.append(dict(self._gate.gh.pinned_data(issue.number)))
        return written

    def held(self):
        """Record every write the client makes, for the duration of one run."""
        return patch.object(self._gate.gh, PINNED_WRITE, self)


class _RefusesOneWrite:
    """A comment GitHub refuses at one point in the tick and takes otherwise.

    The narrow outage, and the one that says WHERE a lost write is handled.
    Refusing the FIRST loses only the transfer's grant, so a tick that carries
    on has the ordinary size gate to fall back to and a tick that lets the
    exception out has nothing. Refusing the SECOND loses the receipt behind a
    push that already landed, which is the one window where the branch must be
    left exactly where the rewrite put it.
    """

    def __init__(self, gate, ordinal: int = 1) -> None:
        self.writes = 0
        self._ordinal = ordinal
        self._writes = gate.gh.write_pinned_state

    def __call__(self, issue, state):
        self.writes += 1
        if self.writes == self._ordinal:
            raise RuntimeError("pinned comment rejected")
        return self._writes(issue, state)

    def held(self, gate):
        """Refuse the write at this point of one run, and take the rest."""
        return patch.object(gate.gh, PINNED_WRITE, self)


class _AdjudicatedSquashMixin:
    """One issue whose exemption names the commit the squash is about to eat."""

    def _adjudicated(self, *, digest: str | None = None, base: str = ""):
        """The gate for an issue whose exemption names the pre-squash head.

        The pinned comment is exactly what a settled `single` verdict leaves:
        the accepted commit, and the canonical digest of what it contributes
        over the base the adjudication was measured from.

        `base` replaces that end, which is the one field of the record a hand
        edit can move without the reader refusing it: another commit in this
        repository types exactly as the frozen base does.
        """
        gate = _squash_gate(self, PublicationSeed())
        accepted = self._head_sha()
        _exemption.record_exemption(gate.state, accepted)
        _exemption.record_semantic_identity(
            gate.state,
            base_sha=base or self._base_sha(),
            candidate_sha=accepted,
            fingerprint=digest or self._contribution(accepted),
        )
        gate.gh.write_pinned_state(gate.issue, gate.state)
        return gate

    def _one_commit_back(self) -> str:
        """A real commit in this repository that is not the frozen base."""
        return squash_support.run_git(
            "rev-parse", "HEAD~1", cwd=self.work,
        ).strip()

    def _contribution(self, candidate: str) -> str:
        """What that candidate really contributes over the frozen base."""
        fingerprinted = _fingerprint._fingerprint_contribution(
            self.work, self._base_sha(), candidate,
        )
        self.assertTrue(fingerprinted.is_fingerprinted)
        return fingerprinted.digest

    def _squashes(self, gate, **run_options):
        """Squash under a ceiling the accepted candidate is already past."""
        return self._squash(
            publication=PublicationSeed(gate=gate),
            **{MAX_ADDED_LINES: PAST_THE_CEILING},
            **run_options,
        )

    def _pinned(self, gate) -> dict:
        """The pinned comment as it durably stands."""
        return gate.gh.pinned_data(gate.issue.number)

    def _assert_exempts(self, gate, commit: str) -> None:
        """The commit the comment durably exempts, whatever else moved."""
        self.assertEqual(
            self._pinned(gate)[_exemption.LATE_EXEMPT_SHA], commit,
        )


class SquashedExemptionRealGitTest(
    _AdjudicatedSquashMixin,
    squash_support.SquashGitFixtureMixin,
    unittest.TestCase,
):
    """The transfer an equivalent squash earns, and what one write puts down."""

    def test_an_equivalent_squash_publishes(self) -> None:
        # The squash has the same tree over the same base, so it contributes
        # the change a human already ruled on. Without the transfer this is
        # the oversized reading that routes an approved pull request back to
        # the adjudication.
        gate = self._adjudicated()

        squash_run = self._squashes(gate)

        self.assertTrue(squash_run.success)
        self.assertFalse(squash_run.held)
        self.assertEqual(
            squash_run.push_mock.call_args.kwargs["revision"],
            self._head_sha(),
        )
        self.assertNotIn(
            (gate.issue.number, LABEL_DECOMPOSING), gate.gh.label_history,
        )

    def test_the_permission_leaves_the_exemption_put(self) -> None:
        # The grant records what licenses the push and moves nothing, and the
        # only moment that is readable is its own write: the verdict stays on
        # the commit a human ruled on until a receipt for a landed push spends
        # the permission, so a push that never lands leaves no verdict on an
        # object only this host has.
        gate = self._adjudicated()
        accepted = self._head_sha()
        writes = _RecordsEachWrite(gate)

        with writes.held():
            self._squashes(gate)

        granted = writes.durable[0]
        self.assertEqual(granted[_exemption.LATE_EXEMPT_SHA], accepted)
        self.assertEqual(
            granted[_rewrites.LATE_REWRITE_PHASE],
            str(_rewrites.LateRewritePhase.AUTHORIZED),
        )

    def test_the_receipt_carries_the_exemption_over(self) -> None:
        # The push landed, so the commit the verdict is about to name is one
        # the pull request really carries -- which is the whole of what makes
        # the move safe, and why it rides this write and no earlier one.
        gate = self._adjudicated()

        self._squashes(gate)

        squashed = self._head_sha()
        self._assert_exempts(gate, squashed)
        durable = gate.gh.read_pinned_state(gate.issue)
        identity = _exemption.read_semantic_identity(durable)
        self.assertEqual(identity.candidate_sha, squashed)
        authorized = _rewrites.read_rewrite_authorization(durable)
        self.assertEqual(
            authorized.phase, _rewrites.LateRewritePhase.PUBLISHED,
        )
        self.assertEqual(
            self._pinned(gate)[KEY_PUBLISHED_SHA], squashed,
        )

    def test_a_refused_receipt_leaves_the_verdict_put(self) -> None:
        # The window the settlement closes, read from the side that can still
        # be wrong: the branch is on the remote and the write that would say
        # so was refused. Nothing may be durable there -- least of all a
        # verdict, which would name a commit no receipt accounts for. The
        # branch is left on the squash the remote now has, and the permission
        # stands for the reconciliation that republishes it as a leased no-op.
        gate = self._adjudicated()
        accepted = self._head_sha()
        refusing = _RefusesOneWrite(gate, ordinal=2)

        with refusing.held(gate), self.assertRaises(RuntimeError):
            self._squashes(gate)

        self.assertNotEqual(self._head_sha(), accepted)
        self._assert_exempts(gate, accepted)
        pinned = self._pinned(gate)
        self.assertEqual(
            pinned[_rewrites.LATE_REWRITE_PHASE],
            str(_rewrites.LateRewritePhase.AUTHORIZED),
        )
        self.assertNotIn(KEY_PUBLISHED_SHA, pinned)

    def test_the_authorization_names_both_ends(self) -> None:
        gate = self._adjudicated()
        accepted = self._head_sha()

        self._squashes(gate)

        authorized = _rewrites.read_rewrite_authorization(
            gate.gh.read_pinned_state(gate.issue),
        )
        self.assertEqual(authorized.rewrite.from_sha, accepted)
        self.assertEqual(authorized.rewrite.to_sha, self._head_sha())
        self.assertEqual(authorized.rewrite.lease, accepted)
        self.assertEqual(
            authorized.rewrite.kind, _rewrites.LateRewriteKind.SQUASH,
        )

    def test_the_grants_first_write_owes_the_push(self) -> None:
        # The crash boundary the grant opens, read at the only moment that
        # settles it: the FIRST durable write the squash makes. By then the
        # branch is one commit, so a comment that explains that commit and
        # does not say a push is owed for it is one the next squash reads as
        # nothing to squash -- reported as success, never measured, never
        # pushed. Both halves land together or the window is real.
        gate = self._adjudicated()
        accepted = self._head_sha()
        writes = _RecordsEachWrite(gate)

        with writes.held():
            self._squashes(gate)

        first = writes.durable[0]
        self.assertEqual(first[KEY_APPROVED_SHA], self._head_sha())
        self.assertEqual(first[KEY_APPROVED_LEASE], accepted)
        self.assertEqual(
            first[_rewrites.LATE_REWRITE_PHASE],
            str(_rewrites.LateRewritePhase.AUTHORIZED),
        )

    def test_a_refused_push_drops_the_permission(self) -> None:
        # The rollback puts the branch back on the accepted commit, which is
        # the commit the exemption never left -- so what the reset owes is
        # dropping the permission granted for an object on no branch.
        gate = self._adjudicated()
        accepted = self._head_sha()

        squash_run = self._squashes(gate, push_result=False)

        self.assertFalse(squash_run.success)
        self.assertEqual(self._head_sha(), accepted)
        pinned = self._pinned(gate)
        self._assert_exempts(gate, accepted)
        self.assertNotIn(_rewrites.LATE_REWRITE_PHASE, pinned)
        identity = _exemption.read_semantic_identity(
            gate.gh.read_pinned_state(gate.issue),
        )
        self.assertEqual(identity.candidate_sha, accepted)


class UntransferredSquashRealGitTest(
    _AdjudicatedSquashMixin,
    squash_support.SquashGitFixtureMixin,
    unittest.TestCase,
):
    """The squashes that earn no transfer, and are measured as they always were."""

    def test_an_unrecorded_digest_is_adjudicated(self) -> None:
        # The recorded digest is what proves the identity belongs to the pair
        # the evidence claims. One that does not is a record nothing may
        # transfer under, so the squash is measured like any other candidate.
        gate = self._adjudicated(digest=UNRECORDED_DIGEST)

        squash_run = self._squashes(gate)

        self.assertTrue(squash_run.held)
        self.assertIn(
            (gate.issue.number, LABEL_DECOMPOSING), gate.gh.label_history,
        )
        self.assertEqual(
            self._pinned(gate)[KEY_CANDIDATE_SHA], self._head_sha(),
        )

    def test_a_hand_edited_base_is_adjudicated(self) -> None:
        # The record's own base is what the accepted contribution is read
        # over. Moved to another commit in this repository it still types, and
        # the digest beside it then describes a pair this issue never
        # adjudicated -- so the record fails to prove itself and the squash is
        # measured like any other candidate.
        gate = self._adjudicated(base=self._one_commit_back())

        self.assertTrue(self._squashes(gate).held)
        self.assertIn(
            (gate.issue.number, LABEL_DECOMPOSING), gate.gh.label_history,
        )

    def test_a_legacy_exemption_is_adjudicated(self) -> None:
        # An issue whose pinned comment predates the semantic record exempts
        # the exact commit and can prove nothing about what it contributes.
        gate = _squash_gate(self, PublicationSeed())
        accepted = self._head_sha()
        _exemption.record_exemption(gate.state, accepted)
        gate.gh.write_pinned_state(gate.issue, gate.state)

        self.assertTrue(self._squashes(gate).held)
        pinned = self._pinned(gate)
        self._assert_exempts(gate, accepted)
        self.assertEqual(pinned[KEY_CANDIDATE_SHA], self._head_sha())

    def test_unadjudicated_work_is_still_measured(self) -> None:
        # The exemption names one commit and only it. An issue that never
        # earned one gets the reading it always did.
        gate = _squash_gate(self, PublicationSeed())

        self.assertTrue(self._squashes(gate).held)
        self.assertIn(
            (gate.issue.number, LABEL_DECOMPOSING), gate.gh.label_history,
        )


class LostGrantRealGitTest(
    _AdjudicatedSquashMixin,
    squash_support.SquashGitFixtureMixin,
    unittest.TestCase,
):
    """What a refused GRANT leaves, with the branch already collapsed.

    A squash has replaced the branch's commits with one by the time that write
    is attempted, so what losing it may not do is end the tick in an
    exception: the caller would never reach the decision about the rewrite it
    is holding. The permit is refused where the write is lost instead, and the
    rewritten commit falls through to the ordinary cumulative gate.
    """

    def test_a_lost_grant_falls_through_to_the_gate(self) -> None:
        # The grant's own write is handled where it happens: the permit is
        # refused, the staged move is put back, and the tick carries on into
        # the ordinary cumulative reading rather than ending in an exception
        # the caller could not roll its rewrite back for.
        gate = self._adjudicated()
        accepted = self._head_sha()
        refusing = _RefusesOneWrite(gate)

        with refusing.held(gate):
            squash_run = self._squashes(gate)

        self.assertTrue(squash_run.held)
        self.assertIsNone(squash_run.error)
        self.assertIn(
            (gate.issue.number, LABEL_DECOMPOSING), gate.gh.label_history,
        )
        pinned = self._pinned(gate)
        self.assertEqual(pinned[KEY_CANDIDATE_SHA], self._head_sha())
        # The move the refused write staged is put back, so what the comment
        # exempts is still the commit the adjudication accepted.
        self._assert_exempts(gate, accepted)
        self.assertNotIn(_rewrites.LATE_REWRITE_PHASE, pinned)
