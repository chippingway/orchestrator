# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Token-bearing git fetches and the askpass session they run under.

Token resolution, the askpass session, and the two fetches share this
module because the token only ever travels through the session: the
session writes the askpass script that prints it and builds the
environment that carries it, and the fetches pass that environment
along with an argv that names nothing but the `x-access-token`
username. Splitting them would put a raw token on a module boundary.
"""
from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

from orchestrator import config
from orchestrator.git import commands, locks

# Named for the historical facade, not this module: operators filter the
# rendered `orchestrator.git_plumbing` prefix and attach handlers to that
# logger, and the push leaf still refuses transport on the same channel.
# Resolving it by name rather than importing the leaf keeps this owner
# self-contained while landing both refusals in one place.
log = logging.getLogger("orchestrator.git_plumbing")

_FETCH = "fetch"

_ASKPASS_MODE = 0o700


@dataclass(frozen=True)
class _GitAuthSession:
    """Token-bearing subprocess inputs scoped to one askpass directory."""

    token: str
    auth_url: str
    env: dict[str, str]


def _resolved_git_token(spec: config.RepoSpec, operation: str) -> Optional[str]:
    """Resolve a per-repository token and log an operation-specific error."""
    token = config._resolve_github_token(spec.slug)
    if token:
        return token
    log.error(
        "GITHUB_TOKEN missing for %s; cannot %s", spec.slug, operation,
    )
    return None


def _git_auth_env(
    askpass: Path, token: str, *, include_identity: bool,
) -> dict[str, str]:
    """Build the detached environment for one token-bearing git command."""
    auth_env = {
        **os.environ,
        **commands._GIT_NO_PROMPT_ENV,
        "GIT_ASKPASS": str(askpass),
        "GIT_TOKEN": token,
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
    }
    if include_identity:
        auth_env.update(
            {
                "GIT_AUTHOR_NAME": config.AGENT_GIT_NAME,
                "GIT_AUTHOR_EMAIL": config.AGENT_GIT_EMAIL,
                "GIT_COMMITTER_NAME": config.AGENT_GIT_NAME,
                "GIT_COMMITTER_EMAIL": config.AGENT_GIT_EMAIL,
            },
        )
    return auth_env


@contextmanager
def _git_auth_session(
    spec: config.RepoSpec, token: str, *, include_identity: bool = False,
) -> Iterator[_GitAuthSession]:
    """Keep a hardened askpass script alive for one authenticated operation."""
    with tempfile.TemporaryDirectory(prefix="orch-askpass-") as temp_dir:
        askpass = Path(temp_dir) / "askpass.sh"
        askpass.write_text('#!/bin/sh\nprintf %s "$GIT_TOKEN"\n')
        askpass.chmod(_ASKPASS_MODE)
        yield _GitAuthSession(
            token=token,
            auth_url=f"https://x-access-token@github.com/{spec.slug}.git",
            env=_git_auth_env(
                askpass, token, include_identity=include_identity,
            ),
        )


def _failed_fetch(stderr: str) -> subprocess.CompletedProcess:
    """Return the stable failure shape shared by authenticated fetches."""
    return subprocess.CompletedProcess(
        args=[commands._GIT, _FETCH], returncode=1, stdout="", stderr=stderr,
    )


def _authed_fetch(
    spec: config.RepoSpec, refspec: str, *, cwd: Path
) -> subprocess.CompletedProcess:
    """Authenticated, hardened `git fetch` -- the same security envelope as
    `_push_branch`.

    Used for fetches from inside an agent-writable worktree where any
    of the following vectors could leak GIT_TOKEN to an attacker host:
      * a planted credential helper in the worktree's `.git/config`,
      * a planted `core.hooksPath` / `core.fsmonitor` that runs an
        attacker-controlled binary with GIT_TOKEN in env,
      * a planted `url.<host>.insteadOf` rewrite in the worktree's
        local config OR in `~/.gitconfig` redirecting fetch to an
        attacker-controlled host,
      * a planted `http.proxy` / `http.sslVerify=false` (or other
        `http.*` TLS/proxy key) in the worktree's local config routing
        the token-bearing fetch through an attacker proxy or disabling
        certificate verification.

    The auth URL carries only the username (`x-access-token`); the
    token itself is read from $GIT_TOKEN by a tempfile askpass script
    so it never appears in argv. Global/system git config is detached
    via `GIT_CONFIG_GLOBAL=/dev/null` / `GIT_CONFIG_SYSTEM=/dev/null`
    so url-rewrite rules planted there cannot apply. We also refuse to
    run if the worktree's local config carries any url-rewrite rule or
    `http.*` transport setting (`_unsafe_local_transport_config`),
    mirroring `_push_branch`'s pre-flight check.

    `refspec` is the fetch refspec; pass an explicit form like
    `+refs/heads/<branch>:refs/remotes/origin/<branch>` so single-branch
    clones still update the remote-tracking ref instead of leaving the
    fetched payload only in FETCH_HEAD.

    The fetch updates the parent clone's `refs/remotes/<remote>/...`
    namespace from inside an agent-writable worktree, which means it
    grabs the parent's ref-update lock under `<git-dir>/packed-refs.lock`
    and `<git-dir>/refs/remotes/<remote>/<branch>.lock`. Two concurrent
    `_authed_fetch` calls from different worktrees of the same
    `target_root` (the common shape during fan-out of multiple
    `resolving_conflict` issues) race those lock files and one fails
    with `Unable to create '...': File exists.`, parking the issue.
    The actual subprocess call is therefore held under the
    per-target_root lock; the pre-flight URL-rewrite check stays
    outside the lock since it only reads the worktree's own
    `.git/config`.
    """
    # Resolve the token from `spec.slug` rather than the cached
    # `config.GITHUB_TOKEN` (which was looked up once for `config.REPO`),
    # so a multi-repo deployment with one token file per slug under
    # `~/.config/<owner>/<repo>/token` fetches with the right repo's token.
    # Mirrors `_push_branch`'s per-spec token resolution; without this,
    # `_handle_resolving_conflict` would fail conflict resolution for any
    # repo other than the legacy `REPO` (or use the wrong token).
    token = _resolved_git_token(spec, _FETCH)
    if not token:
        return _failed_fetch("GITHUB_TOKEN missing")
    unsafe = commands._unsafe_local_transport_config(cwd)
    if unsafe:
        log.error(
            "refusing to fetch into %s: worktree .git/config has "
            "transport-hijacking config: %s", cwd, unsafe,
        )
        return _failed_fetch(
            "unsafe transport config in worktree .git/config",
        )
    with _git_auth_session(
        spec, token, include_identity=True,
    ) as auth_session:
        with locks._target_root_lock(spec.target_root):
            return subprocess.run(
                [
                    *commands._AUTHED_GIT_PREFIX,
                    _FETCH, "--quiet", auth_session.auth_url, refspec,
                ],
                cwd=str(cwd),
                capture_output=True,
                text=True,
                env=auth_session.env,
            )


def _authed_target_fetch(
    spec: config.RepoSpec, branch: str
) -> subprocess.CompletedProcess:
    """Authed `git fetch` into `spec.target_root` using the per-spec token.

    Replaces the plain `git fetch <remote_name> <branch>` invocations the
    worktree creators (`_ensure_worktree` / `_ensure_pr_worktree` /
    `_ensure_decompose_worktree`) and the per-tick base refresh
    (`_refresh_base_and_worktrees`) used to run. The plain form relied on
    git's ambient credential helper or session state, which fails under
    systemd (`GIT_TERMINAL_PROMPT=0` disables the fallback prompt) and
    has no way to pick a per-repo token when the local clone has several
    GitHub-pointing remotes whose `slug` differs from the
    `~/.config/<owner>/<repo>/token` of the configured `REPO`.

    The `spec.remote_name` field selects the local remote namespace --
    refs land under `refs/remotes/<spec.remote_name>/<branch>` -- while
    `spec.slug` selects which GitHub repo / token to authenticate with.
    Without this split, a `REPOS` row like
    `geserdugarov/lance-private|...|private-cache|private` would try to
    use the cached single-repo `config.GITHUB_TOKEN` (looked up once for
    `config.REPO`) and fail to fetch even with a correct per-spec token
    file in place.

    An explicit refspec `+refs/heads/<branch>:refs/remotes/<remote_name>/<branch>`
    is used so single-branch / narrowed clones still update the
    remote-tracking ref instead of leaving the fetched payload only in
    FETCH_HEAD -- the worktree creators then anchor `git worktree add`
    on `<remote>/<branch>` without surprise.

    Same security envelope as `_push_branch` / `_authed_fetch`: token
    delivered via GIT_ASKPASS (never argv), global/system git config
    detached so url-rewrite rules planted in `~/.gitconfig` cannot
    redirect the fetch to an attacker-controlled host, hooks /
    fsmonitor / credential helpers blocked via `-c` overrides. The
    target_root is normally operator-owned, but a linked worktree
    (which the agent does write) can still mutate the parent clone's
    local config via `git config --local`, and local config still
    applies even with GIT_CONFIG_GLOBAL/SYSTEM detached. Mirror the
    `_authed_fetch` / `_push_branch` pre-flight refusal: bail out if
    `target_root`'s local config carries any
    `url.<host>.(insteadOf|pushInsteadOf)` rule or `http.*` proxy/TLS
    setting that could redirect the token-bearing fetch to an
    attacker-controlled host or strip TLS verification
    (`_unsafe_local_transport_config`).

    Serialized via `_target_root_lock` (`RLock` so a caller already
    holding it -- the worktree creators -- re-enters cleanly) for the
    same `.git/config.lock` reason described on `_ensure_worktree`.
    """
    token = _resolved_git_token(spec, _FETCH)
    if not token:
        return _failed_fetch("GITHUB_TOKEN missing")
    unsafe = commands._unsafe_local_transport_config(spec.target_root)
    if unsafe:
        log.error(
            "refusing to fetch into %s: target_root .git/config has "
            "transport-hijacking config: %s", spec.target_root, unsafe,
        )
        return _failed_fetch(
            "unsafe transport config in target_root .git/config",
        )
    refspec = (
        f"+refs/heads/{branch}:refs/remotes/{spec.remote_name}/{branch}"
    )
    with _git_auth_session(spec, token) as auth_session:
        with locks._target_root_lock(spec.target_root):
            return subprocess.run(
                [
                    *commands._AUTHED_GIT_PREFIX,
                    _FETCH, "--quiet", auth_session.auth_url, refspec,
                ],
                cwd=str(spec.target_root),
                capture_output=True,
                text=True,
                env=auth_session.env,
            )
