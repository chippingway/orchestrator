# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The call shape every dev resume goes through."""

from __future__ import annotations

import inspect
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from orchestrator.workflow.stages.implementing import execution as _execution
from orchestrator.workflow.stages.implementing import resume as _resume


_SPEC = "spec"
_ISSUE = "issue"
_STATE = "state"


class DevResumeCallShapeTest(unittest.TestCase):
    def test_developer_resume_preserves_options(self) -> None:
        execution = Mock()
        execution.execute.return_value = (Path("worktree"), "result", False)
        build = Mock(return_value=execution)
        with patch.object(
            _execution._DevResumeContext,
            "build",
            build,
        ):
            resume_result = _resume._resume_dev_with_text(
                "gh",
                _SPEC,
                _ISSUE,
                _STATE,
                "continue",
                stage="fixing",
                pause_guard=True,
            )

        self.assertEqual(resume_result, execution.execute.return_value)
        request = build.call_args.args[0]
        self.assertEqual(request.resume_args, (_STATE, "continue"))
        self.assertEqual(request.option_fields, {"pause_guard": True})
        self.assertEqual(request.stage, "fixing")

    def test_resume_declares_its_signature(self) -> None:
        self.assertEqual(
            str(inspect.signature(_resume._resume_dev_with_text)),
            "(gh, spec, issue, *resume_args, stage=None, **option_fields)",
        )


if __name__ == "__main__":
    unittest.main()
