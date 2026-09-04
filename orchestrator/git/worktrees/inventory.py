# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The read-only scan that derives issue candidates from local artifacts.

Which issues this host has work for is normally GitHub's answer. This scan
answers the local half of it instead, from what the host already holds: every
`issue-<n>` checkout under a spec's worktrees root, every one still standing
under the flat root that predates that per-repository parent, and every branch
in the clone's orchestrator-owned namespace names an issue this orchestrator
has already worked on. Nothing here fetches, writes, or asks GitHub anything,
so the answer costs one directory listing per repository, one more for the
whole host, one `for-each-ref` per clone, and -- only where that flat listing
found something -- one identity read per configured entry and per flat
checkout. It stays valid to take at any point in a tick.

Every side is deduplicated into one entry per issue, because they are views of
one thing: a checkout whose branch was deleted, a branch whose checkout was
removed, and an issue still carrying both are all one issue. So is an issue
published under both branch layouts, and so is one sitting in both checkout
layouts -- a host running across the migration kept the flat tree and made the
per-repository one beside it, and those are two directories of one issue
rather than two issues.

The flat root is read once for the whole host rather than per repository,
because it had no per-repository parent to read: what comes back is a set of
issue numbers with nothing on them saying whose they are, and it is
``attribution`` that settles each against the clone the directory turns out to
be a worktree of.

