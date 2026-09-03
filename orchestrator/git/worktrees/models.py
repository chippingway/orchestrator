# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a scan of this host's per-issue artifacts found, and what it decided.

Data only, for both halves of the artifact domain and for the answer a
teardown over them owes. `IssueArtifacts` is one issue as one repository's
clone and worktrees root show it, and `ArtifactInventory` is the whole answer
a single scan gives; the scan that fills them lives in ``inventory``, the two
local reads under it in ``probes``, and the rules deciding which configured
repository a discovered branch belongs to in ``attribution``.

`ProbeAnswer` and `BranchTip` are what one fail-closed read of those artifacts
comes back with, and `RetentionReason`, `Retention`, `ProvenTip`, and
`ArtifactVerdict` are what a classification over them concludes. The reads
live in ``evidence``, the GitHub side of the same question in ``claims``, and
the classifier composing the two in ``eligibility``.

`ArtifactSurface`, `SurfaceOutcome`, `SurfaceResult`, and `ArtifactReclamation`
are the shape a teardown answers in once an eligible verdict has been spent:
one outcome per place an artifact had to be taken from, since a caller told
only that "something is left" would have to go and re-derive which part of the
issue is still standing.

The refusals are carried in the answer rather than logged and dropped because
of what a reader does with an absence: "this repository has no artifacts" and
"this repository could not be read" look identical in a list of issues, and a
caller acting on the first while holding the second acts on a host it never
saw. A retention is carried for the same reason one step on: "nothing kept
this artifact" and "the question could not be put" are one answer to a caller
that only asks whether it may delete.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from orchestrator import config


@dataclass(frozen=True)
class IssueArtifacts:
    """The orchestrator-owned artifacts one issue left in one repository.

    An issue is in a scan because its `issue-<n>` checkout still stands under
    the spec's worktrees root, because a branch in that clone's
    orchestrator-owned namespace names it, or because both do -- which is why
    either half may be empty. Never both: an entry with no checkout and no
    branch is an issue nothing on this host attests to, and the scan does not
    invent one.

    `branches` carries the names as they exist, so an issue that predates slug
    namespacing and one already migrated read the same way: the namespaced
    name first when it is there, then the legacy flat one. Two entries for one
    issue therefore cannot happen -- the two layouts are two names for the
    same issue, not two issues.
    """

    spec: config.RepoSpec
    issue_number: int
    worktree: Path | None
    branches: tuple[str, ...]


@dataclass(frozen=True)
class ArtifactInventory:
    """Every issue one scan attributed, and the repositories it would not answer for.

    `refused` names the slugs whose picture this scan does not stand behind:
    a ref store or worktrees root it could not read. Their issues are left out
    entirely rather than reported in part, because a partial list of one
    repository's artifacts is indistinguishable from a complete one and reads
    as the same fact. A caller that acts on absence -- nothing here, so
    nothing to adopt or clean up -- has to skip those repositories, and this
    field is how it knows which.

    `issues` is ordered by slug and then issue number, so two scans of an
    unchanged host produce equal answers.
    """

    issues: tuple[IssueArtifacts, ...]
    refused: tuple[str, ...]


class ProbeAnswer(StrEnum):
    """What one fail-closed local read established about an artifact.

    Three answers rather than two, because a caller about to reclaim
    something has to spend the third differently. `REFUTED` is the host
    saying no -- the tree carries changes, the checkout is on somebody
    else's branch -- and it is an established fact about the artifact.
    `UNREADABLE` is the host saying nothing at all: git could not be run, the
    repository would not answer, the exit status was one nothing here claims
    to understand. Collapsed into `REFUTED` it would read as an artifact that
    was inspected and found wanting, and collapsed into `CONFIRMED` it would
    reclaim work on the strength of a probe that never ran.
    """

    CONFIRMED = "confirmed"
    REFUTED = "refuted"
    UNREADABLE = "unreadable"


@dataclass(frozen=True)
class BranchTip:
    """The commit one ref read resolved, or the way it did not resolve.

    `sha` carries a value under `CONFIRMED` and is empty under the other two,
    so a caller that reads it without asking `answer` first measures against
    an empty string rather than against a commit -- which every git probe
    then refuses, since the empty revision names nothing.

    `REFUTED` is the ref not being there, which for a branch this scan
    reported a moment ago means it has since been deleted; `UNREADABLE` is
    the read that could not say either way.
    """

    answer: ProbeAnswer
    sha: str = ""


class RetentionReason(StrEnum):
    """Why one candidate is kept rather than reclaimed.

    Every member names something an operator can go and look at, because a
    retention that repeats every tick is one somebody has to be able to
    settle: which read failed, which artifact carries what, which claim on
    GitHub is still open. A single "not eligible" would say only that the
    orchestrator will not touch it, and never why.

    The three families the classifier fails closed on are all here and stay
    apart. What was ASKED and answered no -- an open pull request, a dirty
    tree, a tree hiding files its own rules cover, commits nothing accounts
    for -- is a fact about the artifact. What could not be asked -- an issue,
    a pinned comment, a pull-request lookup, a git read -- is the absence of
    one. And what was asked and answered
    something nobody here can act on -- an issue in two workflow states at
    once, a pinned comment carrying something that is not a state, a checkout
    on a branch this issue never published -- is neither.

    The third family is kept apart from the second for what an operator does
    with it. A read that failed is transient and clears itself; a pinned
    comment holding a JSON array never clears, and an operator sent to check
    the API for it would find nothing wrong there.
    """

    ISSUE_UNREADABLE = "issue_unreadable"
    STATE_UNREADABLE = "state_unreadable"
    STATE_MALFORMED = "state_malformed"
    ISSUE_OPEN = "issue_open"
    NO_WORKFLOW_LABEL = "no_workflow_label"
    AMBIGUOUS_WORKFLOW_LABEL = "ambiguous_workflow_label"
    NON_TERMINAL_LABEL = "non_terminal_label"
    OPEN_PULL_REQUEST = "open_pull_request"
    PULL_REQUEST_UNREADABLE = "pull_request_unreadable"
    CHECKOUT_UNREADABLE = "checkout_unreadable"
    FOREIGN_CHECKOUT = "foreign_checkout"
    WORKTREE_UNREADABLE = "worktree_unreadable"
    WORKTREE_DIRTY = "worktree_dirty"
    WORKTREE_IGNORED = "worktree_ignored"
    BRANCH_UNREADABLE = "branch_unreadable"
    BASE_UNREADABLE = "base_unreadable"
    REMOTE_UNREADABLE = "remote_unreadable"
    REMOTE_DIVERGENCE = "remote_divergence"
    UNACCOUNTED_COMMITS = "unaccounted_commits"


