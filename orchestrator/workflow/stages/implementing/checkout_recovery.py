# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The one refusal in this stage a human cannot answer with words.

What `checkout_guards` holds an issue for is a checkout it could not hand to
review -- one that had left the commit the size gate approved, or one carrying
work beside it that no push would publish -- and neither of those is a
question anybody can reply to. What settles them is the checkout being that
commit and nothing else again, which is an operator's own `git checkout`
between two ticks rather than a sentence on the thread.

So the park writes the approved commit down and this owner is the proof taken
against what it wrote. It is asked on every ordinary tick rather than on a
command, because the recovery is the checkout coming back and nothing else has
to happen for it -- and it is asked about the same two things the refusal was
taken on, since a proof narrower than the refusal it answers would republish
straight back into it.

What the answer LICENSES is the caller's: the republication of an approved
commit, the records it spends, and the relabel behind them all belong to the
disposition that reads this. This owner decides only whether the checkout is
the one that was approved.
"""
from __future__ import annotations

import logging
from pathlib import Path

from github.Issue import Issue

from orchestrator.git.measurement import commits as _measurement_commits
from orchestrator.git.verification import probes as _verification_probes
from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.late_split import (
    formats as _formats,
    payloads as _payloads,
)
from orchestrator.workflow.stages.implementing import state as _state

log = logging.getLogger("orchestrator.workflow")

_HEAD = "HEAD"


def _restored_checkout(
    issue: Issue, state: PinnedState, worktree: Path,
) -> str:
    """The approved commit this checkout is back on, or "" if it is not.

    Both halves of "this checkout" are asked, because the park it answers is
    taken on either of them. A head somewhere else is one; a tree carrying
    work no push would publish -- or one nothing could read at all -- is the
    other, and it is the half that can be true with the head never having
    moved. Republishing on the head alone would take the very reading
    publication refused on and walk it straight back into the same refusal,
    posting a fresh notice every poll for a checkout that has not changed.

    Asked silently and answered silently. A park still waiting costs one local
    `rev-parse` and one `status` a tick and says nothing on the thread, which
    is what lets the question be asked every tick rather than only when a
    human asks it: the checkout coming back is enough on its own, and an
    operator who leaves it where it is is not told so once a poll.
    """
    approved = _payloads.as_hex(
        state.get(_state._APPROVED_SHA), _formats.COMMIT_LENGTHS,
    )
    if not approved:
        return ""
    proved = _measurement_commits._prove_candidate_commit(worktree, _HEAD)
    if not (proved.is_frozen and proved.sha == approved):
        log.debug(
            "issue=#%s is still not on the approved commit %s; leaving the "
            "park where it is", issue.number, approved,
        )
        return ""
    if _verification_probes._worktree_status(worktree).is_clean:
        return approved
    log.debug(
        "issue=#%s is back on the approved commit %s but its tree is not "
        "provably clean; leaving the park where it is",
        issue.number, approved,
    )
    return ""
