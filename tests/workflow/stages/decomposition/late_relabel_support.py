# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The generations that pin `workflow:decomposing`, and the ones that do not.

Two modules ask the same question of the same three records -- the dispatcher
refusal and the kill-switch bailout -- so the records are described once. Each
of them is a state a live issue really reaches, and each answers False to the
one predicate both paths gate on.
"""
from __future__ import annotations

from orchestrator.workflow.late_split.models import LateGeneration

from tests.support.fakes import FakeLabel
from tests.workflow.stages.decomposition.late_test_support import (
    UNDERSIZED_ADDITIONS,
    late_generation,
)

# An issue that never entered the gate and one measured under its ceiling.
# Neither is this mode's business at all, so both route and relabel freely.
SETTLED_GENERATIONS = (
    ("never entered the gate", LateGeneration()),
    (
        "measured under its ceiling",
        late_generation(additions=UNDERSIZED_ADDITIONS),
    ),
)

# The third record no gate keyed to size holds, and the one that is NOT free
# to be routed: a cancelled cycle is its own ending until that ending is
# written, so the dispatcher stops it on either adjudication label where the
# two above are waved through.
CANCELLED_GENERATION = late_generation(cancelled=True)

# All three, for the predicates that only ask whether an adjudication is live.
NOT_LIVE_GENERATIONS = SETTLED_GENERATIONS + (
    ("cancelled cycle", CANCELLED_GENERATION),
)

# The one that LOOKS settled and is not: a revision that came back under the
# ceiling while the read its own run owes has still to be taken. Every gate
# keyed to size waves it through, and nobody has established that the issue it
# would be published under is still open.
OWED_READ_GENERATION = late_generation(
    additions=UNDERSIZED_ADDITIONS, owner_check_pending=True,
)

# The same read owed on a cycle somebody cancelled: the cleanup path owns what
# is left, and nothing about it is in flight any more.
CANCELLED_OWED_READ = late_generation(
    additions=UNDERSIZED_ADDITIONS,
    owner_check_pending=True,
    cancelled=True,
)


def relabelled(issue, label) -> None:
    """Move an issue's workflow label the way a human's click would."""
    issue.labels = [FakeLabel(label)]
