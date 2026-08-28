# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The wall-clock ceiling every security scan's job runs under.

A job that hangs -- a network read that never returns, an action waiting on
input no one is there to give -- runs until GitHub cancels it six hours later,
and both halves of this set pay for that wait. The dependency review is a
required check and CodeQL's findings are enforced by a code-scanning ruleset,
so a hung job holds a merge for those six hours instead of failing in the
minutes the scan takes. Scorecard, the vulnerability scan, and CodeQL's
scheduled pass have nobody watching, so a hung one holds a runner while
reading as a scan that has yet to report rather than as one that failed. A
job-level `timeout-minutes` is what bounds either wait to the window the scan
is expected to finish in.

Nothing in the tree runs these files -- GitHub does -- so a job added or
rewritten without one would otherwise go unnoticed until the run that hangs.

The ceiling below is what keeps a declared timeout from being a restatement:
GitHub already cancels a job at 360 minutes, so a value at or past that is the
platform default under another name.
"""
from __future__ import annotations

import re
import unittest
from itertools import takewhile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW_DIR = _REPO_ROOT / ".github" / "workflows"
_ENCODING = "utf-8"

# The security scans, whether a pull request waits on one or a schedule runs it.
_SECURITY_WORKFLOWS = (
    "codeql.yml",
    "dependency-review.yml",
    "scorecard.yml",
    "vulnerability-scan.yml",
)

_PLATFORM_DEFAULT_MINUTES = 360

_JOBS_BLOCK = "jobs:"
# A job's own name and its own `timeout-minutes`, each at the one indent that
# belongs to it: a step declares the same key two levels deeper, and that one
# bounds the step rather than the job around it.
_JOB_NAME = re.compile(r"^ {2}([\w-]+):$")
_JOB_TIMEOUT = re.compile(r"^ {4}timeout-minutes: (\d+)$")
_TOP_LEVEL_KEY = re.compile(r"^\S")

_JobTimeouts = dict[str, int | None]


def _below_a_top_level_key(line: str) -> bool:
    return not _TOP_LEVEL_KEY.match(line)


def _job_lines(workflow: str) -> list[str]:
    """The block one workflow's `jobs:` mapping covers, if it declares one."""
    lines = workflow.splitlines()
    if _JOBS_BLOCK not in lines:
        return []
    body = lines[lines.index(_JOBS_BLOCK) + 1:]
    return list(takewhile(_below_a_top_level_key, body))


def _job_timeouts(workflow: str) -> _JobTimeouts:
    """Every job one workflow declares, against the timeout it sets."""
    timeouts: _JobTimeouts = {}
    job = ""
    for line in _job_lines(workflow):
        named = _JOB_NAME.match(line)
        declared = _JOB_TIMEOUT.match(line)
        if named:
            job = named.group(1)
            timeouts[job] = None
        elif declared and job:
            timeouts[job] = int(declared.group(1))
    return timeouts


def _security_workflow_timeouts() -> dict[str, _JobTimeouts]:
    return {
        name: _job_timeouts((_WORKFLOW_DIR / name).read_text(encoding=_ENCODING))
        for name in _SECURITY_WORKFLOWS
    }


def _untimed_jobs() -> list[str]:
    """Every job across the security workflows that declares no timeout."""
    return [
        f"{name}: {job}"
        for name, timeouts in _security_workflow_timeouts().items()
        for job, minutes in timeouts.items()
        if minutes is None
    ]


class SecurityWorkflowTimeoutTest(unittest.TestCase):
    def test_every_job_declares_a_timeout(self) -> None:
        untimed = _untimed_jobs()
        untimed_report = "\n".join(untimed)
        self.assertEqual(
            untimed,
            [],
            "workflow jobs run to GitHub's six-hour default because they "
            f"declare no `timeout-minutes`:\n{untimed_report}",
        )

    def test_no_timeout_reaches_the_platform_default(self) -> None:
        for name, timeouts in _security_workflow_timeouts().items():
            for job, minutes in timeouts.items():
                with self.subTest(workflow=name, job=job):
                    self.assertIsNotNone(minutes)
                    self.assertLess(minutes, _PLATFORM_DEFAULT_MINUTES)

    def test_every_workflow_declares_a_job(self) -> None:
        """A vacuous pass -- a file read as jobless -- is a bug.

        Both checks above report only on the jobs they find, so a renamed
        workflow, or one whose `jobs:` block this module fails to read, would
        pass them without having been looked at.
        """
        for name, timeouts in _security_workflow_timeouts().items():
            with self.subTest(workflow=name):
                self.assertTrue(timeouts)


class JobTimeoutReadingTest(unittest.TestCase):
    """What the reader above counts as a job's own timeout."""

    def test_each_job_maps_to_its_own_timeout(self) -> None:
        cases = {
            "a timed job": ("jobs:\n  analyze:\n    timeout-minutes: 5\n", {"analyze": 5}),
            "an untimed job": ("jobs:\n  grade:\n    runs-on: ubuntu-latest\n", {"grade": None}),
            "one of each": (
                "jobs:\n  audit:\n    timeout-minutes: 7\n  review:\n    runs-on: ubuntu-latest\n",
                {"audit": 7, "review": None},
            ),
            "a step's own timeout": (
                "jobs:\n  scan:\n    steps:\n      - timeout-minutes: 9\n",
                {"scan": None},
            ),
            "a key past the jobs block": (
                "jobs:\n  build:\n    runs-on: ubuntu-latest\nconcurrency:\n    timeout-minutes: 9\n",
                {"build": None},
            ),
            "no jobs at all": ("on:\n  push:\n", {}),
        }
        for description, (workflow, expected) in cases.items():
            with self.subTest(workflow=description):
                self.assertEqual(_job_timeouts(workflow), expected)


if __name__ == "__main__":
    unittest.main()
