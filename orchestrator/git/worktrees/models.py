# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a scan of this host's per-issue artifacts found, and what it decided.

Data only, for the artifact domain's three halves: what a scan found, what a
classification over it concluded, and what a maintenance pass spending that
conclusion did. `IssueArtifacts` is one issue as one repository's clone and
worktrees root show it, and `ArtifactInventory` is the whole answer a single
scan gives; the scan that fills them lives in ``inventory``, the two local
reads under it in ``probes``, and the rules deciding which configured
repository a discovered branch belongs to in ``attribution``.

`ProbeAnswer` and `BranchTip` are what one fail-closed read of those artifacts
comes back with, and `RetentionReason`, `Retention`, `ProvenTip`, and
`ArtifactVerdict` are what a classification over them concludes. The reads
live in ``evidence``, the GitHub side of the same question in ``claims``, and
the classifier composing the two in ``eligibility``.

`CandidateLayout`, `MaintenanceCandidate`, and `MaintenanceScan` are what the
discovery a maintenance pass runs on hands back -- the local scan widened by
what the remote still carries, in ``discovery`` -- and `MaintenanceOutcome`,
`MaintenanceReason`, and `MaintenanceResult` are what one pass over a candidate
answers with, in ``maintenance``. The outcome and the reason are two fields
rather than one because they are read by two different readers: a count of what
a pass did is taken off the first, and what to go and look at off the second.

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

    An issue is in a scan because an `issue-<n>` checkout of it still stands,
    because a branch in that clone's orchestrator-owned namespace names it, or
    because both do -- which is why either half may be empty. Never both: an
    entry with no checkout and no branch is an issue nothing on this host
    attests to, and the scan does not invent one.

    Both halves are tuples, and for the same reason: this orchestrator has
    published an issue under two layouts, and a host that was running across
    the migration can be holding both at once. `branches` carries the
    slug-namespaced name and the legacy flat one; `worktrees` carries the
    checkout under the spec's own root and the legacy one directly under
    `WORKTREES_DIR`. Each is ordered current-first, which is the order a
    teardown takes them in.

    Two entries for one issue therefore cannot happen -- the layouts are
    several names for one issue, not several issues.
    """

    spec: config.RepoSpec
    issue_number: int
    worktrees: tuple[Path, ...]
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


class CandidateLayout(StrEnum):
    """Which of the layouts this orchestrator has published a candidate under.

    Named on the candidate rather than worked out again by every reader,
    because it is the one thing about a candidate that says how it came to
    exist. `CURRENT` is the slug-namespaced branch this orchestrator publishes
    now and the per-repository checkout beside it; `LEGACY` is the flat
    `orchestrator/issue-<n>` an issue in flight when namespacing landed is
    still on; `MIXED` is an issue carrying both names at once, which a
    migration leaves behind and which no single derivation would ever produce.

    `REMOTE_ONLY` is where the artifact is rather than what it is called, and
    it wins over the other three when nothing local is left: a candidate this
    host holds no checkout and no branch for is one an operator has nothing to
    look at here for, whichever name the remote's copy carries.
    """

    CURRENT = "current"
    LEGACY = "legacy"
    REMOTE_ONLY = "remote_only"
    MIXED = "mixed"


@dataclass(frozen=True)
class MaintenanceCandidate:
    """One issue's artifacts, and the layout they were published under.

    The pair rather than the artifacts alone, because the layout is a reading
    taken where both halves of the discovery were still in hand -- what the
    clone holds and what the remote does -- and nothing downstream can
    reconstruct it: by the time a pass has finished, the branch that said the
    candidate was remote-only is gone.
    """

    artifacts: IssueArtifacts
    layout: CandidateLayout


@dataclass(frozen=True)
class MaintenanceScan:
    """Every candidate a maintenance discovery found, and what it will not answer for.

    `refused` carries the same fact the scan's own does, one step wider: a
    repository whose checkout root, ref store, or remote listing could not be
    read is left out entirely rather than reported in part, because a partial
    list of what a repository still holds reads exactly like a complete one.

    `candidates` is ordered by slug and then issue number, so two discoveries
    of an unchanged host and remote produce equal answers.
    """

    candidates: tuple[MaintenanceCandidate, ...]
    refused: tuple[str, ...]


class MaintenanceOutcome(StrEnum):
    """What one maintenance pass over one candidate did.

    Three answers, because a caller counting them has to keep apart the two
    ways a candidate survives a pass. `RETAINED` is the pass deciding not to
    touch it -- every gate in front of the mutation is a decision of that kind,
    and one repeating every pass is a candidate somebody has to settle by hand.
    `FAILED` is the pass trying and being refused: git would not remove the
    checkout, the remote would not accept the delete. Collapsed together, an
    operator could not tell a host that is behaving from one that is not.

    `CLEANED` is every artifact this candidate was found holding now gone from
    the host and the remote, absences included: a pass that found a branch
    already deleted has nothing left to do about it, and reporting that as
    anything but done would keep the candidate reported forever.
    """

    CLEANED = "cleaned"
    RETAINED = "retained"
    FAILED = "failed"


class MaintenanceReason(StrEnum):
    """Why one maintenance pass ended where it did.

    Closed, and each member is fixed to exactly one outcome, so the two fields
    of a result cannot disagree: what an outcome counts, the reason explains.

    `UNPROVEN` is the classification keeping the candidate, and it is one
    member rather than a copy of `RetentionReason` because the result carries
    those retentions themselves -- an operator reads which artifact and which
    question off them, in the vocabulary they were already spelled in.

    The two tip members are the pass's own last reading, taken after everything
    else cleared and immediately before the mutation. `TIP_MOVED` is an
    artifact that has left the commit the classification proved -- an agent
    committed, a human pushed -- which is not a failure but a race the next
    pass re-runs from the start. `TIP_UNREADABLE` is that reading not coming
    back at all.

    The three failures name the step that would not run, because that is what
    separates the operator's next move: a checkout git refuses to remove is a
    tree on this host, a remote delete refused is a token or a branch
    protection rule, and a local ref that would not go is a clone somebody
    else is holding.
    """

    RECLAIMED = "reclaimed"
    UNPROVEN = "unproven"
    RECENT_ACTIVITY = "recent_activity"
    ACTIVITY_UNREADABLE = "activity_unreadable"
    ACTIVE_CLAIM = "active_claim"
    CLAIM_UNREADABLE = "claim_unreadable"
    TIP_MOVED = "tip_moved"
    TIP_UNREADABLE = "tip_unreadable"
    WORKTREE_REMOVAL_FAILED = "worktree_removal_failed"
    REMOTE_DELETE_FAILED = "remote_delete_failed"
    LOCAL_DELETE_FAILED = "local_delete_failed"


@dataclass(frozen=True)
class MaintenanceResult:
    """What one pass over one candidate decided, and what it is about.

    One record per candidate rather than one per artifact, because a pass that
    stops stops for the whole candidate: whatever is still standing when it
    ends is left where it is, and the discovery that found it once finds it
    again. Nothing here is a retry list, which is what lets an interrupted pass
    cost nothing to resume.

    `subject` names the artifact the reason is about -- a branch by name, a
    checkout by path -- spelled the way a retention's and a proven tip's are,
    and empty where the reason is about the candidate as a whole. `retentions`
    is the classification's own answer, carried only where it is what kept the
    candidate: a pass that cleared it has nothing to report there, and a
    retention beside a reclaimed candidate would read as a permission nothing
    gave.
    """

    candidate: MaintenanceCandidate
    outcome: MaintenanceOutcome
    reason: MaintenanceReason
    subject: str = ""
    retentions: tuple[Retention, ...] = ()
