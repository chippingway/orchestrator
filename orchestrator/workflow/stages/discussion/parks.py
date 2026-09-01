# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Every way this stage hands the issue back, and the funnel they share.

A discussion tick has exactly one kind of ending -- awaiting a human -- so what
differs between these is only what the comment says and which reason it is
recorded under. They sit together because that reason is load-bearing beyond
the message: the handler reads its `discussion_` prefix back on the next tick
to decide whose turn it is, so a park that skipped the funnel would read as a
park some other stage wrote and earn a second round over the top of the first.

`_park_discussion` is that funnel, and it exists because the shared park helper
clears `park_reason`: the stage-specific reason has to be restored after it and
persisted, which is also where the round's staged records finally land.

Only the published plan touches the round anchor, and it moves it forward onto
the commit it just put on a PR -- the one case where the branch's new tip IS
what this stage vouches for. Every refusal leaves the anchor exactly where the
round opened it, because a commit is precisely when that number has to survive:
it is the only recorded point that separates what the agent wrote from what the
branch already carried, so it is both the reset target these parks quote and
what the implementing relabel guard measures the branch against once the
operator has reset. Clearing it on the way out would leave a PR-backed issue
with commits ahead of base and nothing left to certify them, refused forever
with no non-destructive way back.

The two dirty parks are distinct on purpose even though both quote the same
bounded path list. One is the agent leaving work loose where the only thing it
may write is a committed plan; the other is a checkout that arrived already
holding work, which no agent of this tick touched -- and the operator's next
move differs, so the reason has to say which happened rather than leaving them
to guess from the tree. A checkout `git status` could not report on at all is a
third answer to the same question and carries its own reason for the same
reason: an empty path list is what a clean tree gives, so an operator reading
the dirty one would go looking for changes that were never named.

