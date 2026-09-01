# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The record a squash hands back, in the three shapes it can end in.

One record rather than a tuple, because the third shape is what a tuple of
flags could not carry honestly: a candidate the size gate held is neither the
success a caller hands on nor the failure it parks over, and reading it as
either is how an adjudication ends up with a park notice on top of it or a
handoff underneath it.

It sits here rather than beside the owner that builds it because three owners
read it -- the entry point that composes the squash, the rewrite that produces
it, and the stage handler that acts on it -- and a record every one of them is
typed by belongs to none of them. `planning._SquashPlan` stays with the owner
that builds it for the opposite reason: nothing outside that step reads a plan.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class _SquashOutcome:
    """What one squash-and-publish did.

    `success` with a `sha` is the ordinary shape: the branch was collapsed and
    the remote force-pushed to match, `count` naming how many commits went
    into it and 0 meaning there was nothing to squash. A failure carries the
    `error` its caller parks with and leaves the original commits on the
    branch.

    `held` is neither, and it is the gate having taken the issue out of this
    caller's hands in one of two shapes. RECORDED, something durable names the
    squashed commit -- an oversized generation the adjudication is deciding
    about, or a frozen pair whose count never came back -- and the commit
    stays on the branch for the verdict or the reconciliation that answers it.
    REFUSED, the gate could not take its reading at all and froze nothing -- a
    pull request a human closed mid-rewrite, a head somebody moved under it --
    and it has already parked with the notice that reading earned, while the
    branch has been put back where the squash found it so the retry has
    commits to squash, measure, and publish afresh. On both the caller must
    neither park over the gate's own answer nor carry on with a handoff.
    """

    success: bool = False
    sha: str | None = None
    count: int = 0
    error: str | None = None
    held: bool = False