The scan is grouped by clone rather than run per repository because several
``REPOS`` entries may share one `target_root`, and a shared ref store is the
one place a name cannot be attributed by looking at it alone -- which is
``attribution``'s subject. What is decided here is the shape of the answer
around it: which reads a refusal takes down with it, and in what order the
result is handed back.
"""
from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from itertools import chain
from pathlib import Path

from orchestrator import config
from orchestrator.git.worktrees import attribution, paths, probes
from orchestrator.git.worktrees.models import ArtifactInventory, IssueArtifacts

# The channel is named for the worktree-lifecycle domain rather than for this
# module's path: operators filter the rendered `orchestrator.worktree_lifecycle`
# prefix and attach handlers to it, so a repository this scan will not answer
# for says so where their filters already point.
log = logging.getLogger("orchestrator.worktree_lifecycle")

# The specs on each clone a scan reads, keyed by the path their spellings
# agree on: one group is one ref store, and everyone in it is a claimant to
# what that store holds.
CloneGroups = dict[Path, tuple[config.RepoSpec, ...]]

# The flat pre-namespacing checkouts, by the repository each was found to be
# a worktree of. A repository nothing was attributed to is absent rather than
# present with an empty entry, so a caller reads the same shape whether the
# host holds one entry's flat checkouts or several entries' -- and one nobody
# could be attributed to is in no entry at all.
LegacyCheckouts = dict[config.RepoSpec, frozenset[int]]


def _resolved_root(spec: config.RepoSpec) -> Path | None:
    """The clone this spec configures, as the one path its spellings agree on.

    `None` when the path cannot be resolved at all, which is a failure worth
    catching here rather than letting out: resolution is what says whether two
    entries are on one clone, it runs before any repository has been read, and
    an exception escaping it ends the whole scan -- every healthy repository
    in it included -- over one entry's `target_root`. What it costs to fail is
    also version-dependent, so it cannot be reasoned about from the value: a
    root reached through a symlink loop raises `RuntimeError` out of
    `Path.resolve` on Python 3.12 and comes back unchanged on 3.13.

    The caller refuses that entry -- nothing about it is reported -- while
    still grouping it under the path as written, because the two are different
    questions. Whether this scan can answer for a repository is one; whether
    that repository could have published what is on the clone it names is the
    other, and dropping it from its group answers the second wrongly: the
    legacy flat branch there would lose a claimant and read as unambiguously
    some other entry's.
    """
    try:
        return spec.target_root.resolve()
    except (OSError, RuntimeError) as resolve_error:
        log.warning(
            "could not resolve the clone %s is configured at (%s): %s",
            spec.slug, spec.target_root, resolve_error,
        )
        return None


def _specs_by_clone(
    specs: Sequence[config.RepoSpec],
) -> tuple[CloneGroups, tuple[str, ...]]:
    """The specs grouped by the clone they name, and whose path did not resolve.

    Grouped on the resolved path, so two entries spelling one clone
    differently -- through a symlink, with a trailing `.` -- land in one group
    with one ambiguous legacy branch between them instead of two groups each
    claiming that branch for itself. The reads still run against a path a spec
    configures, which is the one the rest of the worktree owners lock and run
    git in.

    An entry whose path would not resolve is grouped under that path as
    written rather than dropped: it is still one of the repositories that
    could have published what its clone holds, and the second half of the
    answer is what says the scan will not report for it.
    """
    grouped: CloneGroups = {}
    unresolved: list[str] = []
    for spec in specs:
        resolved = _resolved_root(spec)
        if resolved is None:
            unresolved.append(spec.slug)
        clone = resolved or spec.target_root
        grouped[clone] = (*grouped.get(clone, ()), spec)
    return grouped, tuple(unresolved)


def _held_checkouts(
    spec: config.RepoSpec,
    issue_number: int,
    checkouts: frozenset[int],
    legacy: frozenset[int],
) -> tuple[Path, ...]:
    """Which of this issue's two checkout paths the host is actually holding.

    Filtered out of what this issue's own derivations produce rather than
    assembled from the directory names the scan read, which does what the
    branch side's own recording does: a path neither derivation writes cannot
    enter the answer, and an issue holding both layouts always reads
    current-first, the order a teardown takes them in.
    """
    held = set()
    if issue_number in checkouts:
        held.add(paths._worktree_path(spec, issue_number))
    if issue_number in legacy:
        held.add(paths._legacy_worktree_path(issue_number))
    return tuple(
        path for path in paths._issue_worktree_paths(spec, issue_number)
        if path in held
    )


def _issue_artifacts(
    spec: config.RepoSpec,
    issue_number: int,
    checkouts: tuple[frozenset[int], frozenset[int]],
    branched: Mapping[int, tuple[str, ...]],
) -> IssueArtifacts:
    """One issue's entry: the checkouts it still has, and the branches naming it.

    The two checkout sets arrive as one pair because they are one question read
    in two places: the per-repository root this spec owns, and the flat
    directory every entry once shared.
    """
    return IssueArtifacts(
        spec=spec,
        issue_number=issue_number,
        worktrees=_held_checkouts(spec, issue_number, *checkouts),
        branches=branched.get(issue_number, ()),
    )


def _spec_inventory(
    spec: config.RepoSpec,
    branched: Mapping[int, tuple[str, ...]],
    legacy: frozenset[int],
) -> ArtifactInventory:
    """Every issue one repository has an artifact for, or a refusal for it.

    The union of all three sides is what makes a candidate: an issue is
    reported once whether a checkout, the branches, or any of them named it.
    The per-repository checkouts are read for one repository at a time because
    the directory they sit in is this spec's alone -- an entry that shares it
    with another was refused before the scan reached here. The flat ones were
    read once for the whole host and are handed in already attributed, since
    the directory they sit in is nobody's alone.
    """
    checkouts = probes._worktree_issue_numbers(spec)
    if checkouts is None:
        return ArtifactInventory(issues=(), refused=(spec.slug,))
    return ArtifactInventory(
        issues=tuple(
            _issue_artifacts(
                spec, issue_number, (checkouts, legacy), branched,
            )
            for issue_number in sorted(
                checkouts | legacy | branched.keys(),
            )
        ),
        refused=(),
    )


def _root_inventory(
    root_specs: tuple[config.RepoSpec, ...],
    refused: frozenset[str],
    legacy: LegacyCheckouts,
) -> ArtifactInventory:
    """Every issue the repositories sharing one clone hold artifacts for.

    One listing per clone rather than one per repository: the specs on it
    share a ref store, so a second read would return the same refs and
    attribute them the same way.

    Every spec on the clone is put to the attribution, the already-refused
    ones included, and only the rest are reported. Refusing a repository says
    this scan will not answer for it, not that it never published here: drop
    it from the claimants and the flat `orchestrator/issue-<n>` this clone
    holds loses an owner it could equally have, which is how a branch that
    belongs to nobody ends up charged to whichever entry was left.

    A listing that could not be taken refuses every repository still standing
    on that clone, checkouts included, even though those were never read for.
    What a caller does with an issue turns on the shape of its artifacts -- a
    checkout with no branch and a checkout whose branch simply could not be
    read are different situations with the same appearance -- so reporting the
    checkouts alone would hand out that shape as if it had been established.
    """
    reportable = tuple(
        spec for spec in root_specs if spec.slug not in refused
    )
    if not reportable:
        return ArtifactInventory(issues=(), refused=())
    branches = probes._local_orchestrator_branches(reportable[0].target_root)
    if branches is None:
        return ArtifactInventory(
            issues=(), refused=tuple(spec.slug for spec in reportable),
        )
    owned = attribution._attributed_issues(branches, root_specs)
    return _merged(tuple(
        _spec_inventory(
            spec, owned.get(spec, {}), legacy.get(spec, frozenset()),
        )
        for spec in reportable
    ))


def _merged(
    inventories: tuple[ArtifactInventory, ...],
) -> ArtifactInventory:
    """One answer over several scans, in an order two runs can be compared by.

    Each issue is produced by exactly one repository's scan, so this
    concatenates rather than combines: the deduplication a single issue needs
    has already happened where its two sides were read.
    """
    return ArtifactInventory(
        issues=tuple(sorted(
            chain.from_iterable(scan.issues for scan in inventories),
            key=lambda artifacts: (artifacts.spec.slug, artifacts.issue_number),
        )),
        refused=tuple(sorted({
            slug for scan in inventories for slug in scan.refused
        })),
    )


def _legacy_owner(
    issue_number: int,
    clones: dict[config.RepoSpec, Path | None],
) -> config.RepoSpec | None:
    """Which configured repository one flat checkout is a worktree of."""
    worktree = paths._legacy_worktree_path(issue_number)
    return attribution._legacy_checkout_owner(
        probes._checkout_clone(worktree), clones, str(worktree),
    )


def _attributed_legacy(
    configured: tuple[config.RepoSpec, ...], flat: frozenset[int],
) -> LegacyCheckouts:
    """Which repository each flat pre-namespacing checkout belongs to.

    The clones are resolved once for the whole host and only when there is
    something to attribute, because that read costs a git process per
    configured entry and the layout it settles is one nothing has written to
    for a long time: a host with no flat checkouts left pays nothing at all.
    """
    counted = attribution._countable_legacy_checkouts(configured, flat)
    if not counted:
        return {}
    clones = {
        spec: probes._checkout_clone(spec.target_root) for spec in configured
    }
    owned: LegacyCheckouts = {}
    for issue_number in sorted(counted):
        owner = _legacy_owner(issue_number, clones)
        if owner is not None:
            owned[owner] = owned.get(owner, frozenset()) | {issue_number}
    return owned


def _scanned(
    configured: tuple[config.RepoSpec, ...], legacy: LegacyCheckouts,
) -> ArtifactInventory:
    """The scan proper, once the host-wide flat checkouts have been attributed.

    Two refusals are settled here, before a repository is read, because both
    are answers about the configuration rather than about a host: the entries
    sharing a derived checkout directory, which is ``attribution``'s second
    ambiguity rule, and the entries whose clone would not resolve. Neither is
    read, and neither is reported -- but both stay in the group their clone
    holds, because a repository this scan will not answer for is still one that
    could have published what is on the clone it names.
    """
    colliding = attribution._colliding_worktree_slugs(configured)
    grouped, unresolved = _specs_by_clone(configured)
    refused = frozenset(colliding) | frozenset(unresolved)
    return _merged((
        ArtifactInventory(issues=(), refused=(*colliding, *unresolved)),
        *(
            _root_inventory(root_specs, refused, legacy)
            for root_specs in grouped.values()
        ),
    ))


def _local_issue_inventory(
    specs: Sequence[config.RepoSpec],
) -> ArtifactInventory:
    """Every issue this host holds an orchestrator-owned artifact for.

    The entry point to the scan, taking the configured specs rather than
    reading them, so a caller with a narrower list -- one repository, or the
    ones a tick actually drives -- asks about exactly those.

    An issue appears here because of what is on this host, which is a
    different question from what GitHub would say about it: a candidate may
    name an issue that is closed, merged, or was never this orchestrator's to
    begin with. Deciding that is the caller's, and the repositories named in
    `refused` are the ones it cannot decide anything about from this answer.

    The flat pre-namespacing checkouts are read first and once, because they
    are the one artifact that belongs to no repository by its name: they sit
    directly under `WORKTREES_DIR`, which every entry shares. A listing that
    could not be taken refuses every configured repository, since a flat
    checkout that was not read is one any of them could still be holding --
    and a caller acting on the absence of one would be acting on a reading
    nobody took.
    """
    configured = tuple(specs)
    flat = probes._legacy_checkout_numbers()
    if flat is None:
        return ArtifactInventory(
            issues=(),
            refused=tuple(sorted({spec.slug for spec in configured})),
        )
    return _scanned(configured, _attributed_legacy(configured, flat))
