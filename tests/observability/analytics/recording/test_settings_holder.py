# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Which analytics package instance a recorder writes and dispatches through."""

import json
import tempfile
import unittest


from pathlib import Path
from unittest.mock import patch

from tests.analytics_reload_helpers import reload_analytics as _reload
from tests.observability.observability_test_support import _run_import_probe

_APPEND_RECORD_MEMBER = 'append_record'


_REPO_SHORT = "o/r"


_STAGE_IMPLEMENTING = "implementing"


_STAGE_ENTER = "stage_enter"


_PROBE_ISSUE = 7


# A process that imported the owner and nothing else: no bootstrap ran
# alongside it, so there is no captured instance and the settings have to be
# resolved at call time. Both directions are asserted -- naming the owner must
# not plant the compatibility package, and recording through it must.
_UNCAPTURED_HOLDER_PROBE = """
import os
import sys

os.environ["ORCHESTRATOR_SKIP_DOTENV"] = "1"
os.environ["ANALYTICS_LOG_PATH"] = {path!r}

from orchestrator.observability.analytics import recording

if "orchestrator.analytics" in sys.modules:
    sys.exit("importing the owner planted the compatibility package")
recording.record_stage_enter(repo={repo!r}, issue={issue!r}, stage={stage!r})
if "orchestrator.analytics" not in sys.modules:
    sys.exit("the recorder never resolved a settings holder")
"""


class SettingsHolderTest(unittest.TestCase):
    """A recorder dispatches through the package instance it answers for, so
    a reference held across a `_reload` keeps reaching the one its own callers
    patched rather than whichever the package name resolves to now.
    """

    def test_internal_append_routes_via_the_holder(self) -> None:
        # A recorder's internal `append_record` is late-bound through the
        # settings holder, so patching `analytics.append_record` intercepts it.
        _, analytics = _reload()
        captured: list[dict] = []
        with patch.object(analytics, _APPEND_RECORD_MEMBER, captured.append):
            analytics.record_stage_enter(
                repo=_REPO_SHORT,
                issue=1,
                stage=_STAGE_IMPLEMENTING,
            )
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0]["event"], _STAGE_ENTER)

    def test_reload_keeps_stale_holder_reference(self) -> None:
        # A holder that imported the package before a `_reload` keeps its own
        # instance: its recorders read the knobs patched on THAT instance, not
        # the freshly reloaded one that now sits in `sys.modules`.
        _, stale = _reload()
        captured_stale: list[dict] = []
        stale_patch = patch.object(stale, _APPEND_RECORD_MEMBER, captured_stale.append)
        stale_patch.start()
        self.addCleanup(stale_patch.stop)
        _, fresh = _reload()
        self.assertIsNot(fresh, stale)
        captured_fresh: list[dict] = []
        with patch.object(fresh, _APPEND_RECORD_MEMBER, captured_fresh.append):
            fresh.record_stage_enter(repo=_REPO_SHORT, issue=2, stage="fixing")
        stale.record_stage_enter(
            repo=_REPO_SHORT,
            issue=1,
            stage=_STAGE_IMPLEMENTING,
        )
        self.assertEqual([rec["issue"] for rec in captured_fresh], [2])
        self.assertEqual([rec["issue"] for rec in captured_stale], [1])

    def test_uncaptured_holder_resolved_at_call_time(self) -> None:
        # What a producer does: it names the owner, never the compatibility
        # package, so nothing is captured for it to answer with. The settings
        # still live on that package, so the record only lands if the recorder
        # reaches for it inside the call.
        with tempfile.TemporaryDirectory() as sink_dir:
            sink = Path(sink_dir) / "a.jsonl"
            completed = _run_import_probe(_UNCAPTURED_HOLDER_PROBE.format(
                path=str(sink),
                repo=_REPO_SHORT,
                issue=_PROBE_ISSUE,
                stage=_STAGE_IMPLEMENTING,
            ))
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            records = [
                json.loads(line)
                for line in sink.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["event"], _STAGE_ENTER)
        self.assertEqual(records[0]["issue"], _PROBE_ISSUE)
        self.assertEqual(records[0]["stage"], _STAGE_IMPLEMENTING)


if __name__ == "__main__":
    unittest.main()
