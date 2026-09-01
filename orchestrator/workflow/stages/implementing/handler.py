# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""One implementing tick, in the order its questions have to be asked.

Every check ahead of the spawn is there because running the agent first would
make it unanswerable. A `discussion` this stage's own terminals cannot answer
for comes first of all: an unfinished round or publication is a record written
before the thing it describes, so an issue carrying one has a plan on its
branch and possibly a pull request open for it, and neither is anything a
terminal here may finalize on. A merged PR or a closed issue ends the issue, so
both are read next, before anything spends tokens. A stale read-only park
(`question_*` or `discussion_*`) has to be cleared or refused before the
fresh-spawn path's recovered-worktree shortcut can publish that agent's commits
as a dev implementation. An operator's `/orchestrator continue` has to be
recognized before drift handling mistakes the bare command for changed
requirements. Only then is a body edit considered, and only if that does not own
the tick does the run get prepared.

After the run the order matters just as much: the interruption and live-pause
refusals both come BEFORE the disposition, and both return without writing
pinned state, so the staged in-memory mutations -- the cleared park, the
advanced watermark, the persisted session -- are dropped and the next process
re-derives the whole tick from what durable state still says.
"""
from __future__ import annotations

import logging

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
from orchestrator.workflow.stages.discussion.state import (
    _PLAN_PATH as _DISCUSSION_PLAN_PATH,
    _PLAN_SHA as _DISCUSSION_PLAN_SHA,
)
from orchestrator.workflow.stages.implementing import (
    continue_command as _continue_command,
    disposition as _disposition,
    drift as _drift,
    read_only_relabel as _read_only_relabel,
    spawn as _spawn,
    state as _state,
)

log = logging.getLogger("orchestrator.workflow")


def _recorded_pr_is_the_plan(
    gh: GitHubClient,
    issue: Issue,
    state: PinnedState,
    head_sha: str | None = None,
) -> bool | None:
    """True while the PR this issue records still carries only the plan.

    The `discussion` stage publishes the agreed design as a PR and records its
    number in `pr_number`, so an issue relabeled here can arrive pointing at a
    PR that says what to build rather than a build -- and merging it is a human
    agreeing to the design, which is precisely when they relabel.

    Two records answer it, in the order they stop being true.
    `discussion_plan_path` is the durable one, and it is retired by THIS
    stage's own handoff, which is written before anything is spawned: while it
    stands nothing here has pushed, so the PR is the plan whatever its head
    says now. That distinction is the whole point of asking it first. A human
    correcting the Markdown on the plan PR, or pressing "update branch" before
    merging it, moves that head -- and read as this stage's work, the merge that
    follows would close the issue as `done` and clean up the branch with no
    developer ever having run.

    Past the handoff the commit is what settles it. `discussion_plan_sha` is
    what publication put on that PR, and the PR's head is asked for rather than
    assumed. That is what makes the answer right without depending on a write:
    the head moves the moment this stage pushes onto the same PR -- which is
    exactly when it stops being a plan -- so a tick that pushed and then died
    before persisting anything still leaves a PR that reads as an
    implementation here.

    A PR that cannot be fetched answers None rather than False. False is a
    claim -- "this is not the plan" -- and the caller acts on it by asking
    GitHub the same question again through the merged-PR terminal. A request
    that failed and then succeeded would answer the first question "not the
    plan" and the second "merged", and close the issue as `done` on the
    strength of a design document. What a failed fetch actually establishes is
    nothing, which is what the third answer says.

    `head_sha` is for the caller that already holds the snapshot it is about
    to ACT on, and it is the only thing that snapshot is asked for. The head
    is a mutable thing -- a human can push to a plan PR at any moment -- so a
    caller that classified one read and then mutated another has classified
    something it did not touch. Given the head it read, the answer is about
    that read, and there is no fetch left to fail: the third answer cannot
    arise.
    """
    pr_number = state.get(_state._PR_NUMBER)
    if pr_number is None:
        return False
    if state.get(_DISCUSSION_PLAN_PATH):
        return True
    plan_sha = state.get(_DISCUSSION_PLAN_SHA)
    if not plan_sha:
        return False
    if head_sha is None:
        try:
            head_sha = getattr(gh.get_pr(int(pr_number)).head, "sha", None)
        except Exception:
            log.exception(
                "issue=#%s could not fetch PR #%s while telling a plan from "
                "an implementation; deferring the tick",
                issue.number, pr_number,
            )
            return None
    return head_sha == plan_sha


def _recorded_pr_holds_the_tick(
    gh: GitHubClient, spec: config.RepoSpec, issue: Issue, state: PinnedState,
) -> bool:
    """True when the PR this issue records is why nothing else may run.

    Three answers, because the question ahead of the merged-PR terminal has
    three. A PR that is still the `discussion` stage's plan -- by its live
    record, or by the commit that record names -- lets the tick continue but
    must not finalize: closing the issue as `done` on a merged plan would end
    it without a developer ever running, on the strength of a document whose
    content is work still to do. A PR that is something else is
    handed to the terminal, which decides on the merge as it always has. And a
    PR that could not be read at all ends the tick here, unfinalized and
    unspawned: the terminal would fetch it a second time, and a request that
    failed once and succeeded next would finalize exactly the plan the first
    answer existed to protect. Nothing is written, so the next tick asks again
    from the same durable state.
    """
    plan_verdict = _recorded_pr_is_the_plan(gh, issue, state)
    if plan_verdict is None:
        return True
    if plan_verdict:
        return False
    return _terminals._finalize_if_pr_merged(gh, spec, issue, state)


def _unfinished_discussion_holds_the_tick(
    gh: GitHubClient, spec: config.RepoSpec, issue: Issue, state: PinnedState,
) -> bool:
    """Screen a crashed `discussion` before any terminal can answer for it.

    The same guard the preflight runs further down, hoisted ahead of the
    terminals for the one state that cannot wait for it. Both in-flight records
    are written BEFORE the thing they describe and neither depends on
    `awaiting_human`, so a tick that died after the plan commit -- or after the
    pull request it opened -- leaves an unparked issue whose branch carries the
    plan and whose `pr_number` is still whatever it arrived with.

    A relabel onto that state reaches the merged-PR terminal first, and the PR
    it reads is somebody else's: an implementation from a previous cycle, or a
    plan PR from a discussion that ran before this one. Merged, it closes the
    issue as `done`, deletes the branch the unfinished publication is sitting
    on, and leaves the marker standing on a terminal issue nothing will come
    back for. The plan is gone and the pull request it was published to is
    orphaned, on the strength of a merge that had nothing to do with either.

    So the records are read first and answer for the whole tick. What follows
    is the ordinary refusal -- the issue parks as `discussion_unsafe_relabel`
    naming the label that finishes what was started -- or, for a round that
    died before writing anything to the branch, the handoff those records are
    retired by, after which the terminals below run against a state that no
    longer claims an unfinished conversation.
    """
    if not _read_only_relabel._discussion_in_flight(state):
        return False
    return _read_only_relabel._handle_stale_read_only_park(gh, spec, issue, state)


def _implementing_preflight(
    gh: GitHubClient, spec: config.RepoSpec, issue: Issue, state: PinnedState,
) -> bool:
    """Everything asked before the recorded PR can be ruled on, in order.

    The read-only park is asked twice, and exactly one of the two does any
    work: the screen above returns immediately on an issue carrying no
    in-flight discussion record, and the call in `_terminal_or_relabel_holds`
    returns immediately on one that screen has just handed over.

    An accepted handoff the developer has not published on yet is caught up to
    its plan PR between them, ahead of the question that reads that PR: what
    the humans did to it since the handoff decides both what the PR IS and
    where the developer starts, and reading the first against a record their
    own edit moved is what would close the issue on a design.
    """
    if _unfinished_discussion_holds_the_tick(gh, spec, issue, state):
        return True
    if _read_only_relabel._reconcile_open_plan_handoff(gh, spec, issue, state):
        return True
    if _recorded_pr_holds_the_tick(gh, spec, issue, state):
        return True
    return _terminal_or_relabel_holds(gh, spec, issue, state)


def _terminal_or_relabel_holds(
    gh: GitHubClient, spec: config.RepoSpec, issue: Issue, state: PinnedState,
) -> bool:
    """The rest of the preflight: the closed-issue terminal, then the relabel.

    Each owns the tick outright when it answers, so they are asked in the order
    the cheapest irreversible one comes first -- a closed issue ends the issue,
    and there is nothing to hand over on one.

    The size gate's own park is answered ahead of the generic continue, and
    that order is the whole point: what failed there was a reading rather than
    a session, so the bare command has to reach a re-measurement of the commit
    that already exists. Left to the generic handler it would be refused as a
    continue with no guidance on it, and the committed candidate would sit
    parked behind a question nobody could answer.

    The handoff's own park is answered beside it, and quietly: what it refused
    was a checkout that had left the approved commit, so what settles it is
    the checkout coming back rather than anything a human could write. It is
    asked every tick and says nothing until the answer changes.

    A frozen candidate with NO park beside it is reconciled next, and it is
    the crash window the park would otherwise have covered: a tick that
    recorded the pair and died before counting it leaves nothing on the issue
    saying the workflow is waiting, so an ordinary tick on another host would
    rebuild the checkout at base and pay for a second developer over work the
    first one already finished. It is asked before the spawn because that is
    the only place it can be.
    """
    if _terminals._finalize_if_issue_closed(gh, spec, issue, state):
        return True
    if _read_only_relabel._handle_stale_read_only_park(gh, spec, issue, state):
        return True
    if _disposition._recovers_a_late_park(gh, spec, issue, state):
        return True
    if _disposition._holds_unreconciled_candidate(gh, spec, issue, state):
        return True
    return _continue_command._handle_parked_continue_command(gh, spec, issue, state)


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
