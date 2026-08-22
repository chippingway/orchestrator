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

# An issue that never entered the gate, one measured under its ceiling, and a
# cancelled cycle, which is cleanup-only.
SETTLED_GENERATIONS = (
    ("never entered the gate", LateGeneration()),
    (
        "measured under its ceiling",
        late_generation(additions=UNDERSIZED_ADDITIONS),
    ),
    ("cancelled cycle", late_generation(cancelled=True)),
)


def relabelled(issue, label) -> None:
    """Move an issue's workflow label the way a human's click would."""
    issue.labels = [FakeLabel(label)]
