# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Which configured repository a discovered artifact belongs to, and which issue.

An artifact found on this host is not evidence of anything on its own. Several
``REPOS`` entries may share one `target_root` -- a public and a private remote
over a single checkout is the shape branch namespacing exists for -- and their
ref stores are one store, so everything under `orchestrator/` there was
published by whichever of them owns that issue. Attribution is therefore a
question about the whole set of configured specs rather than about one name in
isolation, and every function here takes that set.

Three rules, all exact and all failing closed:

* A name is attributed only when a spec's own derivation in ``paths``
  produces it character for character. Nothing is parsed back into a slug, so
  a segment no configured entry writes, an extra path component, or a padded
  number is left alone rather than reconstructed into a repository.
* A name several specs could equally own is attributed to none of them. The
  legacy flat layout carries no slug at all, which makes every spec on a
  shared clone an equal claimant to `orchestrator/issue-<n>`. The checkout
  directories are the same story one derivation over: the path sanitizer is
  lossy, so two entries whose slugs differ only in a character it rewrites
  are handed one directory to keep their checkouts in, and an `issue-<n>` in
  it names an issue in whichever of them created it.
* Where no name can settle it, the repository the artifact is OF does. The
  flat pre-namespacing checkout is the one artifact with nothing in its name
  at all -- every entry derived it identically -- so it is attributed by the
  git directory it and its clone share, which is the same identity the
  classification tests a named checkout by. That leaves exactly one case
  ambiguous, and it is the case the rule above already names: two entries on
  one clone.

