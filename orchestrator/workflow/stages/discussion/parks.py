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

No park here touches the round anchor, including the two that found a commit.
The anchor is the tip the round opened on, and a commit is precisely when that
number has to survive: it is the only recorded point that separates what the
agent wrote from what the branch already carried, so it is both the reset
target these parks quote and what the implementing relabel guard measures the
branch against once the operator has reset. Clearing it on the way out would
leave a PR-backed issue with commits ahead of base and nothing left to certify
them, refused forever with no non-destructive way back.

The two dirty parks are distinct on purpose even though both quote the same
bounded path list. One is the agent writing when it was told to discuss; the
other is a checkout that arrived already holding work, which no agent of this
tick touched -- and the operator's next move differs, so the reason has to say
which happened rather than leaving them to guess from the tree.
"""
from __future__ import annotations

import logging

from orchestrator import config
from orchestrator.agents import AgentResult
from orchestrator.workflow.engine import guards as _guards
from orchestrator.workflow.engine import messages as _messages
from orchestrator.workflow.stages.discussion import models as _models
from orchestrator.workflow.stages.discussion import state as _state

log = logging.getLogger("orchestrator.workflow")

_DIRTY_FILES_SHOWN = 10


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
    run.gh.write_pinned_state(run.issue, run.state)


def _dirty_files_markdown(dirty_files: tuple[str, ...]) -> str:
    """Render a bounded path list, naming how many it did not show."""
    shown_files = dirty_files[:_DIRTY_FILES_SHOWN]
    display_lines = [f"- `{file_path}`" for file_path in shown_files]
    hidden_count = len(dirty_files) - len(shown_files)
    if hidden_count:
        display_lines.append(f"- ... ({hidden_count} more)")
    return "\n".join(display_lines)


def _park_dirty_discussion(
    run: _models._DiscussionRun, dirty_files: tuple[str, ...],
) -> None:
    _park_discussion(
        run,
        f"{config.HITL_MENTIONS} discussion agent left "
        f"{len(dirty_files)} uncommitted change(s), but this stage only "
        "discusses the design and waits for your confirmation. Reset the "
        "worktree before resuming."
        f"\n\n{_dirty_files_markdown(dirty_files)}",
        reason=_state._DISCUSSION_DIRTY,
    )


def _park_stranded_worktree(
    run: _models._DiscussionRun, dirty_files: tuple[str, ...],
) -> None:
    """Park on uncommitted work found before the round could open.

    Preparing the checkout would force-remove a dirty tree that carries no
    commits, so this park runs INSTEAD of the round: the changes an earlier
    round died holding are the only record of what it was doing, and an
    operator has to see them before anything overwrites them.
    """
    _park_discussion(
        run,
        f"{config.HITL_MENTIONS} the per-issue worktree already holds "
        f"{len(dirty_files)} uncommitted change(s) from an earlier run that "
        "did not finish. Opening a discussion round would recreate the "
        "checkout and destroy them, so no agent was spawned. Inspect the "
        "worktree and reset it before this issue is picked up again."
        f"\n\n{_dirty_files_markdown(dirty_files)}",
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


def _park_timed_out_discussion(run: _models._DiscussionRun) -> None:
    _park_discussion(
        run,
        f"{config.HITL_MENTIONS} discussion agent timed out "
        f"after {config.AGENT_TIMEOUT}s; manual intervention "
        "needed. The per-issue worktree is left intact for inspection.",
        reason=_state._DISCUSSION_TIMEOUT,
    )


def _park_committed_discussion(run: _models._DiscussionRun) -> None:
    _park_discussion(
        run,
        f"{config.HITL_MENTIONS} discussion agent committed in the "
        "worktree, but this stage only discusses the design and waits "
        f"for your confirmation. {_reset_target(run)}",
        reason=_state._DISCUSSION_COMMITS,
    )


def _park_recovered_commit(run: _models._DiscussionRun) -> None:
    """Park on a commit a round left without ever reaching a disposition.

    The round that made it was withheld or cut short before it could say so,
    so this park is the first time the commit is named. It runs INSTEAD of a
    new round, which is what stops the next one from opening on the commit and
    reporting it as work the branch arrived carrying.
    """
    _park_discussion(
        run,
        f"{config.HITL_MENTIONS} a discussion round that did not finish "
        "(paused mid-run, or interrupted) left a commit in the per-issue "
        "worktree. This stage only discusses the design and waits for your "
        f"confirmation, so no further round was opened. {_reset_target(run)}",
        reason=_state._DISCUSSION_COMMITS,
    )


def _park_blocked_resume(
    run: _models._DiscussionRun, dirty_files: tuple[str, ...],
) -> None:
    """Report a reply that cannot be answered until the checkout is restored.

    A park this stage wrote earlier said "reset the worktree"; this one is for
    the case where none did -- the last round ended cleanly, and the tree was
    dirtied or committed to afterwards. Without it a human who answers the
    frontier gets silence, since the guard that refuses to open a round on such
    a tree has nothing on the thread to point them at.

    The reason it lands under is one of the two the operator's next move
    differs between, chosen by which probe found the violation, so the pinned
    record still says whether there are commits to reset off or edits to clean.
    Both are why this park is written once: the reason it leaves IS a repair
    request, so the tick after it holds quietly rather than repeating itself.
    The reply is left unconsumed either way, so answering it again is not
    something the human has to think to do.
    """
    if dirty_files:
        found = f"it is holding {len(dirty_files)} uncommitted change(s)"
        reason = _state._DISCUSSION_DIRTY
        listing = f"\n\n{_dirty_files_markdown(dirty_files)}"
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
