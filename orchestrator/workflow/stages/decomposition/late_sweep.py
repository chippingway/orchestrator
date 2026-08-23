# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The one pass that comes back to an owner nobody will dispatch again.

A split records what it owes the remote on the generation ledger and lets the
umbrella's terminal settle it. That works for every issue that reaches the
terminal. It does not work for the one a human closed halfway: a closed
`decomposing` or `umbrella` issue is outside every other pass this
orchestrator makes, so the branch its superseded candidate sat on and the
immutable ref its children were cut from would be held by a repository nothing
ever asked about again.

So this owner exists, and its whole shape is decided by what it must NOT do.
It is cleanup, not recovery: no agent is spawned, no label is written, no
child is activated, and no workflow is resumed. The issue is closed, and the
close is a human decision this pass has no standing to reverse -- the only
thing it acts on is the ledger, which is the record of what the orchestrator
put on somebody's repository and is therefore the one thing it still owes.

The rules are the reclamation owner's, not this one's -- the terminal reading
of a consumer, the decision recorded before a delete, and the release that
follows one all live there and are asked in exactly the same order the
umbrella's terminal asks them. What is here is the entry into them: the pinned
read that says whether anything is left to settle, and the first scan of the
recorded consumers, which a closed owner has no handler to take for it.

The one ledger no reading helps is the one this binary could not type. Nothing
on it may be reclaimed, so no consumer is read at all and the pass is spent on
saying so where an operator will see it.

Nothing here decides a terminal. The umbrella's own branch is where a settled
ledger earns a close, and an issue that is already closed has nothing left to
earn -- so the answer this pass gives is the work it did and no verdict at
all.
"""
from __future__ import annotations

import logging

from github.Issue import Issue

from orchestrator import config
from orchestrator.github.client import GitHubClient
from orchestrator.github.issues import issue_is_closed
from orchestrator.workflow.late_split import state as _late_state
from orchestrator.workflow.late_split.models import LateGeneration
from orchestrator.workflow.stages.decomposition import (
    late_cleanup as _late_cleanup,
)

log = logging.getLogger("orchestrator.workflow")


def _handle_closed_owner_cleanup(
    gh: GitHubClient, spec: config.RepoSpec, issue: Issue,
) -> None:
    """Settle what one closed snapshot owner still owes the remote.

    The whole of what a closed owner earns. It is reached only from the
    dispatcher's cleanup route, which is what guarantees the properties this
    pass is allowed to have: an issue on this path is never handed to the
    stage handler its label names, so nothing below can spawn the decomposer,
    resume an adjudication, or walk the dependency graph.

    The close is re-read here rather than trusted, because the reading that
    routed this issue was taken on the polling thread and the worker refetched
    it afterwards. An issue reopened in between is ordinary decomposition work
    again, and running a cleanup pass over it would settle a ledger a live
    cycle is still writing.

    An issue with no recorded generation is every issue the initial decomposer
    ever made, and it leaves without a read of its own.
    """
    if not issue_is_closed(issue):
        return
    state = gh.read_pinned_state(issue)
    generation = _late_state.read_late_generation(state)
    if not _worth_a_pass(issue, generation):
        return
    _late_cleanup._settle(
        gh, spec, issue, state,
        _late_cleanup._consumer_scan(gh, issue, generation),
    )


def _worth_a_pass(issue: Issue, generation: LateGeneration) -> bool:
    """Whether this ledger still holds the remote to anything at all.

    Asked before the consumers are read, because reading them is what the pass
    costs: an owner whose every obligation is reconciled has nothing a fresh
    disposition could unlock, and asking about it once per sweep forever is
    the difference between a sweep that is affordable and one that is not.

    An opaque RESOURCE ledger stops the pass rather than starting one. Nothing
    on a ledger holding an entry this binary cannot type may be recorded -- the
    entries it could not read are obligations too, and settling around them is
    what the verbatim copy exists to prevent -- so every reading this pass
    could take is one it may not act on. Saying so on each visit is the point:
    the ledger is a human's to settle, and only an operator can.

    An opaque CONSUMER ledger is not that. It is what a snapshot's proof is
    taken from, so it keeps the ref -- and it says nothing about the branch,
    which is exactly what this pass would otherwise stop coming back for.
    """
    if not generation.is_present:
        return False
    if _late_cleanup._unwritable(generation):
        log.warning(
            "issue=#%s is closed holding an obligation ledger this "
            "orchestrator cannot read; nothing it records can be reclaimed "
            "until a human settles it", issue.number,
        )
        return False
    return bool(
        _late_cleanup._owed_branches(generation)
        + _late_cleanup._held_snapshots(generation),
    )
