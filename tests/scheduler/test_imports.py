# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Clean-process import checks and owner identity for the scheduler package."""

from __future__ import annotations

import subprocess
import sys
import unittest

from orchestrator import scheduler as _scheduler
from orchestrator.scheduler import models as _models
from orchestrator.scheduler import service as _service

_MODULES = (
    "orchestrator.scheduler",
    "orchestrator.scheduler.models",
    "orchestrator.scheduler.service",
)


class CleanProcessImportTest(unittest.TestCase):
    """Each scheduler module imports standalone in a fresh interpreter.

    The initializer reads the execution mixin off `service`, which imports the
    sibling `models` owner back through the package, so importing either owner
    directly must run the initializer without a partially-initialized-module
    error. A subprocess per module gives each a clean `sys.modules` no other test
    has already populated, exposing an import-order cycle a package-first suite
    run would mask.
    """

    def test_each_module_imports_standalone(self) -> None:
        for module in _MODULES:
            with self.subTest(module=module):
                completed = subprocess.run(
                    [sys.executable, "-c", f"import {module}"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, msg=completed.stderr)


class OwnerReExportTest(unittest.TestCase):
    def test_package_names_resolve_to_their_owners(self) -> None:
        # The historical package names resolve to the owning module's objects
        # rather than rebuilt copies, so patching an owner is observable.
        self.assertIs(_scheduler.SubmissionRequest, _models.SubmissionRequest)
        self.assertIs(_scheduler._Submission, _models.Submission)
        self.assertIs(
            _scheduler.SchedulerExecutionMixin,
            _service.SchedulerExecutionMixin,
        )

    def test_scheduler_inherits_the_execution_owner(self) -> None:
        self.assertIn(
            _service.SchedulerExecutionMixin,
            _scheduler.IssueScheduler.__mro__,
        )


if __name__ == "__main__":
    unittest.main()