@dataclass(frozen=True)
class Retention:
    """One reason a candidate is kept, and the thing that reason is about.

    The subject is carried beside the reason because the reason alone is not
    something anybody can act on: an issue can hold two branches and a
    checkout, and "a branch could not be read" sends an operator looking
    through all of them. It is the artifact's own name -- a branch, a
    checkout path, a pull request, a label -- rather than a rendered
    sentence, so a caller is free to report it as it likes.
    """

    reason: RetentionReason
    subject: str


@dataclass(frozen=True)
class ProvenTip:
    """One commit a classification cleared, and the artifact holding it.

    What an eligible verdict hands over to the teardown that spends it. Every
    proof a classification takes is about a COMMIT -- the base already carries
    it, a pull request that has ended published it -- and the artifact it was
    read from is standing on that commit and no other. A teardown holding only
    the artifact's name would delete whatever that name resolves to by the
    time it gets there, which is not necessarily what anybody proved: a branch
    an agent has committed onto since is the same branch by name and a
    different one by every test that cleared it.

    The subject is spelled the way a retention's is -- a branch by name, a
    checkout by path -- so a caller holding either half of the answer names
    the artifact the same way.
    """

    subject: str
    sha: str


@dataclass(frozen=True)
class ArtifactVerdict:
    """What one classification decided about one issue's artifacts.

    Eligibility is the absence of every reason to keep the artifacts, never
    a flag set beside them: a classifier that reached a failure it did not
    recognize adds a retention, and a verdict cannot come back eligible
    while holding one.

    The candidate is carried along so a caller acting on a verdict does not
    have to pair it back up with the scan that produced it -- and so the
    artifacts it acts on are exactly the ones the classification was about,
    rather than a re-derivation of them.
    """

    artifacts: IssueArtifacts
    retentions: tuple[Retention, ...] = ()
    proven: tuple[ProvenTip, ...] = ()

    @property
    def eligible(self) -> bool:
        """Whether every artifact reported for this issue may be reclaimed."""
        return not self.retentions


class ArtifactSurface(StrEnum):
    """The four places a finished issue leaves something to be taken from.

    Named beside the subject rather than folded into it, because two of them
    carry the same subject: a branch this host holds and the branch of that
    name on the remote are one name over two hosts, and a report saying only
    that `orchestrator/acme__widget/issue-7` is still there does not say
    which of them an operator has to go and look at.

    The first three are the artifacts themselves. `ANCHOR` is what a teardown
    can leave behind rather than something it found: the commit a checkout was
    standing on when it came down, kept under a ref of this orchestrator's own
    because nothing else names it. It is reported like the rest because the
    same thing is true of it -- until somebody settles it, this host is still
    holding something for that issue.
    """

    WORKTREE = "worktree"
    LOCAL_BRANCH = "local_branch"
    REMOTE_BRANCH = "remote_branch"
    ANCHOR = "anchor"


class SurfaceOutcome(StrEnum):
    """What one teardown step left on the surface it was for.

    `ABSENT` is a success, and it is kept apart from `CLEANED` for what it
    says about the pass rather than about the artifact: a surface with
    nothing on it to take is how every retry of a half-finished teardown
    reports the part that already went, and a caller reading it as a deletion
    would be counting one artifact twice.

    `FAILED` covers both a step that ran and did not finish and one this
    teardown would not take at all -- a tree written in since the proof, a
    branch that has moved. What separates them is in the log, because what a
    caller does with either is the same: leave the artifact where it is, and
    let the next pass find it again.
    """

    CLEANED = "cleaned"
    ABSENT = "absent"
    FAILED = "failed"


@dataclass(frozen=True)
class SurfaceResult:
    """What became of one artifact on one of the surfaces it lived on."""

    surface: ArtifactSurface
    subject: str
    outcome: SurfaceOutcome


@dataclass(frozen=True)
class ArtifactReclamation:
    """Every surface one teardown named, and what it left on each.

    Whole rather than filtered down to the failures: a caller holding only
    those cannot tell a surface this pass refused from one it never reached,
    and the second is what a teardown that ended early looks like.

    Nothing here is a retry list. A surface that failed is one whose artifact
    is still on this host or still on the remote, and the scan that found it
    once finds it again -- which is what carries an interrupted reclamation
    across a restart that no in-memory record would survive.
    """

    artifacts: IssueArtifacts
    surfaces: tuple[SurfaceResult, ...] = ()

    @property
    def settled(self) -> bool:
        """Whether every surface this teardown named is now clear."""
        return all(
            taken.outcome is not SurfaceOutcome.FAILED
            for taken in self.surfaces
        )
