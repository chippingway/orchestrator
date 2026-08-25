# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The pin every workflow step names its action by.

A tag is mutable, so a `uses:` naming one leaves the action's owner able to
change what a reviewed workflow executes. A full 40-character commit SHA
cannot move, and the release it belongs to rides beside it in a trailing
comment because that comment is the only thing naming the version a human --
or Dependabot, opening the update PR -- reads the pin by.

Nothing in the tree runs these files -- GitHub does -- so a step that slipped
back to a tag, or lost the comment, would otherwise show up as an unpinned
action on a workflow run nobody is reading.

The SHA is checked for its shape, not against the comment beside it: resolving
a release to its commit needs the network, and a suite that reached for it
would fail on an offline host rather than on the edit it is meant to catch.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW_DIR = _REPO_ROOT / ".github" / "workflows"
_ENCODING = "utf-8"

# `owner/action` or `owner/action/sub-path`, at a full commit SHA, labeled with
# the release that SHA is the tip of.
_PINNED_USES = re.compile(
    r"uses: [\w.-]+/[\w./-]+@[0-9a-f]{40} # v\d+(?:\.\d+)*$", re.MULTILINE,
)
_ANY_USES = "uses: "


def _workflow_files() -> list[Path]:
    return sorted(_WORKFLOW_DIR.glob("*.yml"))


def _unpinned_steps(path: Path) -> list[str]:
    """Every `uses:` line in one workflow that is not a labeled SHA pin."""
    lines = path.read_text(encoding=_ENCODING).splitlines()
    return [
        f"{path.name}:{number}: {line.strip()}"
        for number, line in enumerate(lines, start=1)
        if _ANY_USES in line and not _PINNED_USES.search(line.rstrip())
    ]


class WorkflowActionPinsTest(unittest.TestCase):
    def test_every_workflow_uses_a_commented_sha_pin(self) -> None:
        unpinned = [
            step for path in _workflow_files() for step in _unpinned_steps(path)
        ]
        unpinned_report = "\n".join(unpinned)
        self.assertEqual(
            unpinned,
            [],
            "workflow steps name an action by something other than a SHA pin "
            f"with a trailing version comment:\n{unpinned_report}",
        )

    def test_every_workflow_pins_at_least_one_action(self) -> None:
        """A vacuous pass -- no workflows, or none using an action -- is a bug.

        The check above reports only what it finds, so a directory it fails to
        read, or a workflow whose steps it cannot see, would pass it silently.
        """
        pinned_counts = {
            path.name: len(_PINNED_USES.findall(path.read_text(encoding=_ENCODING)))
            for path in _workflow_files()
        }
        self.assertTrue(pinned_counts)
        for name, count in pinned_counts.items():
            with self.subTest(workflow=name):
                self.assertGreater(count, 0)


if __name__ == "__main__":
    unittest.main()
