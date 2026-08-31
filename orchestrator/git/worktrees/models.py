# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a scan of this host's per-issue artifacts found, and what it refused.

Data only. `IssueArtifacts` is one issue as one repository's clone and
worktrees root show it, and `ArtifactInventory` is the whole answer a single
scan gives. The scan that fills them lives in ``inventory``, the two local
reads under it in ``probes``, and the rules deciding which configured
repository a discovered branch belongs to in ``attribution``.

The refusals are carried in the answer rather than logged and dropped because
of what a reader does with an absence: "this repository has no artifacts" and
"this repository could not be read" look identical in a list of issues, and a
caller acting on the first while holding the second acts on a host it never
saw.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

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
    worktree: Optional[Path]
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
