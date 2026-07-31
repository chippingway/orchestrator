# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What survives when a producer names the owner before the facade exists."""

import json
import tempfile
import unittest


from pathlib import Path

from tests.observability.observability_test_support import _run_import_probe

_REPO_SHORT = "o/r"


_STAGE_IMPLEMENTING = "implementing"


_STAGE_ENTER = "stage_enter"


_PROBE_ISSUE = 11


_STRANDED_ISSUE = 12


_EVENT_VALUE = "pr_opened"


_RECORDERS = (
    "append_record",
    "build_record",
    "record_agent_exit",
    "record_repo_skill_catalog",
    "record_stage_enter",
    "record_stage_evaluation",
)


# The order a producer actually creates: it names the owner at its own import,
# and nothing has named the compatibility package yet. Initializing that
# package afterwards rebuilds the recorders for the instance it belongs to, so
# what this pins is that the rebuild lands *on* the package object the producer
# is holding rather than beside it -- the module a patch is aimed at, the
# objects the facade forwards, and the lock the prune takes all have to stay
# the producer's own.
_OWNER_FIRST_PROBE = """
import json
import sys

import os
os.environ["ORCHESTRATOR_SKIP_DOTENV"] = "1"
os.environ["ANALYTICS_LOG_PATH"] = {path!r}

from orchestrator.observability.analytics import recording as owner
import orchestrator.skills.catalog as producer

if "orchestrator.analytics" in sys.modules:
    sys.exit("importing the owner planted the compatibility package")

from orchestrator import analytics

sink_lock = sys.modules[
    "orchestrator.observability.analytics.recording.io"
].ANALYTICS_FILE_LOCK
failures = []

if producer.recording is not owner:
    failures.append("the producer no longer holds the canonical package")
if sys.modules["orchestrator.observability.analytics.recording"] is not owner:
    failures.append("the canonical package was replaced")
for name in {recorders!r}:
    if getattr(analytics, name) is not getattr(owner, name):
        failures.append("the facade stopped forwarding " + name)
if analytics._FILE_LOCK is not sink_lock:
    failures.append("the facade append takes a different sink lock")
if analytics._retention._FILE_LOCK is not sink_lock:
    failures.append("the prune takes a different sink lock")

# A patch aimed at the canonical owner has to reach the call the producer
# makes, which is the whole point of it holding that object.
intercepted = []
owner.record_repo_skill_catalog = lambda **fields: intercepted.append(fields)
producer.recording.record_repo_skill_catalog(
    repo={repo!r}, base_branch="main", remote_name="origin", skills_available=[],
)
if len(intercepted) != 1:
    failures.append("a patch on the canonical owner missed the producer")
del owner.record_repo_skill_catalog

# Unpatched, the producer's own reference still writes through the sink the
# facade is configured with.
producer.recording.record_stage_enter(
    repo={repo!r}, issue={issue!r}, stage={stage!r},
)
if failures:
    sys.exit("; ".join(failures))
"""


# The sharper owner-first case: a caller that named the recorder itself rather
# than the package holds a function the rebuild never rebinds. It still has to
# serialize against the prune, which is what the probe below drives -- the
# facade is initialized by that very function's first call, so the lock it
# takes is decided before the prune's lock exists.
_STRANDED_APPEND_PROBE = """
import os
import sys
import threading

os.environ["ORCHESTRATOR_SKIP_DOTENV"] = "1"
os.environ["ANALYTICS_LOG_PATH"] = {path!r}

from orchestrator.observability.analytics.recording import (
    append_record,
    build_record,
)

if "orchestrator.analytics" in sys.modules:
    sys.exit("importing the owner planted the compatibility package")

record = build_record(repo={repo!r}, issue={issue!r}, event={event!r})

# Resolving the settings holder is what imports the compatibility package,
# and initializing it is what rebuilds `events` underneath this function.
append_record(record)

from orchestrator import analytics

prune_lock = analytics._retention._FILE_LOCK


def _append_again():
    append_record(record)
    appended.set()


# A `threading.Lock` is not reentrant, so holding the lock the prune takes is
# enough to tell whether this append takes the same object. Left on a lock of
# its own it would sail straight through and write into the file a prune is
# rewriting underneath it.
appended = threading.Event()
worker = threading.Thread(target=_append_again, daemon=True)
prune_lock.acquire()
worker.start()
raced = appended.wait(0.25)
prune_lock.release()
worker.join(10)
if raced:
    sys.exit("a directly held append_record does not take the prune's lock")
if not appended.is_set():
    sys.exit("the append never finished once the prune lock was released")
"""


class OwnerFirstImportTest(unittest.TestCase):
    """A producer that imported the owner first keeps a working, patchable
    package -- and a recorder taken off it keeps the sink lock the prune
    takes -- once the compatibility facade initializes behind it.
    """

    def test_facade_initializes_onto_producer_package(self) -> None:
        with tempfile.TemporaryDirectory() as sink_dir:
            sink = Path(sink_dir) / "a.jsonl"
            completed = _run_import_probe(_OWNER_FIRST_PROBE.format(
                path=str(sink),
                recorders=_RECORDERS,
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

    def test_stranded_append_takes_the_prune_lock(self) -> None:
        with tempfile.TemporaryDirectory() as sink_dir:
            sink = Path(sink_dir) / "a.jsonl"
            completed = _run_import_probe(_STRANDED_APPEND_PROBE.format(
                path=str(sink),
                repo=_REPO_SHORT,
                issue=_STRANDED_ISSUE,
                event=_EVENT_VALUE,
            ))
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            records = [
                json.loads(line)
                for line in sink.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        # Both appends land: serializing against the prune delays the second
        # one, it does not drop it.
        self.assertEqual(len(records), 2)
        self.assertEqual({record["issue"] for record in records}, {_STRANDED_ISSUE})


if __name__ == "__main__":
    unittest.main()
