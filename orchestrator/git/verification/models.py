# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Verification result model and the output budget it is sized to.

The budget lives beside the model because every `output` a caller receives
has already been redacted and truncated to it, so a change to one without
the other would publish output the model documents as post-budget.
"""
from __future__ import annotations

from dataclasses import dataclass

_VERIFY_OUTPUT_BUDGET = 4096


@dataclass(frozen=True)
class VerifyResult:
    """Outcome of running the configured `VERIFY_COMMANDS`.

    `status` is one of:

    * ``"ok"``           -- every command exited 0 and the worktree was clean.
    * ``"failed"``       -- a command exited non-zero.
    * ``"timeout"``      -- a command hit the per-command wall-clock cap.
    * ``"dirty"``        -- every command exited 0 but the worktree carried
                            uncommitted changes afterwards; treated as a
                            verify failure because handing off a dirty tree
                            to in_review would advertise the PR as ready for
                            human merge with state the dev never committed.
    * ``"head_changed"`` -- a command moved `HEAD` (it ran `git commit` or
                            `git reset` etc.) while leaving the tree clean.
                            Treated as a verify failure because the squash-
                            on-approval + force-push that follows would
                            otherwise publish an unreviewed verify-created
                            commit. `head_before` / `head_after` record the
                            SHAs so the operator can identify which commit
                            the verify produced.

    The non-ok fields (`command`, `exit_code`, `output`, `dirty_files`,
    `head_before` / `head_after`) are populated only for the case they
    describe and are otherwise None / empty so the formatter does not
    have to know the variant.

    `output` is already redacted (via `credentials.redact_secrets`) AND truncated to
    `_VERIFY_OUTPUT_BUDGET` bytes -- callers can post it verbatim. The
    redact pass runs before truncation so a secret straddling the cut
    cannot leak a partial value (see `_truncate_verify_output`).
    """

    status: str
    command: str | None = None
    exit_code: int | None = None
    output: str = ""
    dirty_files: tuple[str, ...] = ()
    head_before: str | None = None
    head_after: str | None = None
