# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The pinned fields a settlement an operator authorized leaves behind.

An oversized candidate publishes without a reading only where two records
name it: the exemption an adjudication's settlement wrote, and the terms an
operator authorized that publication on. Every stage whose tests put an
accepted commit in front of the size gate needs both, so they are spelled once
here rather than once per stage -- a seed carrying the exemption alone is the
LEGACY shape, and cases about that ask for it by name.
"""
from __future__ import annotations

from orchestrator.github import PinnedState
from orchestrator.workflow.late_split import (
    exemption as _exemption,
    overrides as _overrides,
)
from tests.workflow.repo_values import (
    CONTRIBUTION_DIGEST,
    MEASURED_BASE_SHA,
    MEASURED_CANDIDATE_SHA,
    SHA_LENGTH,
)

# What the accepted contribution fingerprints to, which is the digest the
# hermetic world answers with: a seed and a reading taken over the same pair
# have to agree, or a case about a record that MATCHES would be seeded with
# one that does not.
ACCEPTED_DIGEST = CONTRIBUTION_DIGEST

# The reading a human was shown when they authorized, and the ceiling it was
# counted against. Strictly past it, because a record at or under its own
# threshold describes a candidate the gate publishes untouched and reads back
# as no authorization at all.
AUTHORIZED_ADDITIONS = 9123
AUTHORIZED_THRESHOLD = 4000

# The comment the authorization was written in, which is what makes it
# attributable.
AUTHORIZING_COMMENT_ID = 5150


def _authorized_exemption(
    candidate_sha: str = MEASURED_CANDIDATE_SHA,
    base_sha: str = MEASURED_BASE_SHA,
    *,
    identity: bool = False,
) -> dict:
    """The pinned fields an authorized settlement of `candidate_sha` leaves.

    Written through the two owners rather than spelled as literals, so a seed
    is exactly what the settlement would have produced and a field this domain
    would refuse never reaches a test as though it had been recorded.

    The reading and the comment are the module's own constants rather than
    parameters: what a case varies is which commit the two records name, and
    nothing the gate asks turns on how large the authorized change was.

    `identity` adds the semantic record beside the exemption, which only the
    cases about a transfer need: the exact-SHA claim is what the gate reads,
    and every other case is about that.
    """
    seeded = PinnedState(data={})
    _exemption.record_exemption(seeded, candidate_sha)
    if identity:
        _exemption.record_semantic_identity(
            seeded,
            base_sha=base_sha,
            candidate_sha=candidate_sha,
            fingerprint=ACCEPTED_DIGEST,
        )
    _overrides.record_publication_override(
        seeded,
        _overrides.LateOversizedPublication(
            candidate_sha=candidate_sha,
            base_sha=base_sha,
            fingerprint=ACCEPTED_DIGEST,
            additions=AUTHORIZED_ADDITIONS,
            threshold=AUTHORIZED_THRESHOLD,
            comment_id=AUTHORIZING_COMMENT_ID,
        ),
    )
    return seeded.data


def _legacy_exemption(candidate_sha: str = MEASURED_CANDIDATE_SHA) -> dict:
    """The exemption an older binary wrote, with no gesture behind it.

    A `single` verdict used to record this on its own, so a live issue can
    carry it. The candidate it names goes to the ordinary cumulative gate.
    """
    seeded = PinnedState(data={})
    _exemption.record_exemption(seeded, candidate_sha)
    return seeded.data


def _damaged_authorization(candidate_sha: str = MEASURED_CANDIDATE_SHA) -> dict:
    """The same exemption beside an authorization nothing can read whole.

    A hand edit, a half-written crash, and an older scheme all reach the same
    place: a group short of a member it needs is no authorization, and the
    candidate is measured exactly as the legacy record's is.
    """
    seeded = _authorized_exemption(candidate_sha)
    seeded.pop(_overrides.LATE_OVERRIDE_FINGERPRINT, None)
    return seeded


def _authorize_command(candidate_sha: str = MEASURED_CANDIDATE_SHA) -> str:
    """The whole comment an operator publishes a parked candidate with."""
    return f"/orchestrator authorize-oversized {candidate_sha}"


# A commit that types as one and that no record on these seeds names.
STRANGER_SHA = "d" * SHA_LENGTH
