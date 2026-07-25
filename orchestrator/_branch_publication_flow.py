# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Branch publication flow."""
from __future__ import annotations

from orchestrator import branch_publication as _owner

_SquashPreparationError = _owner._SquashPreparationError
Issue = _owner.Issue
Optional = _owner.Optional
Path = _owner.Path
Tuple = _owner.Tuple
config = _owner.config


def _squash_and_force_push(
    spec: config.RepoSpec, worktree: Path, branch: str, issue: Issue,
) -> Tuple[bool, Optional[str], int, Optional[str]]:
    """Squash all commits since `origin/<base>` into one, force-push with lease.

    Returns `(success, new_head_sha, squashed_count, error_message)`:
      * `(True, sha, 0, None)` — nothing to squash (zero or one commit on top
        of base). Caller should leave state alone.
      * `(True, sha, N, None)` — squashed N>1 commits into one. `sha` is the
        new local HEAD; the remote was force-pushed to match.
      * `(False, _, _, error)` — squash or push failed. Caller parks
        awaiting_human; the original commits remain on the local branch
        (we abort before resetting if any check fails) and the remote was
        not updated.

    The squash commit subject reuses the first commit's subject when it
    already carries a reusable `<prefix>:` form (Conventional or repo-local,
    so an `event:` / `career:` subject survives); otherwise it builds one
    from the issue title with `_infer_subject_prefix` -- a repo-local prefix
    when recent base history uses one, else `fix`/`feat`. The message is
    subject-only -- no body, no trailers -- so the orchestrator-authored
    squash matches the repo's subject-only commit rule. The commit is
    authored under the AGENT_GIT_* identity (via env vars) so attribution
    matches the per-step commits this squash replaces.
    """
    try:
        plan = _owner._prepare_squash(spec, worktree, issue)
    except _SquashPreparationError as error:
        return _owner._squash_failure(str(error))
    if len(plan.subjects) <= 1:
        return True, plan.original_head, 0, None
    return _owner._rewrite_squash(spec, worktree, branch, issue, plan)
