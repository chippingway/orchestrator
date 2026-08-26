# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Repository and backend values shared by workflow tests."""
from pathlib import Path

from orchestrator import config


TEST_REPO_SLUG = "geserdugarov/agent-orchestrator"
TEST_BASE_BRANCH = "main"
# What the remote says the base branch is at when a round opens. Pinned
# before the spawn, so a test seeding a round that already ran has to seed
# this too or its plan is measured against nothing.
BASE_TIP_SHA = "base-branch-tip"

# The two commits the size gate freezes a candidate between. Whole object
# ids, unlike the readable tip above, because these two round-trip through
# the pinned comment -- which reads a frozen commit at its exact length and
# drops anything else, so a readable stand-in would come back absent.
SHA_LENGTH = 40
MEASURED_BASE_SHA = "b" * SHA_LENGTH
MEASURED_CANDIDATE_SHA = "c" * SHA_LENGTH

# What the checkout's own head reads as before and after a run, in the world
# a test says nothing about. Two values rather than one because the ordinary
# world is a run that COMMITTED: the dispositions decide by comparing the two
# ends, so a single value says "the head never moved" and no value at all says
# "the probe failed" -- both of which are refusals a test should have to ask
# for. A test about either seeds the readings it is about.
HEAD_BEFORE_RUN = "head-before-the-run"
HEAD_AFTER_RUN = "head-after-the-run"

STATE_CLOSED = "closed"
STATE_OPEN = "open"

BACKEND_CLAUDE = "claude"
BACKEND_CODEX = "codex"

_FAKE_WT = Path("/tmp/orchestrator-test-wt-doesnt-matter")
_TEST_SPEC = config.RepoSpec(
    slug=TEST_REPO_SLUG,
    target_root=Path("/tmp/orchestrator-test-target-root"),
    base_branch=TEST_BASE_BRANCH,
)
