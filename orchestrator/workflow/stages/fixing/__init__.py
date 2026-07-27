# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The dev fix-loop that two different routes hand the same PR to.

`in_review` flips here when a human answers an open PR, and `validating` flips
here when its own reviewer requests changes. Almost every decision below turns
on which route it was, and the discriminator is `pending_fix_at`: the in_review
route records it beside the feedback bookmarks, the validating route never
does. It decides whether a pushed fix resets `review_round` or bumps it,
whether a no-commit `ACK:` may return the issue to `in_review`, and whether a
transient park is allowed to clear itself without a human ever commenting.

`handler` holds the order those questions are asked in. The preflight runs
first because a merged or closed PR outranks anything the loop would otherwise
compute, and the rescan behind it reads the in_review watermarks rather than
the `pending_fix_*` bookmarks -- the bookmarks stay untouched in pinned state
because the first resume advances those watermarks past the very feedback that
started the loop, and a later `/orchestrator continue` has nothing else left to
replay from.

That is why `feedback` and `bookmarks` are separate owners: one reads forward
from a watermark, the other reconstructs backward from recorded ids, and only
`continue_command` needs the second. `feedback` also owns the ratchet, because
what a consumed batch is allowed to hide is the same decision as what an unread
scan is allowed to see. `parked` is the dispatcher for a tick that arrived
`awaiting_human`, and `drift` is the exit it takes when the validating-route
recovery cannot clear a transient park but the worktree has fallen behind base:
the per-tick base sync stands down on every park, so nobody else will rebase it.

`resume` is the run and everything a finished run leaves behind -- the quiet
window it waits out, the ACK fast path, the watermark advance that runs on BOTH
outcomes, and the `validating` relabel a pushed fix earns.

Callers import the owner they need, so this initializer binds nothing: the
dispatcher resolves one handler per issue, and an eager binding here would
charge every importer of one stage for the worktree, GitHub, and dev-resume
machinery only the resume path reaches.
"""
