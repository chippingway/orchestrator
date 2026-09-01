# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The three things a finished decomposer reply can turn into.

A reply either carries a usable manifest or it does not, and both halves of
that split are dispositions the issue leaves this tick on. `single` posts the
sizing rationale and the context the decomposer already gathered, then hands
the issue to `ready` -- the comment rather than a body edit, because rewriting
the body would move the user-content hash and re-decompose the issue on the
next tick. `split` creates the children and leaves the parent waiting on them.

Everything else parks awaiting a human, and the park distinguishes two cases
the parse cannot: a malformed manifest is the agent getting the contract wrong,
while no manifest at all is the agent asking a question -- or saying nothing,
which is a backend failure wearing a question's clothes. Only the silent case
carries stderr diagnostics, because an operator answering a real question does
not need to read subprocess noise to do it.
"""
from __future__ import annotations

import logging

from github.Issue import Issue

from orchestrator import config
from orchestrator.agents import AgentResult
from orchestrator.github.client import GitHubClient
from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.engine import comments as _comments
from orchestrator.workflow.engine import guards as _guards
from orchestrator.workflow.engine import messages as _messages
from orchestrator.workflow.engine import prompts as _prompts
from orchestrator.workflow.engine import usage as _usage
from orchestrator.workflow.stages.decomposition import manifest as _manifest
from orchestrator.workflow.stages.decomposition import split as _split
from orchestrator.workflow.stages.decomposition import state as _state
from orchestrator.workflow.state import WorkflowLabel

log = logging.getLogger("orchestrator.workflow")


def _park_unparsed_manifest(
    gh: GitHubClient, issue: Issue, state: PinnedState,
    decomposer_result: AgentResult, error: str | None,
) -> None:
    """Park awaiting human when the decomposer produced no usable manifest.

    Either a malformed manifest (`error` set) OR no manifest at all
    (question / silence, `error` None). Both park; the resume on the next
    comment runs through the awaiting_human branch of `_handle_decomposing`.
    """
    last_msg = decomposer_result.last_message or ""
    if error is None:
        stripped = last_msg.strip()
        raw = stripped or "(decomposer produced no final message)"
        quoted = _messages._as_blockquote(raw)
        # Only attach stderr diagnostics on the silent path -- a
        # real content question from the decomposer doesn't need
        # the operator wading through subprocess noise.
        diag = (
            "" if stripped
            else _messages._format_stderr_diagnostics(
                decomposer_result, "Decomposer",
            )
        )
        _guards._park_awaiting_human(
            gh, issue, state,
            f"{config.HITL_MENTIONS} decomposer needs your input to "
            f"proceed:\n\n{quoted}{diag}",
            reason="decomposer_question" if stripped else "decomposer_silent",
        )
        if not stripped:
            log.warning(
                "issue=#%s decomposer produced no final message; "
                "exit_code=%d timed_out=%s stderr_tail=%r",
                issue.number,
                decomposer_result.exit_code,
                decomposer_result.timed_out,
                _messages._stderr_log_tail(decomposer_result),
            )
    else:
        quoted = _messages._as_blockquote(last_msg.strip())
        _guards._park_awaiting_human(
            gh, issue, state,
            f"{config.HITL_MENTIONS} decomposer manifest invalid "
            f"({error}); manual adjudication needed.\n\n"
            f"_Last decomposer message:_\n\n{quoted}",
            reason="decomposer_invalid_manifest",
        )
    gh.write_pinned_state(issue, state)


def _finalize_single_decision(
    gh: GitHubClient, issue: Issue, state: PinnedState, parsed: dict,
) -> None:
    """Finalize a `single` manifest: post the rationale and flip to `ready`.

    Surface the decomposer's rationale AND the context it already gathered
    (affected files, implementation notes) so the develop agent that picks
    this up in `implementing` starts from that groundwork instead of
    re-deriving it. The builder tolerates missing / malformed optional
    fields -- the single decision is already valid, so no cosmetic field
    should park it.
    """
    _comments._post_issue_comment(
        gh, issue, state,
        _prompts._build_single_decision_comment(parsed),
    )
    state.set("decomposed_at", _usage._now_iso())
    gh.set_workflow_label(issue, WorkflowLabel.READY)
    gh.write_pinned_state(issue, state)


def _dispatch_decomposer_manifest(
    gh: GitHubClient,
    issue: Issue,
    state: PinnedState,
    decomposer_result: AgentResult,
) -> None:
    """Parse the decomposer's final message and route on the outcome.

    Parks awaiting human on an invalid / silent / question manifest,
    finalizes a `single` decision to `ready`, or creates the `split`
    children and finalizes the parent to `blocked` / `umbrella`.
    """
    last_msg = decomposer_result.last_message or ""
    parsed, error = _manifest._parse_manifest(last_msg)

    if parsed is None:
        _park_unparsed_manifest(gh, issue, state, decomposer_result, error)
        return

    if parsed["decision"] == "single":
        _finalize_single_decision(gh, issue, state, parsed)
        return

    # decision == "split".
    split_plan = _split._create_child_issues(
        gh,
        issue,
        state,
        parsed[_state._CHILDREN],
        bool(parsed.get(_state._UMBRELLA)),
    )
    if split_plan is None:
        return
    _split._finalize_split(gh, issue, state, split_plan)
