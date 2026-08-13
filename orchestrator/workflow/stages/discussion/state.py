# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The park reasons, pinned-state keys, and run identity the owners share.

The keys go into the pinned JSON comment live issues already carry, so renaming
one is a migration rather than a refactor -- and none of them has a single
owner: the park is written by one module and read by the handler that decides
whether a tick has a round to run at all, and `discussion_agent` /
`discussion_session_id` record which backend and conversation this issue's
discussion belongs to. Spelling them once is what keeps a typo from reading as
"never parked" or "never spawned".

The reasons share a prefix because that prefix is what `_parked_by_discussion`
asks about -- and what `workflow/stages/implementing/read_only_relabel.py` asks
about from outside the package, refusing to ship what one of these parks left
behind as dev work. Pinned state outlives a relabel, so an issue an operator
moves here arrives carrying whatever park the stage before it wrote; reading
bare `awaiting_human` would leave such an issue inert forever, waiting on a
reply to a question this stage never asked.

`_ROUND_BRANCH` / `_ROUND_SHA` are the round anchor: the branch this stage last
opened a round on and the SHA that branch was at when it did. They are written
BEFORE the spawn and survive every exit this stage takes, which is what lets
one record answer both questions asked of it.

On an issue with no discussion park, a non-empty anchor means a round opened
and never reached a disposition (withheld by a mid-run pause, or cut short by a
crash), and comparing it to the branch says whether that round left a commit.
On a parked issue it is a statement about the branch: everything the branch
carries AT that SHA predates this stage, so a tip still sitting there is
certified and one that has moved is not.
`workflow/stages/implementing/read_only_relabel.py` reads it that way, which is
how a discussion held on an inherited PR branch is relabeled to implementing
without being accused of the dev's commits.

That is also why a park that DID find a commit keeps it rather than spending
it. The anchor is the only recorded point dividing what the agent wrote from
what the branch arrived with, so it is the reset target the commit parks quote
and the tip this guard re-measures against once an operator has reset. Dropped
there, a PR-backed issue would be left with commits ahead of base and nothing
able to certify them: refused forever, with the only remaining remedies --
reset to base, delete the branch -- destroying the PR. The relabel that
succeeds is what finally clears the pair, in `_clear_stale_read_only_park`.

The branch is recorded beside the SHA because a SHA alone does not say which
ref it belongs to: an issue whose pinned `branch` is the legacy
`orchestrator/issue-N` form has its round open there, and a probe that answered
for the slug-namespaced ref instead would report an unchanged tip while the
commit sat on the branch the round actually used.

The stage and role names sit here for the opposite reason: they are not pinned
state at all. `_DISCUSSION_STAGE` is what an audit event and an analytics row
attribute the run to, and `_DECOMPOSER_ROLE` is the role whose configured agent
runs it -- the discussion is the decomposer thinking out loud before anything
is decomposed, so it answers under that role rather than one of its own.
"""
from __future__ import annotations

from orchestrator.github.pinned_state import PinnedState

_DISCUSSION_STAGE = "discussion"

_DECOMPOSER_ROLE = "decomposer"

_AWAITING_HUMAN = "awaiting_human"

_PARK_REASON = "park_reason"

# Not this stage's to write: it is read only to tell an issue whose branch has
# a remote PR head to restore from, from one whose branch exists nowhere but
# locally. See `run._ensure_round_worktree`.
_PR_NUMBER = "pr_number"

_DISCUSSION_AGENT_KEY = "discussion_agent"

_DISCUSSION_SESSION_KEY = "discussion_session_id"

_ROUND_BRANCH = "discussion_round_branch"

_ROUND_SHA = "discussion_round_sha"

_LAST_DISCUSSION_AT = "last_discussion_at"

_DISCUSSION_PARK_PREFIX = "discussion_"

_DISCUSSION_RESPONSE = "discussion_response"

_DISCUSSION_COMMITS = "discussion_commits"

_DISCUSSION_DIRTY = "discussion_dirty"

_DISCUSSION_SILENT = "discussion_silent"

_DISCUSSION_STRANDED = "discussion_stranded"

_DISCUSSION_TIMEOUT = "discussion_timeout"


def _parked_by_discussion(state: PinnedState) -> bool:
    """True when THIS stage is the one waiting on a human reply.

    A park written here is the round on the thread the humans are answering, so
    the next tick has nothing to do. A park written by any other stage is not:
    the operator relabeled a parked issue into a discussion, and the reply that
    park is waiting for is one nobody is going to send here.
    """
    if not state.get(_AWAITING_HUMAN):
        return False
    park_reason = state.get(_PARK_REASON)
    return str(park_reason or "").startswith(_DISCUSSION_PARK_PREFIX)
