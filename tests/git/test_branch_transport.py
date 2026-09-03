# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The refusal channel and the failure shape token-bearing git reports through."""

from __future__ import annotations

import unittest

from orchestrator.git import branch_transport

FETCH_OPERATION = "fetch"
PLUMBING_LOGGER = "orchestrator.git_plumbing"


class RefusalChannelTest(unittest.TestCase):
    """Refusals reach the channel operators already watch.

    Operators filter on the rendered `orchestrator.git_plumbing` prefix and
    attach handlers to that logger, so every fetch and push refusal this
    owner emits has to render under that name rather than a package-derived
    one.
    """

    def test_logger_keeps_its_operator_facing_name(self) -> None:
        self.assertEqual(branch_transport.log.name, PLUMBING_LOGGER)


class FailedFetchTest(unittest.TestCase):
    """Refusals report as a completed `git fetch` that failed."""

    def test_shapes_a_failed_completed_process(self) -> None:
        # Callers branch on `returncode` and surface `stderr` in park
        # comments, so a refusal must be indistinguishable in shape from a
        # fetch that really ran and failed.
        failure = branch_transport._failed_fetch("GITHUB_TOKEN missing")

        self.assertEqual(failure.args, ["git", FETCH_OPERATION])
        self.assertEqual(failure.returncode, 1)
        self.assertEqual(failure.stdout, "")
        self.assertEqual(failure.stderr, "GITHUB_TOKEN missing")


if __name__ == "__main__":
    unittest.main()
