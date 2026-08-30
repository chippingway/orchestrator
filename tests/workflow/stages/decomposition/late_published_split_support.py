# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""One guarded split whose candidate was measured on an existing publication.

The `late_transaction_support` fixture beside this one is the split itself.
What this adds is the side of publication it was entered on: no plan PR was
ever held, and what the verdict was taken over is the implementation pull
request the work is already on.
"""
from __future__ import annotations

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
