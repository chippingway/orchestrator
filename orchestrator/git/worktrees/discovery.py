# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The candidates a maintenance pass acts on: the host's scan, widened by the remote.

The scan in ``inventory`` answers from what this host holds, which is the whole
answer for every artifact a host can still see. It is not the whole answer for
a finished issue: the branch this orchestrator pushed outlives the clone it was
pushed from, so a host rebuilt from scratch, a clone re-cloned, or a local ref
somebody deleted by hand leaves work standing on the remote that nothing local
names. This module is the second half of that question -- what the REMOTE still
carries under the orchestrator-owned namespace -- folded into the first so one
issue comes back as one candidate however many places its artifacts are in.

Folded rather than run beside it. The two halves are two views of one issue,
exactly as a checkout and a branch already are, and a caller handed them
separately would have to pair them back up before it could act: the branch this
clone holds and the branch of that name on the remote are one artifact over two
hosts, and a teardown that took them for two would delete one on the strength
of a proof about the other.

Attribution is the local rule, unchanged and applied to the remote's names too.
A remote is one repository's own, so a name on it could only have been pushed
by an entry configured against that repository -- but the LOCAL ref of the same
name is the thing a teardown goes on to delete, and on a shared clone the
legacy flat `orchestrator/issue-<n>` there belongs to whichever entry created
it. Attributing the remote's copy to one of them would hand a teardown a name
whose local half nobody can attribute, which is the refusal the scan exists to
make. So the remote's names are put to the same claimants the clone's are, and
a name several of them could own is attributed to none.

