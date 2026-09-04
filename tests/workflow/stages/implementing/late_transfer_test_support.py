# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The one rewrite the transfer's tests grant or refuse a permit for.

A squash-on-approval of the exact commit an adjudication accepted, described
once: the pinned comment that records the verdict, the evidence the squash
hands in, the publication the gate froze, and the world the two readings the
permit spends -- the checkout and the two fingerprints -- answer in. A case
about one refusal seeds exactly that one and leaves the rest ordinary.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from orchestrator import config
from orchestrator.git.measurement.models import (
    ContributionFingerprint,
    FingerprintFailure,
    FrozenCommit,
    MeasurementFailure,
)
from orchestrator.git.verification.probes import _WorktreeStatus
from orchestrator.workflow.late_split import (
    exemption as _exemption,
    rewrites as _rewrites,
)
from orchestrator.workflow.stages.implementing import (
    late_records as _records,
    state as _state,
)
from orchestrator.workflow.state import WorkflowLabel
from tests.support.fakes import FakeGitHubClient, FakeLabel, make_issue
from tests.workflow.git_owners import seam_patch

ISSUE_NUMBER = 42
PR_NUMBER = 77
SOURCE_STAGE = WorkflowLabel.VALIDATING

SHA_LENGTH = 40
DIGEST_LENGTH = 64

# The commit a human adjudicated, the base it was measured over, and the
# object the squash replaced it with over that same base.
ACCEPTED_SHA = "a" * SHA_LENGTH
MERGE_BASE_SHA = "b" * SHA_LENGTH
REWRITTEN_SHA = "c" * SHA_LENGTH
STRANGER_SHA = "d" * SHA_LENGTH

# A whole object id this issue has nothing to do with: another commit that
# types exactly as any of the four above, which is what a hand edit can move a
# recorded end to without the reader refusing it.
FOREIGN_SHA = "7" * SHA_LENGTH

# The head the pull request is standing on, which is what the force-push is
# leased against. Deliberately NOT the commit the squash collapsed: the entry
# admits a tip a durable record says this issue's own push put there, so the
# two are separate facts and a fixture that spelled them alike would let one
# stand in for the other unnoticed.
LEASED_SHA = "9" * SHA_LENGTH

# What the accepted contribution fingerprints to, and what an unequal one does.
ACCEPTED_DIGEST = "e" * DIGEST_LENGTH
OTHER_DIGEST = "f" * DIGEST_LENGTH

WORKTREE = Path("/tmp/orchestrator-test-late-transfer")

SPEC = config.RepoSpec(
    slug="chippingway/orchestrator",
    target_root=Path("/tmp/orchestrator-test-target-root"),
    base_branch="main",
)

# The seams a permit spends, named on the owners that define them.
PROVE_CANDIDATE = "_prove_candidate_commit"
WORKTREE_STATUS = "_worktree_status"
FINGERPRINT = "_fingerprint_contribution"

CLEAN = _WorktreeStatus(readable=True)

# The revision a checkout's own head is named by. Every other revision the
# permit asks about is a commit some record names by id.
_HEAD = "HEAD"



def rewrite(**overrides) -> _rewrites.LateRewrite:
    """The evidence the squash hands in, with any one term replaced."""
    return _rewrites.LateRewrite(**{
        "kind": _rewrites.LateRewriteKind.SQUASH,
        "from_sha": ACCEPTED_SHA,
        "from_base_sha": MERGE_BASE_SHA,
        "to_sha": REWRITTEN_SHA,
        "to_base_sha": MERGE_BASE_SHA,
        "pr_number": PR_NUMBER,
        "source_stage": SOURCE_STAGE,
        "lease": LEASED_SHA,
        **overrides,
    })


def entry(**overrides) -> _records._PublicationEntry:
    """The publication the gate froze before the rewrite was measured."""
    return _records._PublicationEntry(**{
        "stage": SOURCE_STAGE,
        "pr_number": PR_NUMBER,
        "published_sha": LEASED_SHA,
        **overrides,
    })


@dataclass(frozen=True)
class Adjudicated:
    """The issue a settled `single` verdict left, and what it was recorded on."""

    github: FakeGitHubClient
    issue: object
    state: object


def adjudicated(
    *,
    identity: bool = True,
    digest: str = ACCEPTED_DIGEST,
    base: str = MERGE_BASE_SHA,
    labels: tuple | None = None,
) -> Adjudicated:
    """The pinned comment a settled `single` verdict leaves behind.

    `identity=False` is the legacy shape: a comment written before the
    semantic record existed, or one whose fingerprint could not be taken, so
    only the exact commit is exempt.

    `base` is the pair's other end, replaceable because it is the one field a
    hand edit can move without the record refusing to read back: a whole
    object id naming some other commit types exactly as the frozen base does.

    `labels` is what the issue reads back as when the transfer re-fetches it,
    seeded on the issue rather than written through the client because the
    relabel that put the stage there happened long before this tick.
    """
    github = FakeGitHubClient()
    issue = make_issue(ISSUE_NUMBER)
    named = (str(SOURCE_STAGE),) if labels is None else labels
    issue.labels.extend(FakeLabel(name) for name in named)
    github.add_issue(issue)
    github.seed_state(ISSUE_NUMBER, **{_state._PR_NUMBER: PR_NUMBER})
    state = github.read_pinned_state(issue)
    _exemption.record_exemption(state, ACCEPTED_SHA)
    if identity:
        _exemption.record_semantic_identity(
            state,
            base_sha=base,
            candidate_sha=ACCEPTED_SHA,
            fingerprint=digest,
        )
    github.write_pinned_state(issue, state)
    return Adjudicated(github=github, issue=issue, state=state)


