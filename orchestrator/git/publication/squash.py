# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The composed squash-and-publish entry point stage handlers call.

Sequencing the three steps is the whole job: `planning` runs every probe while
the branch is still intact, the size gate is entered on the publication the
squash is about to force-push onto, and only a plan that survived both and
carries more than one commit reaches the destructive `rewrite`. Keeping that
order here means no owner has to know when the next one is safe to run.

The gate sits BEFORE the rewrite deliberately. A squash is one of the pushes
onto a pull request the remote already carries, and the refusals it owes --
a pull request nothing could read, one a human closed mid-review, a tree that
is not provably clean, a head that moved out from under the reading -- are all
answerable while the branch is intact. Asked after the reset instead, every
one of them would cost a rewrite and a rollback to learn.
"""
from __future__ import annotations

from orchestrator.git.publication import models, planning, rewrite


def _squash_and_force_push(gate, branch: str) -> models._SquashOutcome:
    """Squash all commits since `origin/<base>` into one, force-push with lease.

    `gate` is the subject the size gate decides about -- the issue, its pinned
    state, and the checkout -- built by the caller, which is in the layer this
    module would otherwise have to reach up into for it.

    Returns one `_SquashOutcome`, in the four shapes a squash can end in:
      * `success` with `sha` and `count=0` — nothing to squash (zero or one
        commit on top of base). Caller should leave state alone.
      * `success` with `sha` and `count=N>1` — squashed N commits into one.
        `sha` is the new local HEAD; the remote was force-pushed to match.
      * `error` — squash refused, or squash / push failed. Caller parks
        awaiting_human; the original commits remain on the local branch (we
        abort before resetting if any check fails) and the remote was not
        updated.
      * `held` — the size gate took the issue out of this caller's hands.
        Where something durable names the squashed commit -- an oversized
        generation, or a frozen pair whose count never came back -- it stays
        on the branch for the verdict or the reconciliation that answers it;
        on a reading the gate could not take at all it froze nothing, parked
        with its own notice, and the branch was put back where the squash
        found it, so the retry has commits to squash and measure again rather
        than one nobody counted. Either way the caller stops without parking
        and without a handoff.

    The publication is entered before anything destructive runs, so a pull
    request nothing could read, one a human closed mid-review, a dirty tree,
    or a head that moved off what this stage read all refuse with the branch
    exactly as the reviewer approved it. The squashed commit is then measured
    like every other candidate for a pull request the remote already carries:
    the tree is the one that was just approved, but the BASE moves, so what
    the branch adds to it is a question only this reading answers -- and this
    is the last push before a human is asked to merge.

    All of it behind the switch. `DECOMPOSE=off` keeps a squash out of the
    gate entirely: no pull request is read, none of those refusals can be
    taken, and no reading is taken over the commit the squash makes. What such
    an install does is squash and force-push, under the lease this stage read
    for itself and under no other claim about the remote.

    The squash commit subject reuses the first commit's subject when it
    already carries a reusable `<prefix>:` form (Conventional or repo-local,
    so an `event:` / `career:` subject survives); otherwise it builds one
    from the issue title with `_infer_subject_prefix` -- a repo-local prefix
    when recent base history uses one, else `fix`/`feat`. The message is
    subject-only -- no body, no trailers -- so the orchestrator-authored
    squash matches the repo's subject-only commit rule. The commit is
    authored under the AGENT_GIT_* identity (via env vars) so attribution
    matches the per-step commits this squash replaces.
    """
    try:
        plan = planning._prepare_squash(
            gate.spec, gate.worktree, gate.issue,
        )
    except planning._SquashPreparationError as error:
        return rewrite._squash_failure(str(error))
    if len(plan.subjects) <= 1:
        return models._SquashOutcome(success=True, sha=plan.original_head)
    entry = rewrite._gated_rewrite()._entered_rewrite(
        gate, plan.original_head,
    )
    if not entry.is_frozen:
        return rewrite._squash_failure(entry.refusal)
    return rewrite._rewrite_squash(gate, branch, plan, entry)
