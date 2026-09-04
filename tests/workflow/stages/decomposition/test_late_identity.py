# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a settled `single` records about the CHANGE it accepted.

The exemption beside it names one commit and only it, so this is the whole of
what says what that commit contributed -- and the retirement a few steps
behind the verdict takes the frozen pair off the record for good. Four things
are pinned down here: the pair it is derived from, the write it rides, what a
reading nobody could take leaves behind, and what such a settlement does with
an identity an earlier candidate left on the same comment.
"""
from __future__ import annotations

import unittest
from types import MappingProxyType
from unittest.mock import patch

from orchestrator.git.measurement.models import FINGERPRINT_FORMAT
from orchestrator.workflow.stages.decomposition import (
    late_handback as _late_handback,
)
from orchestrator.workflow.stages.decomposition.late_models import (
    _LateDisposition,
)
from tests.workflow.stages.decomposition.late_settlement_support import (
    SINGLE_RUN,
    UNFINGERPRINTED,
    GuardedLateCase,
)
from tests.workflow.stages.decomposition.late_test_support import (
    BASE_SHA,
    CANDIDATE_SHA,
    CONTRIBUTION_DIGEST,
    DIGEST_LENGTH,
    IDENTITY_KEYS,
    KEYS,
    MERGED_SHA,
    OTHER_SHA,
    generation_state,
    late_generation,
)

# What an earlier candidate's settlement left on this issue: that commit
# exempted, and the identity of what IT contributed beside it, over a base
# this generation was never measured against.
_EARLIER_DIGEST = "1" * DIGEST_LENGTH

_EARLIER_IDENTITY = MappingProxyType({
    KEYS.exempt_sha: OTHER_SHA,
    KEYS.exempt_base_sha: MERGED_SHA,
    KEYS.exempt_candidate_sha: OTHER_SHA,
    KEYS.exempt_fingerprint: _EARLIER_DIGEST,
    KEYS.exempt_fingerprint_format: FINGERPRINT_FORMAT,
})


class AcceptedIdentityTest(GuardedLateCase, unittest.TestCase):
    """One accepted candidate, and what the record says it carried."""

    def test_the_frozen_pair_is_what_it_reads(self) -> None:
        # Read between the two commits the generation froze rather than
        # between whatever the checkout stands on and a base read now: the
        # worktree is writable for the whole of an adjudication, and the seam
        # answers naming the pair it was handed.
        self._decide(SINGLE_RUN)

        pinned = self._pinned()
        recorded = {key: pinned.get(key) for key in IDENTITY_KEYS}
        self.assertEqual(recorded, {
            KEYS.exempt_base_sha: BASE_SHA,
            KEYS.exempt_candidate_sha: CANDIDATE_SHA,
            KEYS.exempt_fingerprint: CONTRIBUTION_DIGEST,
            KEYS.exempt_fingerprint_format: FINGERPRINT_FORMAT,
        })

    def test_it_is_durable_before_the_handoff(self) -> None:
        # It rides the write that records the exemption, and the retirement
        # past the handoff is what drops the frozen pair. A tick that died in
        # between would otherwise leave an issue whose branch carries an
        # adjudicated change and whose record cannot say which change it was.
        stopped = patch.object(
            _late_handback, "_continued", side_effect=KeyboardInterrupt,
        )

        with stopped, self.assertRaises(KeyboardInterrupt):
            self._decide(SINGLE_RUN)

        pinned = self._pinned()
        self.assertEqual(pinned.get(KEYS.exempt_sha), CANDIDATE_SHA)
        self.assertEqual(
            pinned.get(KEYS.exempt_fingerprint), CONTRIBUTION_DIGEST,
        )

    def test_a_failed_reading_records_none(self) -> None:
        # A store that cannot hand back the content between the two commits
        # leaves nothing transferable, and takes nothing away: the exact
        # commit is exempt and the candidate is handed on as it would be.
        outcome = self._decide(SINGLE_RUN, worktree=UNFINGERPRINTED)

        self.assertEqual(outcome.disposition, _LateDisposition.SETTLED)
        pinned = self._pinned()
        self.assertEqual(pinned.get(KEYS.exempt_sha), CANDIDATE_SHA)
        for key in IDENTITY_KEYS:
            with self.subTest(key=key):
                self.assertNotIn(key, pinned)

    def test_a_prior_identity_is_not_left_behind(self) -> None:
        # The sequence a stale record would be believed in: an earlier
        # candidate settled with an identity, this one settles with none, and
        # a later verdict puts that earlier commit back on the exemption --
        # where the leftover fields would match it by name and hand back a
        # digest taken over a base nobody measured this candidate against.
        self.github.seed_state(
            self.issue.number,
            **generation_state(late_generation()),
            **_EARLIER_IDENTITY,
        )

        self._decide(SINGLE_RUN, worktree=UNFINGERPRINTED)

        pinned = self._pinned()
        self.assertEqual(pinned.get(KEYS.exempt_sha), CANDIDATE_SHA)
        for key in IDENTITY_KEYS:
            with self.subTest(key=key):
                self.assertNotIn(key, pinned)


if __name__ == "__main__":
    unittest.main()