The two refusals of a committed artifact are distinct for the same reason and
share one reason code. Both mean the branch is not the plan file alone, and
both quote the same reading of it, but one is a round reporting on itself and
the other is a commit found by a tick that opened no round at all -- so the
operator is told which, and told why nothing ran this time.
"""
from __future__ import annotations

import logging

from orchestrator import config
from orchestrator.agents import AgentResult
from orchestrator.git.verification import probes as _verification_probes
from orchestrator.workflow.engine import guards as _guards, messages as _messages
from orchestrator.workflow.stages.discussion import models as _models, state as _state
from orchestrator.workflow.state import WorkflowLabel

log = logging.getLogger("orchestrator.workflow")

_PATHS_SHOWN = 10

# What a refusal calls a tip whose read failed, so the message still says
# which of the two SHAs it could not name.
_UNREADABLE_TIP = "an unreadable tip"


def _park_discussion(
    run: _models._DiscussionRun, message: str, *, reason: str,
) -> None:
    """Park the issue awaiting human under the discussion-stage reason.

    The shared park helper clears `park_reason`, so this funnel restores the
    stage-specific one and persists the completed state mutation -- the single
    durable write every route in this stage reaches the issue through.

    It also stamps `last_action_comment_id` at the newest comment on the
    thread, which this funnel restores for the same kind of reason. That stamp
    is right for a stage whose park ENDS the exchange, but a discussion's park
    is an invitation to answer it, and minutes of agent run separate the thread
    the round read from the thread as it stands now. Anything posted in that
    window -- a human's second thought, an outsider's comment the allowlist may
    later admit -- would be recorded as read by a round that never saw it, and
    nothing here reads a comment twice. What the round did read it has already
    staged, so restoring the value this call was entered with is exactly the
    ceiling to keep. The comment just posted needs no watermark to be skipped:
    `_new_trusted_replies` knows the stage's own messages by id and marker.
    """
    consumed_through = run.state.get(_state._LAST_ACTION_COMMENT_ID)
    _guards._park_awaiting_human(
        run.gh, run.issue, run.state, message, reason=reason,
    )
    run.state.set(_state._PARK_REASON, reason)
    run.state.set(_state._LAST_ACTION_COMMENT_ID, consumed_through)
    # A park IS the report a round owes, so it is what ends the window the
    # open flag marks. Cleared here rather than at each ending, because every
    # one of them lands on this funnel and a flag left standing would have the
    # next tick attribute somebody else's commit to a round already answered.
    run.state.set(_state._ROUND_OPEN, None)
    run.gh.write_pinned_state(run.issue, run.state)


def _paths_markdown(paths: tuple[str, ...]) -> str:
    """Render a bounded path list, naming how many it did not show."""
    shown_paths = paths[:_PATHS_SHOWN]
    display_lines = [f"- `{file_path}`" for file_path in shown_paths]
    hidden_count = len(paths) - len(shown_paths)
    if hidden_count:
        display_lines.append(f"- ... ({hidden_count} more)")
    return "\n".join(display_lines)


def _park_dirty_discussion(
    run: _models._DiscussionRun, dirty_files: tuple[str, ...],
) -> None:
    _park_discussion(
        run,
        f"{config.HITL_MENTIONS} discussion agent left "
        f"{len(dirty_files)} uncommitted change(s), but the only thing this "
        "stage publishes is the agreed plan, committed on its own. Reset the "
        "worktree before resuming."
        f"\n\n{_paths_markdown(dirty_files)}",
        reason=_state._DISCUSSION_DIRTY,
    )


def _park_stranded_worktree(
    run: _models._DiscussionRun, stranded: _verification_probes._WorktreeStatus,
) -> None:
    """Park on a checkout no round may open over, instead of recreating it.

    Preparing the checkout would force-remove a dirty tree that carries no
    commits, so this park runs INSTEAD of the round: the changes an earlier
    round died holding are the only record of what it was doing, and an
    operator has to see them before anything overwrites them.

    A checkout that could not be read lands here for the sharper version of
    the same reason, under its own reason code -- either probe failing is that
    answer, since a `git status` that could not run and a `HEAD` that would not
    resolve leave the same nothing behind. The destructive step behind this
    question does not wait to be told twice, so recreating on a probe that
    never answered would delete the very tree an operator needs to look at to
    find out why it failed. There is no path list to quote and no tip to reset
    to, which is exactly what the message has to say instead.
    """
    if not stranded.readable:
        _park_discussion(
            run,
            f"{config.HITL_MENTIONS} the per-issue worktree could not be read "
            "(`git status` or `HEAD` failed), so nothing here can show it is "
            "empty or say where it is -- and opening a discussion round would "
            "recreate the checkout over whatever is in it. No agent was "
            "spawned and the tree was left exactly as it is. Inspect it (a "
            "corrupt index or a half-removed directory reads this way) and "
            "repair or remove it before this issue is picked up again.",
            reason=_state._DISCUSSION_UNREADABLE,
        )
        return
    _park_discussion(
        run,
        f"{config.HITL_MENTIONS} the per-issue worktree already holds "
        f"{len(stranded.paths)} uncommitted change(s) from an earlier run that "
        "did not finish. Opening a discussion round would recreate the "
        "checkout and destroy them, so no agent was spawned. Inspect the "
        "worktree and reset it before this issue is picked up again."
        f"\n\n{_paths_markdown(stranded.paths)}",
        reason=_state._DISCUSSION_STRANDED,
    )


def _reset_target(run: _models._DiscussionRun) -> str:
    """Name the SHA a commit park has to be reset back to, not just "reset".

    The branch an issue arrives on can already be ahead of base -- a PR-backed
    issue relabeled here carries its dev's commits -- so "reset the worktree"
    read as "reset to base" would throw away the PR. The anchor is the exact
    tip the round opened on, which is the one target that drops what the agent
    wrote and keeps everything under it, and it is also what the implementing
    relabel guard checks the branch against afterwards.
    """
    anchor = run.state.get(_state._ROUND_SHA)
    if not anchor:
        return "Reset the worktree before resuming."
    return (
        f"Reset the worktree to `{anchor}` -- the tip this round opened on, so "
        "anything the branch already carried survives -- before resuming: "
        f"`git -C <worktree> reset --hard {anchor} && "
        "git -C <worktree> clean -fd`."
    )


def _park_unreadable_round(run: _models._DiscussionRun) -> None:
    """Report a finished round whose checkout will not say what it did.

    `HEAD` is one end of every comparison this stage classifies a round by, and
    a read that failed makes all of them unanswerable at once: whether the
    agent committed, whether what it committed is the plan, and whether the
    tree beside it is clean. The one thing that must not follow is a
    publication, because empty compares unequal to the SHA the round opened on
    -- so the "yes, it committed" answer is exactly the one a failed read
    produces, and the commit the branch already carried would go out under this
    round's session.

    Nothing is reset and nothing is recreated: what the round did is still in
    the tree, and the tree is what an operator has to look at to find out why
    git could not be asked about it.
    """
    _park_discussion(
        run,
        f"{config.HITL_MENTIONS} the discussion round finished, but `HEAD` "
        "could not be read in the per-issue worktree afterwards -- so nothing "
        "here can say whether it committed, and nothing was published or "
        "recorded on the strength of a reading that did not happen. The "
        "worktree was left exactly as the round left it. Inspect it (a corrupt "
        "index or a half-removed directory reads this way) and repair or "
        "remove it before this issue is picked up again.",
        reason=_state._DISCUSSION_UNREADABLE,
    )


def _park_timed_out_discussion(run: _models._DiscussionRun) -> None:
    _park_discussion(
        run,
        f"{config.HITL_MENTIONS} discussion agent timed out "
        f"after {config.AGENT_TIMEOUT}s; manual intervention "
        "needed. The per-issue worktree is left intact for inspection.",
        reason=_state._DISCUSSION_TIMEOUT,
    )


def _committed_reading(artifact: _models._PlanArtifact) -> str:
    """Say what the commits changed, and whether the plan survived them.

    A round with no recorded base is reported as having no reading at all
    rather than as an empty diff: the paths below were measured from
    somewhere, and an operator told "changes nothing" about a comparison that
    never happened would reset a branch on the strength of it.
    """
    if not artifact.base_sha:
        return (
            "The commit this round was measured from was never recorded, so "
            "what this branch changes against the base branch could not be "
            "established."
        )
    if not artifact.changed_paths:
        return (
            "The commits on this branch change nothing against the base "
            "branch."
        )
    listing = (
        "Committed against the base branch:\n"
        f"{_paths_markdown(artifact.changed_paths)}"
    )
    if artifact.plan_in_head:
        return listing
    # A deletion changes exactly the path an addition would, so the diff on
    # its own reads as the artifact being asked for. Saying which happened is
    # the difference between "your plan needs trimming" and "there is no plan".
    return f"{listing}\n\n`{artifact.plan_path}` is not in the branch's HEAD."


def _artifact_reading(artifact: _models._PlanArtifact) -> str:
    """Quote what the branch actually carries, in the halves it is judged by.

    Every half is named even when only one of them is why the publication was
    refused: an operator deciding what to reset needs to see the committed
    diff and the loose edits together, and a plan that is absent -- never
    written, or deleted by the commit that named its path -- is a fact the
    listing has to state rather than imply by omission.

    An unreadable worktree is reported as exactly that. It is not a clean tree
    and not a dirty one; what it means is that nothing here could tell, which
    an operator has to know before they go looking for edits that may not be
    there.

    A commit made off the branch is reported for the opposite reason: every
    reading above it comes back exactly as it would for a plan written the way
    it was asked for, so without saying which ref HEAD is on the operator
    reads a refusal whose every stated fact looks right.
    """
    committed = _committed_reading(artifact)
    if not artifact.head_attached:
        committed = (
            f"{committed}\n\nHEAD is not `{artifact.branch}`: the commit was "
            "made on a detached HEAD or on another ref, so that branch is not "
            "on it -- and nothing here moves a ref an agent left behind."
        )
    if not artifact.tree_readable:
        return (
            f"{committed}\n\nThe worktree's state could not be read "
            "(`git status` failed), so nothing was assumed about it."
        )
    if not artifact.dirty_files:
        return committed
    return (
        f"{committed}\n\nUncommitted in the worktree "
        f"({len(artifact.dirty_files)}):\n"
        f"{_paths_markdown(artifact.dirty_files)}"
    )


def _unpublishable_plan_message(
    run: _models._DiscussionRun, artifact: _models._PlanArtifact, found: str,
) -> str:
    """The refusal every unpublishable commit gets, framed by where it came from."""
    return (
        f"{config.HITL_MENTIONS} {found}, but the only thing this stage "
        f"publishes is `{artifact.plan_path}` committed on its own, with a "
        "clean worktree, once you have confirmed the design on this thread. "
        "Nothing was pushed and no pull request was opened."
        f"\n\n{_artifact_reading(artifact)}\n\n{_reset_target(run)}"
    )


def _park_unpublishable_plan(
    run: _models._DiscussionRun, artifact: _models._PlanArtifact,
) -> None:
    _park_discussion(
        run,
        _unpublishable_plan_message(
            run, artifact, "the discussion round committed in the worktree",
        ),
        reason=_state._DISCUSSION_PLAN_INVALID,
    )


def _park_foreign_commit(run: _models._DiscussionRun) -> None:
    """Report a commit on the branch that no round of this stage made.

    The counterpart to the recovered-commit park beside it, and the difference
    is who wrote what is there. That one names a plan a round of this stage
    left unreported; this one is for a tip that moved while no round was in
    flight -- another stage's agent under its own park, or a hand-made commit
    on the branch -- so nothing here can say what it is, and it is certainly
    not a design this conversation agreed to.

    It runs INSTEAD of a round for the same reason every commit park does: the
    checkout would be recreated over it. And it says so on the thread, because
    an issue whose stage has quietly stopped opening rounds looks exactly like
    one waiting for an answer.
    """
    _park_discussion(
        run,
        f"{config.HITL_MENTIONS} the per-issue worktree carries commits made "
        "since the last discussion round opened, and no round of this stage "
        "was running when they appeared -- so they are not a design agreed on "
        "this thread, and nothing was published. No agent was spawned and "
        f"nothing was overwritten. {_reset_target(run)}",
        reason=_state._DISCUSSION_COMMITS,
    )


def _park_recovered_commit(
    run: _models._DiscussionRun, artifact: _models._PlanArtifact,
) -> None:
    """Park on a commit a round left without ever reaching a disposition.

    The round that made it was withheld or cut short before it could say so,
    so this park is the first time the commit is named. It runs INSTEAD of a
    new round, which is what stops the next one from opening on the commit and
    reporting it as work the branch arrived carrying.
    """
    _park_discussion(
        run,
        _unpublishable_plan_message(
            run,
            artifact,
            "a discussion round that did not finish (paused mid-run, or "
            "interrupted) left a commit in the per-issue worktree and no "
            "further round was opened",
        ),
        reason=_state._DISCUSSION_PLAN_INVALID,
    )


def _park_published_plan(
    run: _models._DiscussionRun, artifact: _models._PlanArtifact,
    pr_number: int,
) -> None:
    """Hand back an issue whose agreed design is now on a PR to review.

    Still a park, and still under this stage's own prefix: the label does not
    move, and what happens next is a human's -- reviewing the plan, then
    relabeling the issue to have it built. The comment says both, because an
    issue that keeps its `discussion` label while its stage has stopped
    opening rounds is otherwise indistinguishable from one waiting on an
    answer.
    """
    _park_discussion(
        run,
        f"{config.HITL_MENTIONS} the design confirmed on this thread is "
        f"written up in `{artifact.plan_path}` and opened as PR "
        f"#{pr_number}. That branch changes nothing else -- it was checked "
        "against the base branch before anything was pushed. Review the plan "
        f"there, and relabel this issue to `{WorkflowLabel.IMPLEMENTING}` "
        "when it should be built; no further discussion round is opened "
        "while the plan PR stands.",
        reason=_state._DISCUSSION_PLAN_PUBLISHED,
    )


def _park_unattributed_plan(
    run: _models._DiscussionRun, artifact: _models._PlanArtifact,
) -> None:
    """Report a valid plan with no conversation to publish it under.

    The artifact passed every check the branch can answer; what it has no
    answer for is which discussion produced it, and that is what the PR body
    exists to say. It happens when a backend hands back no session id, and
    when a round that opened a new conversation is cut short before it can
    record the one it opened.

    The remedy is a re-run, so the message asks for the reset that makes one
    possible: the commit has to come off the branch before a round may open on
    it, and the round that follows writes the same plan under a session a
    reviewer can follow back.
    """
    _park_discussion(
        run,
        f"{config.HITL_MENTIONS} the agreed plan is committed in "
        f"`{artifact.plan_path}`, but no session id was recorded for the "
        "round that wrote it -- the backend handed none back, or the round "
        "was cut short before it could. A published plan has to name the "
        "conversation it came out of, so nothing was pushed and the commit is "
        f"untouched. {_reset_target(run)} The next reply then re-runs the "
        "discussion, which writes the plan again under a session that can be "
        "followed back; relabeling to "
        f"`{WorkflowLabel.IMPLEMENTING}` builds from the file as it stands "
        "instead.",
        reason=_state._DISCUSSION_PLAN_UNATTRIBUTED,
    )


def _park_stale_publication(
    run: _models._DiscussionRun,
    artifact: _models._PlanArtifact,
    in_flight: str,
    published: bool,
) -> None:
    """Report a publication whose commit the branch has moved off.

    Named rather than described, both SHAs: the one that was checked and
    pushed for, and the one the branch is on instead. Restoring the first is
    what lets the publication finish on its own next tick, which is why it is
    the remedy offered before the one that ends the conversation's artifact.

    What the remote holds decides the rest of it, because it decides whether
    the other remedy is even available. With nothing of ours on that branch, a
    local reset ends the plan and the message can offer it. With the commit
    still out there -- pushed from a checkout whose ref never moved, or left by
    a tick that died after opening the pull request -- the plan is published
    whatever this tree says, so telling an operator to reset would tell them to
    lose track of a PR that stays open either way. That one is dropped where it
    really lives, and this stage will not spend the record until it is.
    """
    branch_tip = artifact.head_sha or _UNREADABLE_TIP
    _park_discussion(
        run,
        f"{config.HITL_MENTIONS} a publication of `{artifact.plan_path}` was "
        f"in flight on `{in_flight}`, but the branch is at "
        f"`{branch_tip}` now. {_stale_publication_standing(published)} Restore "
        f"`{in_flight}` on `{artifact.branch}` and it is published on the "
        f"next tick; {_stale_publication_remedy(run, published)}"
        f"\n\n{_artifact_reading(artifact)}",
        reason=_state._DISCUSSION_STALE_PUBLISH,
    )


def _stale_publication_standing(published: bool) -> str:
    """What the remote says is out there, which is not what the tree says."""
    if published:
        return (
            "The commit is on the remote branch, so the plan is published "
            "whatever this checkout is on -- nothing here recorded it, and no "
            "round is opening over the top of it."
        )
    return (
        "Nothing was pushed: whatever moved it is not the commit this stage "
        "checked, and it is not published on that commit's behalf."
    )


def _stale_publication_remedy(
    run: _models._DiscussionRun, published: bool,
) -> str:
    """The other way out, which a published commit does not have locally."""
    if published:
        return (
            "to drop the plan instead, close its pull request and delete the "
            "remote branch -- a reset here cannot, and this stage keeps the "
            "record until the commit is gone from the remote."
        )
    return f"to drop it and keep discussing: {_reset_target(run)}"


def _park_diverged_plan_branch(
    run: _models._DiscussionRun,
    artifact: _models._PlanArtifact,
    remote_tip: str | None,
) -> None:
    """Report a remote branch this publication is not allowed to overwrite.

    Shares the failed-push reason because the operator's way out is the same
    one: the plan is still committed, nothing was published, and a reply
    retries the publication once the remote and the branch agree again. What
    differs is why, so the message names the tip that is there -- or says the
    remote could not be read at all, which is not the same as a remote that
    moved and must not be reported as one.

    Written every time rather than once, unlike the repair parks: each tick
    that reaches here has taken a fresh reading of a remote somebody else is
    moving, and the answer an operator needs is the current one.
    """
    if remote_tip is None:
        found = (
            "the remote could not be asked what "
            f"`{artifact.branch}` is at (see the orchestrator logs)"
        )
    else:
        found = (
            f"`{artifact.branch}` is at `{remote_tip}` on the remote, and the "
            "commit this plan is on does not descend from it -- somebody has "
            "written on that branch, or the branch was reset out from under "
            "what it carried"
        )
    _park_discussion(
        run,
        f"{config.HITL_MENTIONS} the agreed plan is committed in "
        f"`{artifact.plan_path}`, but {found}. Nothing was pushed and nothing "
        f"was overwritten: `{artifact.head_sha}` does not contain what is "
        "there, so publishing it would have discarded it. Reconcile the "
        "branch with the remote and reply here to retry the publication, or, "
        f"to drop the plan and keep discussing: {_reset_target(run)}",
        reason=_state._DISCUSSION_PUSH_FAILED,
    )


def _park_failed_plan_push(
    run: _models._DiscussionRun, artifact: _models._PlanArtifact,
) -> None:
    """Report a valid plan that could not be pushed, and what to do with it.

    The commit is left exactly where it is: it is the agreed design, and the
    remedies are ordered so the destructive one is last. A reply on this park
    retries the publication -- the branch still carries the same publishable
    artifact -- so an operator who fixes the token, the network, or the remote
    can say so on the thread instead of resetting the plan away.
    """
    _park_discussion(
        run,
        f"{config.HITL_MENTIONS} the agreed plan is committed in "
        f"`{artifact.plan_path}`, but pushing `{artifact.branch}` failed; see "
        "the orchestrator logs. Nothing was published and the commit is still "
        "in the per-issue worktree. Fix the push and reply here to retry it, "
        f"or, to drop the plan and keep discussing: {_reset_target(run)}",
        reason=_state._DISCUSSION_PUSH_FAILED,
    )


def _park_blocked_resume(
    run: _models._DiscussionRun, stranded: _verification_probes._WorktreeStatus,
) -> None:
    """Report a reply that cannot be answered until the checkout is restored.

    A park this stage wrote earlier said "reset the worktree"; this one is for
    the case where none did -- the last round ended cleanly, and the tree was
    dirtied or committed to afterwards. Without it a human who answers the
    frontier gets silence, since the guard that refuses to open a round on such
    a tree has nothing on the thread to point them at.

    The reason it lands under is one of the three the operator's next move
    differs between, chosen by which probe found the violation, so the pinned
    record still says whether there are commits to reset off, edits to clean,
    or a checkout that could not be read at all. That last one comes with no
    reset target on purpose: the read that would have named one is the thing
    that failed, and quoting the anchor would tell an operator to run a command
    over a tree nobody has established anything about. All of them are why this
    park is written once: the reason it leaves IS a repair request, so the tick
    after it holds quietly rather than repeating itself. The reply is left
    unconsumed either way, so answering it again is not something the human has
    to think to do.

    A commit that IS the agreed plan never reaches here: the reply publishes it
    instead, which is what keeps a tick that died between opening the plan PR
    and recording it from telling an operator to reset away the commit that PR
    is open against.
    """
    if not stranded.readable:
        _park_discussion(
            run,
            f"{config.HITL_MENTIONS} your reply is noted, but the per-issue "
            "worktree could not be read (`git status` or `HEAD` failed), so "
            "nothing here can show it is still the checkout this discussion "
            "was left on. No round was opened on it and nothing was "
            "overwritten. Inspect it (a corrupt index or a half-removed "
            "directory reads this way) and repair or remove it; your reply "
            "stays unread until then, and the discussion continues from it on "
            "its own once the tree reads again.",
            reason=_state._DISCUSSION_UNREADABLE,
        )
        return
    if stranded.paths:
        found = f"it is holding {len(stranded.paths)} uncommitted change(s)"
        reason = _state._DISCUSSION_DIRTY
        listing = f"\n\n{_paths_markdown(stranded.paths)}"
    else:
        found = "it carries commits made since that round opened"
        reason = _state._DISCUSSION_COMMITS
        listing = ""
    _park_discussion(
        run,
        f"{config.HITL_MENTIONS} your reply is noted, but the per-issue "
        "worktree is no longer the checkout this discussion was left on "
        f"({found}), so no round was opened on it and nothing was overwritten."
        f" {_reset_target(run)} Your reply stays unread until then, and the "
        f"discussion continues from it on its own once the tree is back."
        f"{listing}",
        reason=reason,
    )


def _park_silent_discussion(
    run: _models._DiscussionRun, discussion_result: AgentResult,
) -> None:
    # A round of this stage is either a first spawn or a resume of the pinned
    # session, and the stderr tail is what tells an operator which one went
    # quiet -- so the message names neither rather than sending them looking
    # for a session that may never have been asked for.
    diagnostics = _messages._format_stderr_diagnostics(
        discussion_result, "Discussion agent",
    )
    _park_discussion(
        run,
        f"{config.HITL_MENTIONS} discussion agent produced no output (the "
        "backend exited without writing a response); manual intervention "
        f"needed.{diagnostics}",
        reason=_state._DISCUSSION_SILENT,
    )
    log.warning(
        "issue=#%s discussion agent produced no output; "
        "exit_code=%d timed_out=%s stderr_tail=%r",
        run.issue.number,
        discussion_result.exit_code,
        discussion_result.timed_out,
        _messages._stderr_log_tail(discussion_result),
    )


def _park_discussion_response(
    run: _models._DiscussionRun, response: str,
) -> None:
    _park_discussion(
        run,
        f"{config.HITL_MENTIONS} discussion agent opened the design "
        f"discussion:\n\n{_messages._as_blockquote(response)}",
        reason=_state._DISCUSSION_RESPONSE,
    )
