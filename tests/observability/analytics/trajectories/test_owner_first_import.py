# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What survives when a caller names the append before the facade exists."""

import json
import tempfile
import unittest


from pathlib import Path


from tests.observability.observability_test_support import _run_import_probe

_SESSION_ID = "stranded"


# The owner-first case the rebuild has to survive: a caller that named the
# append itself holds a function no rebuild ever rebinds, and the facade is
# initialized by that very function's first call. It still has to serialize
# against the by-age prune, so the lock it takes is decided before the prune's
# lock exists -- which is why the lock is minted on an owner no reload
# rebuilds rather than beside the append that takes it.
_STRANDED_APPEND_PROBE = """
import os
import sys
import threading

os.environ["ORCHESTRATOR_SKIP_DOTENV"] = "1"
os.environ["TRAJECTORY_LOG_PATH"] = {path!r}

from orchestrator.observability.analytics.trajectories.api import (
    append_trajectory_record,
)

if "orchestrator.analytics" in sys.modules:
    sys.exit("importing the owner planted the compatibility package")

record = {{"ts": "2026-01-01T00:00:00+00:00", "session_id": {session!r}}}

# Resolving the settings holder is what imports the compatibility package,
# and initializing it is what rebuilds this function's owner underneath it.
append_trajectory_record(record)

from orchestrator import analytics

prune_lock = sys.modules[
    "orchestrator.observability.analytics.retention"
].TRAJECTORY_FILE_LOCK
if analytics._TRAJECTORY_FILE_LOCK is not prune_lock:
    sys.exit("the facade publishes a different lock than the prune takes")


def _append_again():
    append_trajectory_record(record)
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
    sys.exit("a directly held append_trajectory_record misses the prune's lock")
if not appended.is_set():
    sys.exit("the append never finished once the prune lock was released")
"""


class OwnerFirstTrajectoryAppendTest(unittest.TestCase):
    """An append taken off the owner before the compatibility facade existed
    keeps the sink lock the prune takes, across the rebuild that facade's
    initialization performs.
    """

    def test_stranded_append_takes_the_prune_lock(self) -> None:
        with tempfile.TemporaryDirectory() as sink_dir:
            sink = Path(sink_dir) / "t.jsonl"
            completed = _run_import_probe(_STRANDED_APPEND_PROBE.format(
                path=str(sink),
                session=_SESSION_ID,
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
        self.assertEqual({record["session_id"] for record in records}, {_SESSION_ID})


if __name__ == "__main__":
    unittest.main()
