# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Per-target-root lock ownership in the git locks module."""

from __future__ import annotations

import threading
import unittest
from pathlib import Path

from orchestrator.git import locks

TARGET_ROOT = Path("/tmp/orchestrator-test-locks-target-root")


class TargetRootLockRegistryTest(unittest.TestCase):
    """`tick()` fans stages out across worker threads, so two workers can
    drive git plumbing against the same `spec.target_root` at once and race
    on `.git/config.lock`. The registry hands both of them the same lock.
    """

    def setUp(self) -> None:
        # Drop the per-key locks earlier cases retained for temporary paths.
        locks._TARGET_ROOT_LOCKS.clear()

    def test_same_root_shares_one_reentrant_lock(self) -> None:
        root_lock = locks._target_root_lock(TARGET_ROOT)

        self.assertIs(locks._target_root_lock(TARGET_ROOT), root_lock)
        with root_lock:
            # Re-entrant, so a caller holding the lock can call a helper that
            # acquires it again instead of deadlocking.
            self.assertTrue(root_lock.acquire(blocking=False))
            root_lock.release()

    def test_distinct_roots_do_not_serialize(self) -> None:
        self.assertIsNot(
            locks._target_root_lock(TARGET_ROOT),
            locks._target_root_lock(TARGET_ROOT.with_name("other-root")),
        )

    def test_creation_runs_under_registry_guard(self) -> None:
        self.assertIs(
            locks._TARGET_ROOT_LOCKS_LOCK,
            locks._TARGET_ROOT_LOCKS.guard,
        )
        self.assertIsInstance(
            locks._TARGET_ROOT_LOCKS_LOCK,
            type(threading.Lock()),
        )

    def test_clear_drops_retained_locks(self) -> None:
        stale = locks._target_root_lock(TARGET_ROOT)

        locks._TARGET_ROOT_LOCKS.clear()

        self.assertIsNot(locks._target_root_lock(TARGET_ROOT), stale)


if __name__ == "__main__":
    unittest.main()
