# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Which repository a client is for, and whether a head belongs to it.

One question with one right answer and three callers, all of them refusing a
publication on it: the size gate's entry freeze, the delivery proof behind a
publication receipt, and the settlement's own reconciliation. Each is deciding
whether a pull request it just read is one THIS repository could have
published, and none of them can answer from the pull request alone -- a fork
carries this repository's ref names over its commits, so the branch and the
head agree while the pull request is somebody else's entirely.

The client is the authority because the client is what took the reading. A
spec passed alongside it would be a second copy of the same fact, and the one
that can drift.

What that answer is compared as matters as much as where it comes from.
Configuration is whatever an operator typed, and GitHub matches owner and
repository names case-insensitively -- so the same repository is one spelling
in a setting and another in every answer the API gives. Read from the
repository OBJECT the name is the one GitHub uses, which is also the one a
park quotes back at a human; compared case-insensitively on top of that, a
configuration that disagrees only in case cannot make this repository's own
publication read as a stranger's.
"""
from __future__ import annotations


class GitHubRepositoryIdentityMixin:
    """The repository a client speaks for, as a fact other owners may ask."""

    @property
    def repo_slug(self) -> str:
        """The repository this client reads and writes, as GitHub spells it.

        Answered from the repository object rather than from the configured
        slug, so what comes back is the canonical name: the configuration is
        whatever an operator typed, and `ChippingWay/Orchestrator` resolves the
        same repository as `chippingway/orchestrator` while being a name no
        human would recognize in a refusal. The configured spelling is the
        fallback for a client whose repository could not be described.
        """
        return getattr(
            getattr(self, "repo", None), "full_name", None,
        ) or self._repo_slug

    def is_own_repository(self, full_name: str | None) -> bool:
        """Whether `full_name` names the repository this client is for.

        Case-INSENSITIVELY, which is the whole reason this is asked here
        rather than spelled as an equality at each call site: owner and
        repository names are case-insensitive on GitHub, so a repository is
        `octo/Repo` in one answer and `Octo/repo` in a hand-typed setting, and
        compared exactly one of this repository's own publications reads as a
        fork's.

        A head naming no repository at all answers False. That is a pull
        request whose head repository is gone -- a deleted fork is the plain
        case -- and nothing about it says it was ever this repository's.
        """
        if not full_name:
            return False
        return full_name.casefold() == self.repo_slug.casefold()