A repository whose remote would not answer is refused outright rather than
reported from its local half alone. Every question that follows -- what a
branch is at, whether the base carries it, the lease a delete is pinned to --
is asked of that same remote, so a repository it cannot reach is one this pass
could not finish anyway, and a candidate list that quietly narrows to the local
half would report a remote-only artifact as an issue with nothing left.
"""
from __future__ import annotations

import logging
from collections.abc import Sequence

from orchestrator import config
from orchestrator.git import ref_transport
from orchestrator.git.worktrees import attribution, inventory, paths
from orchestrator.git.worktrees.models import (
    CandidateLayout,
    IssueArtifacts,
    MaintenanceCandidate,
    MaintenanceScan,
)

# The channel is named for the worktree-lifecycle domain rather than for this
# module's path: operators filter the rendered `orchestrator.worktree_lifecycle`
# prefix and attach handlers to it, so a remote this discovery will not answer
# for says so where their filters already point.
log = logging.getLogger("orchestrator.worktree_lifecycle")

# The namespace every branch this orchestrator publishes lives under, in the
# pattern form `ls-remote` matches by. git's glob crosses `/` here, so the one
# pattern covers the flat legacy name and the slug-namespaced one a component
# deeper alike, and the trailing separator keeps a ref called
# `refs/heads/orchestrator` itself out of the answer.
_ORCHESTRATOR_REMOTE_REFS = "refs/heads/orchestrator/*"

_REMOTE_BRANCH_PREFIX = "refs/heads/"

# What the remote carries, by the repository that published it and the issue it
# names: the remote-side counterpart of the clone's own attributed listing.
PublishedBranches = dict[config.RepoSpec, attribution.IssueBranches]

# One issue of one repository, as both halves of a discovery key it.
CandidateKey = tuple[config.RepoSpec, int]


def _remote_orchestrator_branches(
    spec: config.RepoSpec,
) -> tuple[str, ...] | None:
    """Every branch this repository's remote carries under the owned namespace.

    Named as the derivations in ``paths`` spell them, so the attribution that
    re-derives each spec's own name can compare against them without either
    side adjusting; a refname the listing reports outside `refs/heads/` is not
    a branch and is left out rather than trimmed into one.

    `None` when the remote would not answer, which is not the empty tuple a
    repository whose branches have all been deleted gives. The read runs in the
    clone rather than in a per-issue checkout, because the transport-config
    refusal in front of it has to inspect the repository this discovery is
    about -- and a checkout a candidate names may already be gone.

    The boundary around it is total, for the reason every probe with a fixed
    set of answers carries one: the transport answers `None` for the failures
    it recognizes and raises for the ones underneath them -- a git that cannot
    be spawned, a host that will not let this process write the askpass script,
    a clone that has been removed since the configuration named it. An
    exception out of one repository's listing would end the discovery for every
    other repository in it, which is the one way an unreachable remote could
    cost more than the artifacts it is about.
    """
    try:
        listed = ref_transport._remote_ref_names(
            spec, spec.target_root, pattern=_ORCHESTRATOR_REMOTE_REFS,
        )
    except Exception:
        log.warning(
            "could not ask %s what it still carries under the orchestrator "
            "namespace", spec.slug, exc_info=True,
        )
        return None
    if listed is None:
        log.warning(
            "could not list what %s still carries under the orchestrator "
            "namespace; leaving its artifacts alone", spec.slug,
        )
        return None
    return tuple(
        refname[len(_REMOTE_BRANCH_PREFIX):] for refname in listed
        if refname.startswith(_REMOTE_BRANCH_PREFIX)
    )


def _remote_issue_branches(
    spec: config.RepoSpec, root_specs: tuple[config.RepoSpec, ...],
) -> attribution.IssueBranches | None:
    """Which of this remote's branches belong to this repository, by issue.

    Put to every claimant on the clone rather than to this spec alone, which is
    what keeps the ambiguous legacy name unattributed: the remote says which
    repository the branch was pushed to, and nothing says which of the entries
    sharing a clone created it -- so a name more than one of them could own
    stays nobody's here as it does locally.

    A name attributed to a SIBLING on that clone is dropped rather than
    reported under it: what this repository's remote carries is evidence about
    this repository, and a branch spelled for another entry that turned up here
    is not something either of them can be charged for.
    """
    listed = _remote_orchestrator_branches(spec)
    if listed is None:
        return None
    owned = attribution._attributed_issues(listed, root_specs)
    return owned.get(spec, {})


def _group_published(
    root_specs: tuple[config.RepoSpec, ...], refused: frozenset[str],
) -> tuple[PublishedBranches, frozenset[str]]:
    """What the remotes of the repositories on one clone carry, and whose would not say.

    One listing per repository rather than per clone, because a remote is the
    one thing entries sharing a clone do not share: two `REPOS` entries over a
    single checkout are a public and a private repository, and asking one of
    them what the other holds would attribute a branch to a repository that
    never carried it.

    A repository the local scan already refused is not listed for, since
    nothing about it will be reported either way -- and it stays in the group
    put to the attribution, because a repository this pass will not answer for
    is still one the flat legacy branch on its clone could belong to.
    """
    listed = {
        spec: _remote_issue_branches(spec, root_specs)
        for spec in root_specs if spec.slug not in refused
    }
    return (
        {
            spec: branched for spec, branched in listed.items()
            if branched is not None
        },
        frozenset(
            spec.slug for spec, branched in listed.items()
            if branched is None
        ),
    )


def _published_branches(
    grouped: inventory.CloneGroups, refused: frozenset[str],
) -> tuple[PublishedBranches, frozenset[str]]:
    """What every repository's remote still carries, over every clone at once."""
    published: PublishedBranches = {}
    unreachable: frozenset[str] = frozenset()
    for root_specs in grouped.values():
        listed, missed = _group_published(root_specs, refused)
        published.update(listed)
        unreachable |= missed
    return published, unreachable


def _candidate_layout(
    artifacts: IssueArtifacts, local: tuple[str, ...],
) -> CandidateLayout:
    """Which layout this candidate's artifacts were published under.

    `REMOTE_ONLY` is answered first and on where the artifacts are rather than
    on what they are called: an issue this host holds no checkout and no branch
    for leaves an operator nothing here to look at, whichever name the remote's
    copy carries, and that is the fact the reading is spent on.

    The rest is the names themselves. Every name in the answer is one of the
    two `paths` derives, so the question is only which of them are there: both
    is the shape a migration leaves and no single derivation produces, the flat
    one alone is an issue that was in flight when namespacing landed, and
    anything else is the current layout -- a checkout with no branch left
    beside it included, since the path it sits at is the one this orchestrator
    writes now.
    """
    if artifacts.worktree is None and not local:
        return CandidateLayout.REMOTE_ONLY
    named = frozenset(artifacts.branches)
    legacy = paths._legacy_branch_name(artifacts.issue_number) in named
    current = (
        paths._branch_name(artifacts.spec, artifacts.issue_number) in named
        or not named
    )
    if legacy and current:
        return CandidateLayout.MIXED
    return CandidateLayout.LEGACY if legacy else CandidateLayout.CURRENT


