# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What the streamed runner hands over, and the policy it is spawned under."""

from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path
from types import MappingProxyType
from unittest.mock import MagicMock, patch

from orchestrator.git import commands, streaming
from tests.git.transport_helpers import _temp_git_repo_with_local_config

GIT = "git"
DIFF = "diff"
SUBPROCESS_RUN = "subprocess.run"
SUBPROCESS_POPEN = "subprocess.Popen"
ENV_KEY = "env"
WORKTREE = Path("/tmp/orchestrator-test-git-streaming")

# A revision no repository built here resolves, so git fails and says why.
ABSENT_REVISION = "no/such/revision"

# What a caller pinning one reading states for it, over the envelope every
# hardened call already runs under.
PINNED_READING = MappingProxyType({"GIT_NO_LAZY_FETCH": "1"})

# One committed payload, and the identity a temporary repository inheriting no
# config has to be handed to commit it at all.
BLOB_NAME = "streamed.bin"
BLOB_CONTENT = b"\x00streamed content\xff"
COMMIT_IDENTITY = MappingProxyType({
    "GIT_AUTHOR_NAME": "Dev",
    "GIT_AUTHOR_EMAIL": "dev@example.com",
    "GIT_COMMITTER_NAME": "Dev",
    "GIT_COMMITTER_EMAIL": "dev@example.com",
})


class StreamedSpawnTest(unittest.TestCase):
    """The streamed child is spawned under the command owner's own policy."""

    def test_the_spawn_reads_the_hardening_it_shares(self) -> None:
        # A copy of the prefix or the environment beside this runner is free
        # to lose a protection the runners in `commands` still have, and
        # nothing at any call site would show it.
        subprocess_run = MagicMock(
            return_value=MagicMock(returncode=0, stdout="", stderr=""),
        )
        popen = MagicMock()
        child = popen.return_value.__enter__.return_value
        child.stdout.read.return_value = b""

        with patch(SUBPROCESS_RUN, subprocess_run), patch(SUBPROCESS_POPEN, popen):
            commands._git_hardened(DIFF, cwd=WORKTREE)
            hardened = subprocess_run.call_args
            streaming._git_hardened_streamed(
                DIFF, cwd=WORKTREE, stdin_bytes=b"", consume=len,
                env_extra=PINNED_READING,
            )

        self.assertEqual(popen.call_args.args[0], hardened.args[0])
        # A caller that pins a reading pins the streamed half of it too, and
        # what it states goes over the envelope rather than beside it.
        self.assertEqual(
            popen.call_args.kwargs[ENV_KEY],
            {**hardened.kwargs[ENV_KEY], **PINNED_READING},
        )


class StreamedOutputTest(unittest.TestCase):
    """Every byte git wrote arrives, and none of it is held."""

    def test_streamed_output_is_handed_over_whole(self) -> None:
        # A caller folding git's output into a digest gets every byte of it
        # and holds none: the pieces arrive in order and add up to what git
        # wrote, and there is no `stdout` on the record to have kept them in.
        chunks = []

        with _temp_git_repo_with_local_config([]) as repo:
            written = self._committed_blob(repo)
            streamed = streaming._git_hardened_streamed(
                "cat-file", "--batch", cwd=repo,
                stdin_bytes=f"{written}\n".encode(),
                consume=chunks.append,
            )

        self.assertEqual(streamed.returncode, 0)
        self.assertIsNone(streamed.stdout)
        self.assertEqual(
            b"".join(chunks),
            b"".join((
                f"{written} blob {len(BLOB_CONTENT)}\n".encode(),
                BLOB_CONTENT,
                b"\n",
            )),
        )

    def test_a_streamed_failure_reports_what_git_said(self) -> None:
        # Streaming discards no diagnostic: stderr goes to a file rather than
        # to a pipe nobody drains, and comes back on the record so a caller
        # that refuses can still say why.
        with _temp_git_repo_with_local_config([]) as repo:
            streamed = streaming._git_hardened_streamed(
                "rev-parse", "--verify", ABSENT_REVISION,
                cwd=repo, stdin_bytes=b"", consume=lambda chunk: None,
            )

        self.assertNotEqual(streamed.returncode, 0)
        self.assertTrue(streamed.stderr)

    def _committed_blob(self, repo) -> str:
        """Commit one known payload in `repo`, and name the blob it became."""
        (repo / BLOB_NAME).write_bytes(BLOB_CONTENT)
        for argv in (["add", "-A"], ["commit", "-qm", "blob"]):
            subprocess.run(
                [GIT, *argv], cwd=repo, check=True,
                capture_output=True, env={**os.environ, **COMMIT_IDENTITY},
            )
        named = subprocess.run(
            [GIT, "rev-parse", f"HEAD:{BLOB_NAME}"],
            cwd=repo, check=True, capture_output=True, text=True,
        )
        return named.stdout.strip()


if __name__ == "__main__":
    unittest.main()
