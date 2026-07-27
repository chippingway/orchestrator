# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""One implementing tick, in the order its questions have to be asked.

Every check ahead of the spawn is there because running the agent first would
make it unanswerable. A merged PR or a closed issue ends the issue, so both are
read before anything spends tokens. A stale `question_*` park has to be cleared
or refused before the fresh-spawn path's recovered-worktree shortcut can publish
question-agent commits as a dev implementation. An operator's
`/orchestrator continue` has to be recognized before drift handling mistakes the
bare command for changed requirements. Only then is a body edit considered, and
only if that does not own the tick does the run get prepared.

After the run the order matters just as much: the interruption and live-pause
refusals both come BEFORE the disposition, and both return without writing
pinned state, so the staged in-memory mutations -- the cleared park, the
advanced watermark, the persisted session -- are dropped and the next process
re-derives the whole tick from what durable state still says.
"""
from __future__ import annotations

from github.Issue import Issue

from orchestrator import config
from orchestrator.github.client import GitHubClient
from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.engine import (
    drift as _engine_drift,
    guards as _guards,
    terminals as _terminals,
    usage as _usage,
)
from orchestrator.workflow.stages.implementing import (
    continue_command as _continue_command,
    disposition as _disposition,
    drift as _drift,
    question_relabel as _question_relabel,
    spawn as _spawn,
)


def _implementing_preflight(
    gh: GitHubClient, spec: config.RepoSpec, issue: Issue, state: PinnedState,
) -> bool:
    if _terminals._finalize_if_pr_merged(gh, spec, issue, state):
        return True
    if _terminals._finalize_if_issue_closed(gh, spec, issue, state):
        return True
    if _question_relabel._handle_stale_question_park(gh, spec, issue, state):
        return True
    if _continue_command._handle_parked_continue_command(gh, spec, issue, state):
        return True
    return False


def _handle_detected_implementing_drift(
    gh: GitHubClient, spec: config.RepoSpec, issue: Issue, state: PinnedState,
) -> bool:
    new_hash = _engine_drift._detect_user_content_change(gh, issue, state)
    return new_hash is not None and _drift._handle_user_content_drift(
        gh, spec, issue, state, new_hash,
    )


def _handle_implementing(gh: GitHubClient, spec: config.RepoSpec, issue: Issue) -> None:
    state = gh.read_pinned_state(issue)
    if _implementing_preflight(gh, spec, issue, state):
        return

    # User-content drift: a human edited the issue title/body after the dev
    # session was spawned. `_handle_user_content_drift` persists the new hash
    # and either resumes the locked session against the updated requirements
    # (returning True), parks recovered pre-edit work, or -- when no dev
    # session exists yet -- clears any park and returns False so the fresh-
    # spawn path below picks up the new body via `_build_implement_prompt`.
    if _handle_detected_implementing_drift(gh, spec, issue, state):
        return

    prepared = _spawn._prepare_dev_run(gh, spec, issue, state)
    if prepared is None:
        return

    state.set("last_agent_action_at", _usage._now_iso())

    # Shutdown-sweep interruption: a run the orchestrator killed mid-flight
    # has no trustworthy result, so ignore it and return WITHOUT writing
    # pinned state (the in-memory `awaiting_human=False` / watermark / session
    # mutations in `_prepare_dev_run` are discarded) so the next process
    # retries from durable state. Must precede the disposition below.
    if (
        _guards._ignore_if_interrupted(issue, prepared.agent_result)
        or prepared.paused
    ):
        return

    _disposition._dispose_agent_result(gh, spec, issue, state, prepared)
