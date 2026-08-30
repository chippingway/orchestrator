# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""One guarded split whose candidate was measured on an existing publication.

The `late_transaction_support` fixture beside this one is the split itself.
What this adds is the side of publication it was entered on: no plan PR was
ever opened, and what the verdict was taken over is the implementation pull
request the work is already on.

Seeded unheld, which is the narrower of the two shapes a transaction meets: a
publication that was open when the adjudication started wears this cycle's
hold, and one settled by then does not. `held_publication` is the other.
"""
from __future__ import annotations

from dataclasses import replace

from orchestrator.workflow.late_split.models import LateGeneration
from orchestrator.workflow.stages.decomposition import late_hold as _late_hold

from tests.workflow.stages.decomposition.late_published_support import (
    published_generation,
    seed_published_pr,
)
from tests.workflow.stages.decomposition.late_test_support import (
    PUBLISHED_PR_NUMBER,
    generation_state,
)
from tests.workflow.stages.decomposition.late_transaction_support import (
    KEY_PR_NUMBER,
    LateSplitCase,
)


# The description an implementation pull request was opened with, and what
# the hold on it displaced.
PUBLISHED_BODY = "the change this publication was opened with"


class PublishedSplitCase(LateSplitCase):
    """A split whose candidate was measured on a pull request that exists.

    There is no plan PR here and there never was: the gate was entered past
    the first push, so what the verdict was taken over is the implementation
    pull request the work is already on. Seeded that way rather than reached
    through a gate, for the reason the held case is seeded: getting here
    through an adjudication would cost a recorded verdict, which is what stops
    the next tick spawning the run under test.
    """

    def setUp(self) -> None:
        super().setUp()
        self.generation = published_generation()
        self.github.seed_state(
            self.issue.number,
            **{
                **generation_state(self.generation),
                KEY_PR_NUMBER: PUBLISHED_PR_NUMBER,
            },
        )
        self.published_pr = seed_published_pr(self.github)

    def held_publication(self) -> LateGeneration:
        """The same generation with this cycle's hold on its publication.

        What a tick that reached the transaction over an OPEN pull request is
        actually carrying: the hold goes on before the agent starts, on the
        pull request the entry names, and the description it displaced is
        preserved beside the identity and the head it was taken over.
        """
        held = replace(
            self.generation,
            plan_pr_number=PUBLISHED_PR_NUMBER,
            plan_pr_head=self.published_pr.head.sha,
            plan_pr_body=PUBLISHED_BODY,
        )
        self.published_pr.body = _late_hold._hold_body(held)
        return held
