# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Plain and hardened git execution plus local transport probing.

The argv prefixes live here because every git invocation is assembled from
them: the hardened prefix extends the authenticated one that the
token-bearing fetch and push leaves run under, so the two cannot drift.

Output is decoded with `surrogateescape` rather than strictly. A repository
path is bytes on this platform, and git hands back exactly the bytes it has --
so a committed file whose name is not valid UTF-8 makes a strict decode raise
inside `subprocess` itself, before any caller can read a return code. What that
costs is the whole point: the probes reading these paths are the ones that
refuse to publish a branch carrying anything unexpected, and a raise there
takes the tick out rather than parking the artifact that caused it. Decoded
with surrogates, such a path comes back as a path -- unequal to whatever the
caller permitted, which is the answer it was asking for.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from orchestrator import config

_GIT_NO_PROMPT_ENV: Mapping[str, str] = MappingProxyType({
    "GIT_TERMINAL_PROMPT": "0",
})

_GIT = "git"

_GIT_CONFIG_FLAG = "-c"

# How git's own output is turned into text. Paths are bytes on this platform
# and nothing guarantees they are UTF-8, so a byte that is not decodable is
# carried as a surrogate instead of raising out of `subprocess.run`.
_UNDECODABLE_BYTES = "surrogateescape"

_AUTHED_GIT_PREFIX = (
    _GIT,
    _GIT_CONFIG_FLAG, "core.hooksPath=/dev/null",
    _GIT_CONFIG_FLAG, "credential.helper=",
    _GIT_CONFIG_FLAG, "core.fsmonitor=",
)

_HARDENED_GIT_PREFIX = (
    *_AUTHED_GIT_PREFIX,
    _GIT_CONFIG_FLAG, "commit.gpgsign=false",
    _GIT_CONFIG_FLAG, "rebase.autoStash=false",
    # The graft file is disabled by pointing it at /dev/null, which git reads
    # as a graft file that happens to be empty and warns about on every call.
    # The deprecation notice is true and useless here, and it would otherwise
    # ride out on the stderr an operator is shown when an operation fails.
    _GIT_CONFIG_FLAG, "advice.graftFileDeprecated=false",
)

# The two ways a repository can be told to serve one object in place of
# another. Both are honored by every command that reads history, both live in
# the clone the agent's worktree shares, and neither is config: `refs/replace/`
# is a ref namespace and the graft file is a plain file in the git dir, so
# detaching global config and overriding `-c` settings does not touch either.
_NO_OBJECT_REPLACEMENT_ENV: Mapping[str, str] = MappingProxyType({
    "GIT_NO_REPLACE_OBJECTS": "1",
    "GIT_GRAFT_FILE": os.devnull,
})

_UNSAFE_TRANSPORT_CONFIG_RE = (
    r"^(url\..*\.(insteadof|pushinsteadof)|http\..*)$"
)


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_GIT, *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        errors=_UNDECODABLE_BYTES,
        env={**os.environ, **_GIT_NO_PROMPT_ENV},
    )


def _git_hardened(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    """`_git` plus the agent-hostile-environment hardening from `_push_branch`.

    Used for local git operations inside a worktree the agent can write to: a
    planted `core.hooksPath`, `core.fsmonitor`, or url rewrite rule in
    the worktree's `.git/config` (or in `~/.gitconfig`) would otherwise
    execute attacker code mid-operation or redirect a transient fetch to an
    attacker-controlled host, and a planted replacement object or graft would
    have git answer for a commit nobody wrote. Drops global/system git config so url
    `insteadOf` rewrites and host-wide hooks cannot apply, and disables
    repo-local hooks / fsmonitor / credential helpers / commit signing via
    `-c` overrides. No askpass is wired in -- this helper is for local-only
    operations (rebase, diff, rev-parse); push remains the only call site
    that handles GIT_TOKEN.

    Injects `GIT_AUTHOR_*` / `GIT_COMMITTER_*` env vars (matching the
    agent spawn's `agent_env`) so a `git rebase` that needs to replay
    commits doesn't fail with "Committer identity unknown" -- stripping
    global config also strips any `user.name` / `user.email` set there,
    and env vars take precedence over config.

    Object replacement is turned off for the same reason the config is
    detached, and it is the sharper of the two: an agent that writes
    `refs/replace/<commit>` or a line in `info/grafts` changes what git says a
    commit's tree and history ARE, without touching the commit anybody named.
    A check that reads a branch here and a push that sends the same SHA would
    then be talking about two different things -- the reading measured against
    a synthetic stand-in, the push carrying the real commits. Refs and the
    graft file are not config, so nothing above disables them; the two env
    vars here do.
    """
    env = {
        **os.environ,
        **_GIT_NO_PROMPT_ENV,
        **_NO_OBJECT_REPLACEMENT_ENV,
        "GIT_AUTHOR_NAME": config.AGENT_GIT_NAME,
        "GIT_AUTHOR_EMAIL": config.AGENT_GIT_EMAIL,
        "GIT_COMMITTER_NAME": config.AGENT_GIT_NAME,
        "GIT_COMMITTER_EMAIL": config.AGENT_GIT_EMAIL,
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
    }
    return subprocess.run(
        [*_HARDENED_GIT_PREFIX, *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        errors=_UNDECODABLE_BYTES,
        env=env,
    )


def _unsafe_local_transport_config(cwd: Path) -> str:
    """Return non-global git config in `cwd` that could hijack token transport.

    Scans the exact config view a token-bearing fetch/push honors: the local
    config plus any `include.path` file it pulls in and, when
    `extensions.worktreeConfig` is set, the per-worktree `config.worktree` --
    with global/system config detached (the same `GIT_CONFIG_GLOBAL`/`SYSTEM`
    envelope the fetch/push runs under). It deliberately does NOT scope to
    `--local`: a `git config --local` probe reads only the raw local file, so
    it misses `include.path` targets and per-worktree config that the real
    command still resolves and honors. Returns the matching
    `git config --get-regexp` lines joined for logging, or "" when the config
    view is clean; callers refuse to run any GIT_TOKEN-bearing git command
    while the result is non-empty.
    """
    probe = subprocess.run(
        [_GIT, "config", "--get-regexp", _UNSAFE_TRANSPORT_CONFIG_RE],
        cwd=str(cwd), capture_output=True, text=True,
        errors=_UNDECODABLE_BYTES,
        env={
            **os.environ,
            **_GIT_NO_PROMPT_ENV,
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
        },
    )
    if probe.returncode == 0 and probe.stdout.strip():
        return probe.stdout.strip()
    return ""
