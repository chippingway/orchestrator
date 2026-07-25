# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Result fields and statuses owned by the verification model module."""

from __future__ import annotations

import unittest

from orchestrator.git.verification import models

VERIFY_STATUSES = ("ok", "failed", "timeout", "dirty", "head_changed")


class VerifyResultTest(unittest.TestCase):
    """Every status is constructible from `status` alone."""

    def test_variant_fields_default_to_empty(self) -> None:
        # The park-comment formatter switches on `status` and then reads the
        # variant fields unconditionally, so each one has to carry a None /
        # empty default instead of forcing the runner to pass placeholders.
        for status in VERIFY_STATUSES:
            with self.subTest(status=status):
                run = models.VerifyResult(status=status)
                self.assertEqual(run.status, status)
                self.assertIsNone(run.command)
                self.assertIsNone(run.exit_code)
                self.assertEqual(run.output, "")
                self.assertEqual(run.dirty_files, ())
                self.assertIsNone(run.head_before)
                self.assertIsNone(run.head_after)


if __name__ == "__main__":
    unittest.main()
