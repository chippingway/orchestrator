# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Subprocess envelopes and transport probing owned by the command module."""

from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path
from types import MappingProxyType
from unittest.mock import MagicMock, patch

from orchestrator import config
from orchestrator.git import commands
from tests.git.transport_helpers import _temp_git_repo_with_local_config

GIT = "git"
DIFF = "diff"
SUBPROCESS_RUN = "subprocess.run"
SUBPROCESS_POPEN = "subprocess.Popen"
ENV_KEY = "env"
HTTP_PROXY_KEY = "http.proxy"
PROXY_URL = "http://evil.example:8080"
WORKTREE = Path("/tmp/orchestrator-test-git-commands")

WORK_TREE_FLAG = "--work-tree"

# A worktree path in the shape `WORKTREES_DIR` produces when it is configured
# relative -- as the default derived from a relative `TARGET_ROOT` is.
RELATIVE_WORKTREE = Path("../wt-orchestrator/owner__name/issue-7")

# A legal filename carrying the one byte pair a decoded capture destroys.
CARRIAGE_RETURN_NAME = "carriage\r\nreturn.txt"

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

# The `-c` overrides that keep an agent-writable `.git/config` from executing
# code or rewriting transport during a local git operation.
HARDENING_OVERRIDES = (
    "core.hooksPath=/dev/null",
    "credential.helper=",
    "core.fsmonitor=",
    "commit.gpgsign=false",
    "rebase.autoStash=false",
)


def _recorded_run() -> MagicMock:
    """Return a `subprocess.run` double reporting a successful command."""
    return MagicMock(
        return_value=MagicMock(returncode=0, stdout="", stderr=""),
    )


class GitExecutionTest(unittest.TestCase):
    """The plain and hardened runners keep their subprocess envelopes."""

    def test_plain_git_blocks_the_terminal_prompt(self) -> None:
        # Under systemd there is no terminal to answer a credential prompt, so
        # a prompting git command would hang the worker instead of failing.
        subprocess_run = _recorded_run()

        with patch(SUBPROCESS_RUN, subprocess_run):
            commands._git("status", "--porcelain", cwd=WORKTREE)

        self.assertEqual(
            subprocess_run.call_args.args[0],
            [GIT, "status", "--porcelain"],
        )
        self.assertEqual(subprocess_run.call_args.kwargs["cwd"], str(WORKTREE))
        self.assertEqual(
            subprocess_run.call_args.kwargs[ENV_KEY]["GIT_TERMINAL_PROMPT"],
            "0",
        )

    def test_hardened_git_blocks_planted_config(self) -> None:
        subprocess_run = _recorded_run()

        with patch(SUBPROCESS_RUN, subprocess_run):
            commands._git_hardened("rebase", "x", cwd=WORKTREE)

        argv = subprocess_run.call_args.args[0]
        self.assertEqual(argv[0], GIT)
        self.assertEqual(argv[-2:], ["rebase", "x"])
        for override in HARDENING_OVERRIDES:
            with self.subTest(override=override):
                self.assertEqual(argv[argv.index(override) - 1], "-c")

    def test_hardened_git_injects_the_agent_identity(self) -> None:
        # Hardening detaches global / system config, where `user.name` and
        # `user.email` normally live, so a rebase that replays commits fails
        # with "Committer identity unknown" without these env vars.
        subprocess_run = _recorded_run()

        with patch(SUBPROCESS_RUN, subprocess_run):
            commands._git_hardened("rebase", "x", cwd=WORKTREE)

        env = subprocess_run.call_args.kwargs[ENV_KEY]
        self.assertEqual(env.get("GIT_AUTHOR_NAME"), config.AGENT_GIT_NAME)
        self.assertEqual(env.get("GIT_AUTHOR_EMAIL"), config.AGENT_GIT_EMAIL)
        self.assertEqual(env.get("GIT_COMMITTER_NAME"), config.AGENT_GIT_NAME)
        self.assertEqual(env.get("GIT_COMMITTER_EMAIL"), config.AGENT_GIT_EMAIL)
        self.assertEqual(env.get("GIT_CONFIG_GLOBAL"), os.devnull)
        self.assertEqual(env.get("GIT_CONFIG_SYSTEM"), os.devnull)

    def test_hardened_git_disables_object_replacement(self) -> None:
        # `refs/replace/` and the graft file are not config, so detaching
        # global config and overriding `-c` settings leaves both standing --
        # and either one makes git answer for a commit nobody wrote. Only
        # these two env vars turn them off.
        subprocess_run = _recorded_run()

        with patch(SUBPROCESS_RUN, subprocess_run):
            commands._git_hardened("diff", "--name-only", cwd=WORKTREE)

        env = subprocess_run.call_args.kwargs[ENV_KEY]
        self.assertEqual(env.get("GIT_NO_REPLACE_OBJECTS"), "1")
        self.assertEqual(env.get("GIT_GRAFT_FILE"), os.devnull)


