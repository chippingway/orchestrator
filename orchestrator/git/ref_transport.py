# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Remote reads, writes, and deletes over the authenticated transport.

The reads and the two writes sit on one owner because they are one contract: a
caller establishes what the remote carries and then states that reading back as
the lease its write is pinned to. There is no form here that overwrites
whatever it finds, which is what an immutable ref namespace is owned through --
an empty lease says the ref must not exist, and any other value says it must
still be exactly what was read.

The reads are asked of the remote rather than of a local ref because the object
store a worktree shares is writable by the agent running in it: a local ref
that looks like the answer proves nothing, while the remote's own answer is the
one nothing on this host can rewrite. They are the lower half of every remote
question the git layer asks -- the branch transport beside this module spends
one of them on `refs/heads/<branch>`.

Two shapes of read, because two questions are put to a remote. What one named
ref is at is what a lease is pinned to; what a remote carries under a PATTERN
is what says an artifact is there at all, which is the only way a branch this
host no longer holds a copy of can be found.

Every call runs under the whole token-bearing envelope: a token resolved per
repository through `credentials`, an askpass session that keeps it out of the
world-readable `/proc/<pid>/cmdline`, global and system config detached, hooks,
credential helpers, and fsmonitor disabled by `-c`, and a refusal when the
worktree's local config carries a url rewrite or an `http.*` setting that could
redirect the call to an attacker-controlled host. The session carries the token
back here for the one thing the environment cannot do: scrubbing it out of the
stderr a failed call is logged with -- and handed back on, since the caller that
has to explain a reading it could not take is a long way from the process that
took it.