def _widened(
    artifacts: IssueArtifacts, published: tuple[str, ...],
) -> MaintenanceCandidate:
    """One candidate: the artifacts as the host and the remote together hold them.

    The two lists are merged through `paths._issue_branch_names` rather than
    concatenated, which does what the local scan's own recording does one level
    up: an issue carrying both layouts always reads namespaced-first, the order
    a teardown takes them in, one name cannot arrive twice because it is on
    both hosts, and a name neither derivation produces cannot enter through
    this door either.

    The layout is decided here because this is the last place both halves are
    still apart. Afterwards the branches are one list by design, and nothing
    downstream could say which of them the clone was actually holding.
    """
    held = frozenset(artifacts.branches) | frozenset(published)
    branches = tuple(
        name for name in paths._issue_branch_names(
            artifacts.spec, artifacts.issue_number,
        )
        if name in held
    )
    widened = IssueArtifacts(
        spec=artifacts.spec,
        issue_number=artifacts.issue_number,
        worktree=artifacts.worktree,
        branches=branches,
    )
    return MaintenanceCandidate(
        artifacts=widened,
        layout=_candidate_layout(widened, artifacts.branches),
    )


def _candidate_order(key: CandidateKey) -> tuple[str, int]:
    """One key as the pair a discovery's whole answer is ordered by."""
    spec, issue_number = key
    return spec.slug, issue_number


def _candidate_keys(
    local: dict[CandidateKey, IssueArtifacts], published: PublishedBranches,
) -> tuple[CandidateKey, ...]:
    """Every repository and issue either half of the discovery named, in order.

    Sorted by slug and then issue number, so a candidate found only on the
    remote lands where the same issue would have landed had this host still
    held it -- which is what lets two discoveries of an unchanged world be
    compared.
    """
    keyed = set(local) | {
        (spec, issue_number)
        for spec, branched in published.items()
        for issue_number in branched
    }
    return tuple(sorted(keyed, key=_candidate_order))


def _keyed_candidate(
    key: CandidateKey,
    local: dict[CandidateKey, IssueArtifacts],
    published: PublishedBranches,
) -> MaintenanceCandidate:
    """The candidate one repository-and-issue key stands for.

    A key the local scan never named is an issue whose artifacts are all on the
    remote, and it is built with the empty local shape rather than skipped:
    what makes it a candidate is the branch out there, and the widening beside
    this is what puts that branch on it.
    """
    spec, issue_number = key
    artifacts = local.get(key) or IssueArtifacts(
        spec=spec, issue_number=issue_number, worktree=None, branches=(),
    )
    return _widened(artifacts, published.get(spec, {}).get(issue_number, ()))


def _remote_half(
    configured: tuple[config.RepoSpec, ...], refused: frozenset[str],
) -> tuple[PublishedBranches, frozenset[str]]:
    """What every reachable remote carries, and who is left out of the answer.

    The grouping is taken again here rather than carried over from the scan,
    because what it decides is not the same question: the scan groups to know
    which repositories claim one ref store, and this groups to know which of
    them a name on one remote could equally have come from. Both answers are
    the same clone map, and neither is worth threading through a record that
    exists to describe a host.
    """
    grouped, _unresolved = inventory._specs_by_clone(configured)
    published, unreachable = _published_branches(grouped, refused)
    return published, refused | unreachable


def _maintenance_candidates(
    specs: Sequence[config.RepoSpec],
) -> MaintenanceScan:
    """Every candidate a maintenance pass may consider, over host and remote.

    The entry point, taking the configured specs rather than reading them, so a
    caller driving one repository still hands over the whole set: attribution
    is a question about every entry at once -- which of them share a clone,
    which of them derive one checkout directory -- and a scan told about one
    would attribute a name several could own to the only claimant it knew.

    A candidate here is an issue this host or its remote holds something for,
    which is a different question from what GitHub would say about it: it may
    be open, may never have been this orchestrator's, may not exist. Deciding
    that is the classification's, and the repositories in `refused` are the
    ones nothing can be decided about from this answer at all.
    """
    configured = tuple(specs)
    scanned = inventory._local_issue_inventory(configured)
    published, refused = _remote_half(
        configured, frozenset(scanned.refused),
    )
    local = {
        (artifacts.spec, artifacts.issue_number): artifacts
        for artifacts in scanned.issues
        if artifacts.spec.slug not in refused
    }
    return MaintenanceScan(
        candidates=tuple(
            _keyed_candidate(key, local, published)
            for key in _candidate_keys(local, published)
        ),
        refused=tuple(sorted(refused)),
    )