class HardenedByteCaptureTest(unittest.TestCase):
    """The undecoded runners keep the envelope and hand back the bytes."""

    def test_every_runner_shares_one_environment(self) -> None:
        # A second copy of the hardening is free to lose a protection the
        # others still have, and nothing at any call site would show it.
        subprocess_run = _recorded_run()
        popen = MagicMock()
        streaming = popen.return_value.__enter__.return_value
        streaming.stdout.read.return_value = b""

        with patch(SUBPROCESS_RUN, subprocess_run), patch(SUBPROCESS_POPEN, popen):
            commands._git_hardened(DIFF, cwd=WORKTREE)
            decoded = subprocess_run.call_args
            commands._git_hardened_bytes(DIFF, cwd=WORKTREE)
            undecoded = subprocess_run.call_args
            commands._git_hardened_streamed(
                DIFF, cwd=WORKTREE, stdin_bytes=b"", consume=len,
                env_extra=PINNED_READING,
            )

        self.assertEqual(undecoded.kwargs[ENV_KEY], decoded.kwargs[ENV_KEY])
        self.assertEqual(undecoded.args[0], decoded.args[0])
        self.assertEqual(popen.call_args.args[0], decoded.args[0])
        # A caller that pins a reading pins the streamed half of it too, and
        # what it states goes over the envelope rather than beside it.
        self.assertEqual(
            popen.call_args.kwargs[ENV_KEY],
            {**decoded.kwargs[ENV_KEY], **PINNED_READING},
        )

    def test_output_arrives_as_the_bytes_git_wrote(self) -> None:
        # Text capture folds a CR LF pair into a single LF. A path is bytes
        # and a carriage return is one of the bytes it may hold, so a caller
        # hashing a listing of paths would hash two different names alike.
        with _temp_git_repo_with_local_config([]) as repo:
            (repo / CARRIAGE_RETURN_NAME).write_text("x\n")
            subprocess.run(
                [GIT, "add", "-A"], cwd=repo, check=True, capture_output=True,
            )

            listed = commands._git_hardened_bytes("ls-files", "-z", cwd=repo)

        self.assertEqual(listed.returncode, 0)
        self.assertEqual(
            listed.stdout, os.fsencode(f"{CARRIAGE_RETURN_NAME}\0"),
        )

    def test_streamed_output_is_handed_over_whole(self) -> None:
        # A caller folding git's output into a digest gets every byte of it
        # and holds none: the pieces arrive in order and add up to what git
        # wrote, and there is no `stdout` on the record to have kept them in.
        chunks = []

        with _temp_git_repo_with_local_config([]) as repo:
            written = self._committed_blob(repo)
            streamed = commands._git_hardened_streamed(
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
            streamed = commands._git_hardened_streamed(
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


class WorkTreeArgumentTest(unittest.TestCase):
    """The tree a command acts on is named absolutely."""

    def test_a_relative_worktree_is_named_absolutely(self) -> None:
        # Every caller runs its command with `cwd` inside the worktree, and git
        # resolves a relative `--work-tree` against that cwd rather than this
        # process's -- so a relative path would name a directory beneath the
        # worktree itself, which does not exist, and git would refuse to run
        # the command at all.
        argument = commands._work_tree_arg(RELATIVE_WORKTREE)

        flag, _, named = argument.partition("=")
        self.assertEqual(flag, WORK_TREE_FLAG)
        self.assertTrue(Path(named).is_absolute())
        self.assertEqual(named, os.path.realpath(RELATIVE_WORKTREE))


class TransportConfigProbeTest(unittest.TestCase):
    """The probe flags config that could hijack a token-bearing transport."""

    def test_probe_flags_transport_keys(self) -> None:
        cases = {
            HTTP_PROXY_KEY: [(HTTP_PROXY_KEY, PROXY_URL)],
            "http.sslVerify=false": [("http.sslVerify", "false")],
            "url-scoped http.proxy": [
                ("http.https://github.com/.proxy", PROXY_URL),
            ],
            "url rewrite": [
                ("url.https://evil.example/.insteadOf", "https://github.com/"),
            ],
        }
        for label, pairs in cases.items():
            with self.subTest(config=label):
                with _temp_git_repo_with_local_config(pairs) as repo:
                    flagged = commands._unsafe_local_transport_config(repo)
                self.assertTrue(flagged, f"{label} should be rejected, got {flagged!r}")

    def test_probe_allows_clean_clone_config(self) -> None:
        clean = [
            ("remote.origin.url", "https://github.com/acme/widgets.git"),
            ("branch.main.remote", "origin"),
            ("core.logAllRefUpdates", "true"),
        ]
        with _temp_git_repo_with_local_config(clean) as repo:
            self.assertEqual(commands._unsafe_local_transport_config(repo), "")

    def test_probe_follows_local_include_path(self) -> None:
        with _temp_git_repo_with_local_config([]) as repo:
            evil = repo / "evil.conf"
            evil.write_text(f"[http]\n\tproxy = {PROXY_URL}\n")
            subprocess.run(
                [GIT, "config", "--local", "include.path", str(evil)],
                cwd=repo,
                check=True,
                capture_output=True,
            )
            self.assertIn(
                HTTP_PROXY_KEY,
                commands._unsafe_local_transport_config(repo),
            )

    def test_probe_reads_per_worktree_config(self) -> None:
        with _temp_git_repo_with_local_config([("extensions.worktreeConfig", "true")]) as repo:
            subprocess.run(
                [GIT, "config", "--worktree", HTTP_PROXY_KEY, PROXY_URL],
                cwd=repo,
                check=True,
                capture_output=True,
            )
            self.assertIn(
                HTTP_PROXY_KEY,
                commands._unsafe_local_transport_config(repo),
            )


if __name__ == "__main__":
    unittest.main()