Both refusals cost the same thing -- an artifact this scan will not report --
and the alternative costs more: an artifact attributed to the wrong repository
is one a caller acts on against the wrong GitHub issue.
"""
from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from orchestrator import config
from orchestrator.git.worktrees import paths

# The channel is named for the worktree-lifecycle domain rather than for this
# module's path: operators filter the rendered `orchestrator.worktree_lifecycle`
# prefix and attach handlers to it, so the refusals below report where their
# filters already point.
log = logging.getLogger("orchestrator.worktree_lifecycle")

_REF_SEPARATOR = "/"

# How a refusal lists the several things it will not choose between.
_LISTED = ", "

# One repository's branches, keyed by the issue they name: one entry per
# issue however many layouts it is published under.
IssueBranches = dict[int, tuple[str, ...]]

# What one clone's branches say about the repositories sharing it.
AttributedIssues = dict[config.RepoSpec, IssueBranches]


@dataclass(frozen=True)
class CheckoutClaim:
    """What a flat checkout's clone identity settled, and what it did not.

    `owner` is the one repository the directory was PROVEN to be a worktree of,
    and it is set only when nothing else could be: one claimant, whose clone
    was read and matched. `claimants` is every repository it could belong to,
    which is what a caller withholds the issue from when the question was not
    settled -- the two overlap by design, since a settled claim is a claimant
    that happens to be alone.
    """

    owner: config.RepoSpec | None
    claimants: tuple[config.RepoSpec, ...]


def _matching_owners(
    branch: str,
    issue_number: int,
    specs: tuple[config.RepoSpec, ...],
) -> tuple[config.RepoSpec, ...]:
    """Every spec on this clone whose own derivation produces `branch`.

    The current layout carries the publishing spec's ref-safe slug, so it is
    matched by re-deriving each spec's name for that issue and comparing:
    another repository's segment, a segment no ``REPOS`` entry produces, and
    an `issue-<n>` tail hanging under two path components all match nobody.

    The legacy layout carries no slug, so every spec sharing the clone is
    returned for it. That is not a claim that all of them own the branch -- it
    is the ambiguity itself, handed to the caller in the only form that can
    express it, and a clone with a single spec on it resolves the same way
    without a special case.
    """
    namespaced = tuple(
        spec for spec in specs
        if paths._branch_name(spec, issue_number) == branch
    )
    if namespaced:
        return namespaced
    if branch == paths._legacy_branch_name(issue_number):
        return specs
    return ()


def _branch_attribution(
    branch: str, specs: tuple[config.RepoSpec, ...],
) -> tuple[config.RepoSpec, int] | None:
    """The repository and issue one local branch belongs to, or None.

    None covers three different artifacts, deliberately answered the same
    way: a name carrying no readable issue number, a name no configured
    repository publishes, and a name more than one of them could. Only the
    last is worth an operator's attention -- the other two describe branches
    somebody else's tooling or a human left in the `orchestrator/` namespace,
    and a scan that ran every tick would say so every tick.
    """
    issue_number = paths._issue_segment_number(
        branch.rsplit(_REF_SEPARATOR, 1)[-1],
    )
    if issue_number is None:
        log.debug("local branch %r names no issue; leaving it alone", branch)
        return None
    owners = _matching_owners(branch, issue_number, specs)
    if len(owners) > 1:
        log.warning(
            "local branch %r could belong to any of %s; refusing to "
            "attribute it rather than charging one of them for it",
            branch, _LISTED.join(spec.slug for spec in owners),
        )
        return None
    if not owners:
        log.debug(
            "local branch %r belongs to no configured repository; leaving "
            "it alone", branch,
        )
        return None
    return owners[0], issue_number


def _record_attribution(
    owned: AttributedIssues,
    attribution: tuple[config.RepoSpec, int],
    branch: str,
) -> None:
    """File one attributed branch under the repository and issue it names.

    Rebuilt through `paths._issue_branch_names` rather than appended in the
    order the ref store listed them, which does two things at once: an issue
    carrying both layouts always reads namespaced-first, the order a caller
    acts on them in, and a name that is not one of the two that derivation
    produces cannot enter the answer through this door either.
    """
    spec, issue_number = attribution
    issues = owned.setdefault(spec, {})
    found = set(issues.get(issue_number, ())) | {branch}
    issues[issue_number] = tuple(
        name for name in paths._issue_branch_names(spec, issue_number)
        if name in found
    )


def _attributed_issues(
    branches: Iterable[str], specs: tuple[config.RepoSpec, ...],
) -> AttributedIssues:
    """Group one clone's orchestrator branches by repository and issue.

    A repository with no branch of its own is absent from the answer rather
    than present with an empty entry, so a caller reading it back gets the
    same shape whether the clone holds one repository's branches or several.
    """
    owned: AttributedIssues = {}
    for branch in branches:
        attribution = _branch_attribution(branch, specs)
        if attribution is not None:
            _record_attribution(owned, attribution, branch)
    return owned


def _slugs_by_worktrees_root(
    specs: Iterable[config.RepoSpec],
) -> dict[Path, tuple[str, ...]]:
    """Group the configured slugs by the checkout directory each derives."""
    by_root: dict[Path, tuple[str, ...]] = {}
    for spec in specs:
        root = paths._repo_worktrees_root(spec)
        by_root[root] = (*by_root.get(root, ()), spec.slug)
    return by_root


def _countable_legacy_checkouts(
    specs: Iterable[config.RepoSpec], found: frozenset[int],
) -> frozenset[int]:
    """The flat `issue-<n>` directories that are checkouts rather than roots.

    A number whose flat path is also some entry's per-repository worktrees root
    is dropped, which takes a `REPOS` slug that sanitizes to an `issue-<n>` of
    its own: what sits at that path is then a directory full of checkouts
    rather than a checkout, and the two must not be confused whichever of them
    the scan reached first.
    """
    roots = {paths._repo_worktrees_root(spec) for spec in specs}
    return frozenset(
        issue_number for issue_number in found
        if paths._legacy_worktree_path(issue_number) not in roots
    )


def _legacy_checkout_claim(
    clone: Path | None,
    clones: Mapping[config.RepoSpec, Path | None],
    subject: str,
) -> CheckoutClaim:
    """Who a flat checkout could be a worktree of, and whether that was settled.

    The flat layout carries no slug, so unlike every other rule here the
    question cannot be settled by re-deriving a name: `WORKTREES_DIR/issue-<n>`
    is what every configured entry produced, identically. What settles it
    instead is the same identity the classification tests a named checkout by
    -- the git directory the checkout and its clone share -- so a host driving
    several repositories on several clones still attributes each flat checkout
    to the one entry whose clone it is a worktree of.

    An entry whose OWN clone could not be read claims the checkout too. Nothing
    established that it is not the one, and dropping it from the claimants is
    how a checkout on a shared clone reads as uniquely owned: the sibling that
    would have made it ambiguous simply did not answer. The same reading covers
    the checkout whose own clone could not be read, which claims every entry
    there is.

    An owner therefore comes back only where the whole question was answered:
    one claimant, and that claimant's clone read and matched. Every other shape
    hands the claimants over instead, because a tree none of them may take is
    standing on one of that issue's branches -- so the caller has to withhold
    the issue rather than merely drop the directory.
    """
    if clone is None:
        log.warning(
            "could not tell which clone the flat checkout %s is of; leaving "
            "every repository's copy of that issue alone", subject,
        )
        return CheckoutClaim(owner=None, claimants=tuple(clones))
    claimants = tuple(
        spec for spec, configured_at in clones.items()
        if configured_at is None or configured_at == clone
    )
    if len(claimants) == 1 and clones[claimants[0]] is not None:
        return CheckoutClaim(owner=claimants[0], claimants=claimants)
    _report_unsettled(claimants, subject)
    return CheckoutClaim(owner=None, claimants=claimants)


def _report_unsettled(
    claimants: tuple[config.RepoSpec, ...], subject: str,
) -> None:
    """Say why a flat checkout was not charged to anybody.

    Three shapes, and an operator settles each differently: a clone nobody
    could read is a repository to go and look at, several claimants is a
    configuration whose entries share a store, and no claimant at all is a
    directory that is simply not this orchestrator's -- which is the one shape
    that costs nothing and says so at debug.
    """
    named = _LISTED.join(spec.slug for spec in claimants)
    if len(claimants) > 1:
        log.warning(
            "the flat checkout %s could belong to any of %s; refusing to "
            "attribute it, and leaving that issue's artifacts alone in all "
            "of them", subject, named,
        )
    elif claimants:
        log.warning(
            "could not tell whether the flat checkout %s is %s's; leaving "
            "that issue's artifacts alone", subject, named,
        )
    else:
        log.debug(
            "the flat checkout %s is no configured repository's; leaving it "
            "alone", subject,
        )


def _colliding_worktree_slugs(
    specs: Iterable[config.RepoSpec],
) -> tuple[str, ...]:
    """The slugs whose checkout directory is not theirs alone.

    The path counterpart of the branch rules above, and it has to be asked
    across every configured entry rather than per clone: the checkouts hang
    off one `WORKTREES_DIR` whatever clone their repository is on, and the
    slug sanitizer that names the per-repo directory under it rewrites every
    character it cannot keep. Two entries it cannot tell apart therefore get
    one directory, and an `issue-<n>` checkout in it carries nothing that says
    which of them created it -- the same unanswerable question a shared
    clone's legacy branch asks.

    Refusing those repositories outright rather than only their checkouts is
    the honest reading of it: what a caller does with a candidate turns on the
    artifacts under it, and half a picture of a repository whose other half
    cannot be attributed is not one to act on. It costs nothing a healthy
    configuration has -- a real `owner/name` pair sanitizes injectively, so
    reaching this needs a `REPOS` entry carrying a character GitHub does not
    allow in a repository name.
    """
    colliding: list[str] = []
    for root, slugs in _slugs_by_worktrees_root(specs).items():
        if len(slugs) > 1:
            log.warning(
                "the checkout directory %s is derived by %s; refusing to "
                "attribute anything under it to any of them",
                root, _LISTED.join(slugs),
            )
            colliding.extend(slugs)
    return tuple(sorted(colliding))