def spent(state) -> None:
    """The comment a settled transfer leaves, written here by hand.

    Nothing in this build spends a permission -- the receipt that would is
    another owner's write -- so a `published` record reaches these readers
    only the way a hand edit or some other build would put it there. Which is
    the whole reason the phase is read at all: what a record binds to changes
    with it, and a reader that ignored the phase would ask its question of the
    wrong end of the rewrite.

    Three fields, because that is what "spent" means on the comment: the
    exemption and the identity beside it describe the pair the rewrite
    produced, and the phase says the move is done.
    """
    _exemption.record_exemption(state, REWRITTEN_SHA)
    _exemption.record_semantic_identity(
        state,
        base_sha=MERGE_BASE_SHA,
        candidate_sha=REWRITTEN_SHA,
        fingerprint=ACCEPTED_DIGEST,
    )
    state.set(
        _rewrites.LATE_REWRITE_PHASE, str(_rewrites.LateRewritePhase.PUBLISHED),
    )


def gate(github, issue, state, **overrides) -> _records._Gate:
    """The subject one gate call taken past publication is about."""
    return _records._Gate(**{
        "gh": github,
        "spec": SPEC,
        "issue": issue,
        "state": state,
        "worktree": WORKTREE,
        "reconciling": True,
        "candidate": REWRITTEN_SHA,
        "entry": entry(),
        "rewrite": rewrite(),
        **overrides,
    })


def _over(base_sha: str) -> str:
    """The digest a pair read over this base contributes, unseeded.

    One answer for the merge base the rewrite really sits on and another for
    every other end, since a contribution is what a candidate adds over ITS
    base and two bases are two contributions.
    """
    return ACCEPTED_DIGEST if base_sha == MERGE_BASE_SHA else OTHER_DIGEST


class Readings:
    """The three readings a permit spends, and what each answers this case.

    One controller installed once rather than a patch per case, because the
    refusals are a family: every one of them is the ordinary world with a
    single reading replaced, and a case that re-entered the whole patch set to
    move one of them would stack doubles over doubles.

    The fingerprints are keyed on the CANDIDATE rather than seeded as a
    sequence, so a case naming one side says which side it means: the accepted
    contribution and the rewritten one are read in order, and a positional
    seed would silently swap them if that order ever changed.

    What a case seeds nothing for still depends on the BASE, because that is
    what a contribution is: only the merge base both sides of this rewrite are
    read over answers with the digest the adjudication recorded, and any other
    end answers with a different one. Without that a hand-edited base would
    fingerprint identically to the frozen one and every reading of it would
    agree by construction.

    `absent` is the other half of the ordinary world being ordinary: every
    commit the evidence names is an object this host holds unless a case says
    otherwise.
    """

    def __init__(self) -> None:
        self.head = FrozenCommit(sha=REWRITTEN_SHA)
        self.tree = CLEAN
        self.digests: dict = {}
        self.absent: set = set()

    def stands_on(self, head) -> None:
        """Put the checkout on this commit, or on this failed proof."""
        self.head = head if isinstance(head, FrozenCommit) else FrozenCommit(
            sha=head,
        )

    def proved(self, worktree, revision) -> FrozenCommit:
        """What one revision the permit names proves to.

        Two answers behind one seam, because the permit asks it two different
        questions: what the checkout stands on, and whether a commit the
        EVIDENCE names is an object this host still holds. A revision a case
        put in `absent` answers the way one made on another host does -- it
        resolves to itself and will not peel -- which is the whole reason a
        whole-looking id is not proof of anything.
        """
        if revision == _HEAD:
            return self.head
        if revision in self.absent:
            return FrozenCommit(
                sha=revision, failure=MeasurementFailure.CANDIDATE_ABSENT,
            )
        return FrozenCommit(sha=revision)

    def status(self, worktree) -> _WorktreeStatus:
        """What `git status` said about the tree a push would publish from."""
        return self.tree

    def fingerprint(
        self, worktree, base_sha: str, candidate_sha: str,
    ) -> ContributionFingerprint:
        """What one pair contributes, as the digest naming it."""
        answered = self.digests.get(candidate_sha) or _over(base_sha)
        if isinstance(answered, FingerprintFailure):
            return ContributionFingerprint(
                base_sha=base_sha, candidate_sha=candidate_sha,
                failure=answered,
            )
        return ContributionFingerprint(
            base_sha=base_sha, candidate_sha=candidate_sha, digest=answered,
        )


def readings(fixture) -> Readings:
    """Install the ordinary world a transfer is granted in, and hand it back.

    The checkout stands on the rewritten commit over a provably clean tree,
    and both contributions fingerprint to the digest the adjudication
    recorded, so a case that touches nothing is a permit and a case about a
    refusal moves exactly one answer.
    """
    answers = Readings()
    fixture.enterContext(seam_patch(PROVE_CANDIDATE, answers.proved))
    fixture.enterContext(seam_patch(WORKTREE_STATUS, answers.status))
    fixture.enterContext(seam_patch(FINGERPRINT, answers.fingerprint))
    return answers
