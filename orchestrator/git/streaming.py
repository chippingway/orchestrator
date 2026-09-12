# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Hardened git execution for an answer this process may not hold whole.

Its own owner because what happens here differs from the runners beside it in
kind rather than in capture. Those spend one `subprocess.run` and come back
holding everything git wrote, which is affordable exactly while the size of
that is the size of a listing. This one takes its request on stdin, hands
stdout to a consumer a chunk at a time, and assembles none of it, so the peak
is one chunk however large the answer is -- and the caller it exists for is
folding the content of every object in a contribution into a digest, where an
agent decides how large that is.

The argv prefix and the environment are read straight off `commands`, where
the policy every hardened call is spawned under is decided. They are the
hardening itself -- the detached global and system config, the `-c` overrides
over a `.git/config` an agent can write, the disabled object replacement, the
injected committer identity -- and a copy of any of it here would be free to
lose a protection the original still has, with nothing at either call site
showing the difference.
"""
from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Callable, Mapping
from functools import partial
from pathlib import Path

from orchestrator.git import commands

# How much of a streamed answer is held at once. Large enough that reading a
# whole contribution's content is not a syscall per line, small enough that the
# size of what is being read decides nothing about this process's memory.
_CHUNK = 65536


def _git_hardened_streamed(
    *args: str,
    cwd: Path,
    stdin_bytes: bytes,
    consume: Callable[[bytes], object],
    env_extra: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """`commands._git_hardened_bytes` for output too big to hold, in pieces.

    The same argv prefix and the same environment; what differs is that stdout
    is passed to `consume` a chunk at a time and never assembled. The caller
    this exists for is folding git's output into a digest, and the output is
    the content of every object in a contribution -- which an agent decides
    the size of. Captured whole, one committed file would be as much of this
    process's memory as somebody cared to make it; captured in chunks, the
    peak is one chunk however large the contribution is.

    Both of the child's other streams are files rather than pipes, which is
    what makes reading stdout to exhaustion safe: git can write as much stderr
    as it likes without filling a pipe nobody is draining, and it reads its
    whole request without this process having to interleave writing that with
    reading the answer. What it wrote to stderr comes back on the result, so a
    caller that streams and refuses can still say what git said.

    `env_extra` is what it is on the runners in `commands`, and a caller that
    pins a reading passes the same pins here: the answer streamed back has to
    be the one the rest of that reading was taken under.

    The record handed back is the same `CompletedProcess` those runners answer
    with, minus a `stdout` there deliberately is not one of.
    """
    argv = [*commands._HARDENED_GIT_PREFIX, *args]
    with tempfile.TemporaryFile() as asked, tempfile.TemporaryFile() as said:
        asked.write(stdin_bytes)
        asked.seek(0)
        with subprocess.Popen(
            argv,
            cwd=str(cwd),
            stdin=asked,
            stdout=subprocess.PIPE,
            stderr=said,
            env=commands._hardened_env(env_extra),
        ) as streaming:
            _drain(streaming.stdout, consume)
            status = streaming.wait()
        said.seek(0)
        return subprocess.CompletedProcess(
            args=argv, returncode=status, stderr=said.read(),
        )


def _drain(stream, consume: Callable[[bytes], object]) -> None:
    """Hand a child's output to `consume` a chunk at a time, to exhaustion.

    Read to EOF rather than to a size, since what is being read is as long as
    an agent's committed content makes it; the chunk bounds what is held, not
    what is read.
    """
    for chunk in iter(partial(stream.read, _CHUNK), b""):
        consume(chunk)