What policy the leases serve -- which namespace, and what an existing ref at
another commit means -- belongs to `git/snapshots/`, which is the only caller
of the writes.
"""
from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from orchestrator import config
from orchestrator.git import commands, credentials, locks

# The channel is named for the git-plumbing domain rather than for this
# module's path: operators filter the rendered `orchestrator.git_plumbing`
# prefix and attach handlers to it, so every read and update refusal reports
# where their filters already point.
log = logging.getLogger("orchestrator.git_plumbing")

_PUSH = "push"

# What a read that failed with nothing on its stderr says for itself, so a
# detail is empty only where a read SUCCEEDED and answered "no such ref".
_SAID_NOTHING = "git reported no reason"


@dataclass(frozen=True)
class _RefRead:
    """What the remote says a ref is at, and why a read that failed did.

    The two fields answer different callers. `sha` is the reading -- a commit
    id, "" where the remote does not carry the ref at all, and None where the
    read established nothing -- and it is the only thing a lease or a freeze
    may be pinned to. `detail` is the one line of git's own stderr that says
    WHY nothing was established, carried so a caller reporting a failure to an
    operator can say which of the many ways a token-bearing read fails this
    one was: a rejected token, an unreachable host, a repository the token
    cannot see. It is scrubbed of the token before it is set, because a
    diagnostic that leaks the secret is one no caller could safely log.

    Empty exactly where `sha` is not None: a read that answered, even with "",
    has nothing to explain.
    """

    sha: str | None = None
    detail: str = ""


@dataclass(frozen=True)
class _RefUpdate:
    """One lease-pinned write to a fully-qualified ref, and what it is called.

    Carried as a record rather than as four arguments because the four are one
    decision: the ref names what is being written, the refspec says whether
    that is a commit or a deletion, the lease says what the caller established
    was there first, and the name is what a refusal is reported as. A caller
    assembling three of them and forgetting the fourth would be pushing
    without a lease, which is the one thing this transport does not do.
    """

    ref: str
    refspec: str
    expected: str
    operation: str


def _remote_ref_read(
    auth_session: credentials._GitAuthSession,
    worktree: Path,
    label: str,
    ref: str,
) -> _RefRead:
    """Return what the remote says `ref` is at through an open session.

    "" where the remote does not carry that ref at all, and None where the read
    established nothing, so a caller can tell an answer apart from a failure.
    `label` is what a failed read is reported as -- the branch a caller asked
    about rather than the refname it was spelled as.

    A failure is reported to the operator AND handed back. The log line is
    where somebody watching the plumbing sees it; the record is for the caller
    that has to say why a decision it owns could not be taken, minutes later
    and somewhere else, where nothing has this stderr any more. Both spend the
    same scrubbed text, so the token cannot reach either.
    """
    ls_remote = subprocess.run(
        [*commands._AUTHED_GIT_PREFIX, "ls-remote", auth_session.auth_url, ref],
        cwd=str(worktree),
        capture_output=True,
        text=True,
        env=auth_session.env,
        check=False,
    )
    if ls_remote.returncode != 0:
        scrubbed = credentials._scrubbed(
            ls_remote.stderr, auth_session.token,
        )
        log.error("git ls-remote failed for %s: %s", label, scrubbed)
        return _RefRead(
            detail=commands._first_reported_line(scrubbed) or _SAID_NOTHING,
        )
    for output_line in (ls_remote.stdout or "").splitlines():
        parts = output_line.strip().split()
        if len(parts) >= 2 and parts[1] == ref:
            return _RefRead(sha=parts[0])
    return _RefRead(sha="")


def _remote_ref_sha(
    spec: config.RepoSpec, worktree: Path, ref: str,
) -> str | None:
    """Ask the REMOTE what one fully-qualified ref resolves to.

    The read every snapshot decision is made on, and it is taken from the
    remote rather than from a local ref for the reason the branch tip read is:
    the object store a worktree shares is writable by the agent that runs in
    it, so a local ref that looks like the snapshot proves nothing about what
    the remote actually carries.

    Three answers, and the caller has to tell them apart. A SHA is the ref as
    the remote holds it. "" is the remote saying it does not carry that ref at
    all, which is what makes an absent-is-success deletion and a create that
    may proceed possible. None established nothing -- a missing token, a
    worktree whose config could hijack the transport, an unreachable remote --
    and a caller that created or deleted on the strength of it would be acting
    on a reading nobody gave.
    """
    token = credentials._resolved_git_token(spec, "read the remote ref")
    if not token:
        return None
    unsafe = commands._unsafe_local_transport_config(worktree)
    if unsafe:
        log.error(
            "refusing to read %s from the remote: worktree .git/config has "
            "transport-hijacking config: %s", ref, unsafe,
        )
        return None
    with credentials._git_auth_session(spec, token) as auth_session:
        return _remote_ref_read(auth_session, worktree, ref, ref).sha


def _remote_ref_listing(
    auth_session: credentials._GitAuthSession,
    worktree: Path,
    pattern: str,
) -> tuple[str, ...] | None:
    """Every refname the remote carries under `pattern`, through an open session.

    The empty tuple where the remote carries none, and None where the listing
    established nothing, so a caller cannot read a failed call as a remote
    holding nothing under that namespace.

    `--refs` is asked for so a tag's peeled entry cannot arrive as a refname
    of its own; the pattern is passed as git's own, which matches across `/`
    and so covers a namespace however many components deep its members are.

    A line that does not carry both fields is dropped rather than refused,
    which is the safe direction for the one thing this listing is spent on: a
    name that never arrives is an artifact nobody goes on to act on, while a
    listing refused wholesale over one odd line would take every healthy name
    beside it down too.
    """
    listed = subprocess.run(
        [
            *commands._AUTHED_GIT_PREFIX,
            "ls-remote", "--refs", auth_session.auth_url, pattern,
        ],
        cwd=str(worktree),
        capture_output=True,
        text=True,
        env=auth_session.env,
        check=False,
    )
    if listed.returncode != 0:
        log.error(
            "git ls-remote failed for %s: %s",
            pattern, credentials._scrubbed(listed.stderr, auth_session.token),
        )
        return None
    named = (
        output_line.strip().split() for output_line in
        (listed.stdout or "").splitlines()
    )
    return tuple(parts[1] for parts in named if len(parts) >= 2)


def _remote_ref_names(
    spec: config.RepoSpec, worktree: Path, *, pattern: str,
) -> tuple[str, ...] | None:
    """Ask the REMOTE which refs it carries under one pattern.

    The read that finds an artifact this host holds no copy of. Every other
    remote question here starts from a name somebody already has -- a branch
    the clone still carries, a snapshot ref a record names -- so a branch whose
    local ref was deleted, or whose whole clone was rebuilt, is invisible to
    all of them while the remote still carries it.

    Two answers a caller must keep apart, as with every read on this owner: the
    empty tuple is the remote answering that it holds nothing under the
    pattern, and None is a read that established nothing -- a missing token, a
    worktree whose config could hijack the transport, an unreachable remote.
    A caller that took the second for the first would conclude a repository has
    no artifacts left because nobody could ask it.
    """
    token = credentials._resolved_git_token(spec, "list the remote refs")
    if not token:
        return None
    unsafe = commands._unsafe_local_transport_config(worktree)
    if unsafe:
        log.error(
            "refusing to list %s from the remote: worktree .git/config has "
            "transport-hijacking config: %s", pattern, unsafe,
        )
        return None
    with credentials._git_auth_session(spec, token) as auth_session:
        return _remote_ref_listing(auth_session, worktree, pattern)


def _push_ref(
    spec: config.RepoSpec,
    worktree: Path,
    *,
    ref: str,
    revision: str,
    expected: str,
) -> bool:
    """Publish one exact commit under one fully-qualified ref.

    `expected` is the SHA the caller established the remote ref was at, and it
    is required rather than optional: this is the transport an immutable ref
    namespace is written through, so it has no form that overwrites whatever
    happens to be there. An empty string is the lease saying the ref must not
    exist, which is how a snapshot is created; any other value is the lease
    saying it must still be exactly what the caller read.

    The revision is named rather than pushed as `HEAD`, for the reason the
    branch push takes one: what is published is a commit somebody proved, and
    HEAD between the proof and the push is not necessarily still it.
    """
    return _authed_ref_update(spec, worktree, _RefUpdate(
        ref=ref,
        refspec=f"{revision}:{ref}",
        expected=expected,
        operation=_PUSH,
    ))


def _delete_remote_ref(
    spec: config.RepoSpec, worktree: Path, *, ref: str, expected: str,
) -> bool:
    """Delete one fully-qualified ref the caller has just read.

    Pinned to what that read said, for the reason the create is: a ref
    somebody re-pointed between the read and the delete is not the ref this
    caller decided was reclaimable, and deleting it would destroy an artifact
    nobody adjudicated. A caller that found nothing there has nothing to
    delete and never reaches this.
    """
    return _authed_ref_update(spec, worktree, _RefUpdate(
        ref=ref,
        refspec=f":{ref}",
        expected=expected,
        operation="delete",
    ))


def _authed_ref_update(
    spec: config.RepoSpec, worktree: Path, update: _RefUpdate,
) -> bool:
    """Run one lease-pinned ref update under the whole transport envelope.

    The same envelope the branch push runs under -- per-spec token, askpass so
    the token never reaches argv, global and system config detached, hooks,
    credential helpers, and fsmonitor disabled by `-c`, and a refusal when the
    local config carries a url rewrite or an `http.*` setting that could
    redirect the token-bearing push -- because this call carries the same token
    to the same host.

    Held under the target-root lock, which the branch push does not need and
    this does: the namespace it writes is the one a verifying fetch reads back
    into the shared clone, so a concurrent fetch of the same namespace from
    another worktree of this target root would race the update it is proving.
    """
    token = credentials._resolved_git_token(spec, f"{update.operation} {update.ref}")
    if not token:
        return False
    unsafe = commands._unsafe_local_transport_config(worktree)
    if unsafe:
        log.error(
            "refusing to %s %s: worktree .git/config has "
            "transport-hijacking config: %s",
            update.operation, update.ref, unsafe,
        )
        return False
    with credentials._git_auth_session(spec, token) as auth_session:
        with locks._target_root_lock(spec.target_root):
            updated = subprocess.run(
                [
                    *commands._AUTHED_GIT_PREFIX,
                    _PUSH,
                    f"--force-with-lease={update.ref}:{update.expected}",
                    auth_session.auth_url,
                    update.refspec,
                ],
                cwd=str(worktree),
                capture_output=True,
                text=True,
                env=auth_session.env,
                check=False,
            )
        if updated.returncode == 0:
            return True
        log.error(
            "git %s failed for %s: %s",
            update.operation,
            update.ref,
            credentials._scrubbed(updated.stderr, auth_session.token),
        )
    return False
