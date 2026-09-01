# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The late run one issue is locked to: read back, recorded, and spawned.

The same lock every other role carries, for the same reason: a resume has to
land on the CLI that issued the session id, so the whole configured spec is
pinned at the first spawn -- before that spawn can fail -- and read back on
every later tick whatever `DECOMPOSE_AGENT` currently says. `DECOMPOSE_AGENT`
is the fallback for the first-ever late run on an issue and nothing after it,
which is what makes a mid-flight config flip safe while a generation is under
adjudication.

The pin is a separate pair from the initial decomposer's. An issue can carry
both -- it was decomposed once and its implementation later measured oversized
-- and they are different conversations against different bodies of context,
so `late_agent` / `late_session_id` never share the `decomposer_agent` /
`decomposer_session_id` keys the initial mode locked.

Beside them this owner records what the late-agent boundary calls its durable
facts: the role the run was recorded under, the cycle and generation it
belongs to, the exact source commit it was spawned against, and -- once it
finishes -- the result it completed with. Those three identities are what make
a recorded result believable: an answer is this candidate's only when it names
this cycle, this generation, AND this commit. The cycle is required because
the counter beside it is not unique without one -- a restart mints a fresh
cycle and puts the generation back where it started -- and these run fields
survive a late-generation clear, which is exactly the window a repeated
counter would be read in. A fresh spawn drops the previous result first, so a
tick that crashes mid-run cannot read the last attempt's verdict back as this
one's.

What is recorded of the result is the whole of what the verdict decided: a
`single` alone, a `question` with its category and the sentence it asked, and
a `split` with the ordered child manifest that IS its decision. That is what
lets a crashed tick recover an answer rather than pay for a second run that
may not decide the same way. The one part deliberately not kept is the agent's
rationale, which is prose and belongs on the issue thread rather than in the
state every stage shares.

Both ends of that are bounded rather than trusted. What a recorded outcome is
measured against is the whole comment the write would produce -- the preserved
held-PR body and every other stage's keys included, since a result small on
its own can still be the one that pushes the comment past what GitHub accepts
-- and an outcome past that budget is refused whole, because shortening it
would record a question nobody asked or children nobody proposed. On the way
back, a recorded manifest is read through the same split rules the reply was
held to, so a shape this binary would not have written is read as no manifest
at all rather than as half a split to create.

One late run in three resumes. A human answering the categorized question the
adjudicator asked is answering an agent that ASKED it, so that run continues
the pinned session rather than opening a conversation which would have to be
told what it had asked before it could be told the answer -- which is what the
pin was written for. Every other late run is fresh: a first adjudication has
no conversation to continue, and a candidate the developer revised is a
different question, so a session opened against the commit it replaced would
hand the agent a transcript about work nobody is adjudicating. Both halves of
that are proved rather than assumed -- the caller says it is carrying an
answer, and the record says its session really ran against THIS cycle,
generation, and commit.
"""
from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path

from orchestrator import config
from orchestrator.agents import AgentResult
from orchestrator.github import pinned_state as _pinned_state
from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.engine import comments as _comments, usage as _usage
from orchestrator.workflow.late_split import formats as _formats, payloads as _payloads
from orchestrator.workflow.late_split.events import LateVerdictCategory
from orchestrator.workflow.late_split.models import (
    LateGeneration,
    LateVerdict,
)
from orchestrator.workflow.stages.decomposition import (
    late_prompt as _prompt,
    validation as _split_validation,
)
from orchestrator.workflow.stages.decomposition.late_models import (
    _DECOMPOSER_ROLE,
    _LateAdjudication,
    _LateContext,
    _LateRun,
)

log = logging.getLogger("orchestrator.workflow")

# The stage a late run is attributed to on both observability surfaces. Late
# adjudication is an additive mode under the existing label, not a stage of
# its own, so an analytics row reads `decomposing` exactly as the initial
# decomposer's does.
_DECOMPOSING_STAGE = "decomposing"

_RETRY_COUNT = "retry_count"

_LATE_AGENT_ROLE = "late_agent_role"
_LATE_AGENT = "late_agent"
_LATE_SESSION_ID = "late_session_id"
_LATE_RUN_CYCLE_ID = "late_run_cycle_id"
_LATE_SOURCE_SHA = "late_source_sha"
_LATE_RUN_GENERATION = "late_run_generation"
_LATE_RESULT_VERDICT = "late_result_verdict"
_LATE_RESULT_CATEGORY = "late_result_category"
_LATE_RESULT_QUESTION = "late_result_question"
_LATE_RESULT_CHILDREN = "late_result_children"

# What a completed run recorded, and therefore what a fresh one has to drop.
_RESULT_KEYS = (
    _LATE_RESULT_VERDICT,
    _LATE_RESULT_CATEGORY,
    _LATE_RESULT_QUESTION,
    _LATE_RESULT_CHILDREN,
)

# What a recorded outcome is measured against: not its own size, but what the
# WHOLE pinned comment would become with it in -- the preserved held-PR body
# and every other stage's keys included. A result small enough on its own can
# still be the one that pushes the comment past what GitHub accepts, and
# finding that out from the failed write means the agent has already been paid
# for and the next tick pays again.
#
# The headroom below GitHub's limit is for the keys other stages still write
# into the same comment after an outcome is recorded -- watermarks, counters,
# a PR number. Leaving an outcome sitting exactly at the ceiling would move
# the failure onto whichever of them wrote next.
_COMMENT_HEADROOM = 4096

MAX_RECORDED_BODY = _pinned_state.MAX_PINNED_BODY - _COMMENT_HEADROOM

# How long a session id this record will pin. Every backend issues a bounded
# token, so an id past this is not one -- and pinning it would put the comment
# past the room a hold measured for it. The resume such an id would have
# served does not exist yet; a write that cannot land does.
MAX_SESSION_ID = 256


def _read_late_run(state: PinnedState) -> _LateRun:
    """Return the late run this issue is locked to, defaults where unset.

    Every field is read through the late domain's own defensive readers: a
    hand-edited or older value that cannot be typed reads back absent, so a
    damaged `late_result_verdict` leaves the run looking unanswered -- which
    costs one more adjudication -- rather than publishing on a verdict nobody
    recorded.
    """
    spec, backend, extra_args = _locked_spec(state)
    return _LateRun(
        role=_payloads.as_text(
            state.get(_LATE_AGENT_ROLE),
        ) or _DECOMPOSER_ROLE,
        session_id=_payloads.as_text(state.get(_LATE_SESSION_ID)),
        cycle_id=_payloads.as_identity(state.get(_LATE_RUN_CYCLE_ID)) or 0,
        source_sha=_payloads.as_hex(
            state.get(_LATE_SOURCE_SHA), _formats.COMMIT_LENGTHS,
        ) or "",
        generation=_payloads.as_count(state.get(_LATE_RUN_GENERATION)) or 0,
        verdict=_payloads.as_member(
            LateVerdict, state.get(_LATE_RESULT_VERDICT),
        ),
        category=_payloads.as_member(
            LateVerdictCategory, state.get(_LATE_RESULT_CATEGORY),
        ),
        question=_payloads.as_text(state.get(_LATE_RESULT_QUESTION)) or "",
        children=_recorded_children(state),
        spec=spec,
        backend=backend,
        extra_args=extra_args,
    )


def _recorded_children(state: PinnedState) -> tuple[dict, ...]:
    """Return the recorded child manifest, or nothing if it is not one.

    Held to the same rules the reply was: the child cap, the shape of each
    child, and the acyclicity of the graph they declare. A manifest a hand
    edit or an older binary left in a shape this validator refuses is not one
    children may be created from, and reading it back as empty is what sends
    the adjudicator round again instead of creating half of a split.
    """
    recorded = state.get(_LATE_RESULT_CHILDREN)
    if not isinstance(recorded, list) or not recorded:
        return ()
    if _split_validation._split_manifest_error({"children": recorded}):
        return ()
    return tuple(recorded)


def _locked_spec(state: PinnedState) -> tuple[str, str, tuple[str, ...]]:
    """Return the agent spec a late run is locked to, or the configured one.

    A legacy bare-backend value (`"codex"` / `"claude"`) re-parses to
    `(backend, ())` and round-trips cleanly, the way every other role's pin
    does.
    """
    stored = _payloads.as_text(state.get(_LATE_AGENT))
    if stored:
        backend, extra_args = config._parse_agent_spec(_LATE_AGENT, stored)
        return stored, backend, extra_args
    return (
        config.DECOMPOSE_AGENT_SPEC,
        config.DECOMPOSE_AGENT,
        config.DECOMPOSE_AGENT_ARGS,
    )


def _record_late_spawn(state: PinnedState, run: _LateRun) -> None:
    """Record what a late run IS, before that run can fail.

    Written ahead of the spawn for the reason the initial decomposer's spec
    is: a backend that produces an answer without surfacing a session id would
    otherwise leave the issue unattributed, and a later config flip could
    retarget its resume at a CLI that never ran here. The identity of the
    attempt goes with it, so the result recorded when the run returns cannot
    be read as an answer to a different generation or a different commit.

    The session goes only when the run is not continuing it. A resume keeps
    the pinned id so a tick that crashes mid-run resumes the same conversation
    rather than opening a second one; a fresh run drops it so a backend that
    surfaces none of its own cannot leave the next tick resuming the run this
    one replaced. The result is dropped either way -- what a new run decides
    replaces what the last one did, and a half-read record is not an answer.
    """
    state.set(_LATE_AGENT_ROLE, run.role)
    state.set(_LATE_AGENT, run.spec)
    state.set(_LATE_RUN_CYCLE_ID, run.cycle_id)
    state.set(_LATE_SOURCE_SHA, run.source_sha)
    state.set(_LATE_RUN_GENERATION, run.generation)
    if run.session_id:
        state.set(_LATE_SESSION_ID, run.session_id)
    else:
        state.data.pop(_LATE_SESSION_ID, None)
    for recorded in _RESULT_KEYS:
        state.data.pop(recorded, None)


def _drop_late_result(state: PinnedState) -> None:
    """Forget the outcome a completed run recorded, keeping its identity.

    What a human's answer to a categorized question earns. The record is what
    suppresses the next spawn, so a question the human has now answered has to
    stop being an answer before the adjudicator will run again -- and only the
    result goes, because the spec this issue is locked to and the session it
    opened are not what the human replied to.
    """
    for recorded in _RESULT_KEYS:
        state.data.pop(recorded, None)


def _record_late_session(state: PinnedState, agent_result: AgentResult) -> None:
    """Pin the session a finished run opened, when it surfaced one.

    Bounded, because the room for it was reserved before any pull request was
    ever held. A token longer than any backend issues is not one this may pin:
    it would push the comment past what the hold proved would fit, and the
    write that follows -- a park, or the outcome itself -- has nowhere else to
    go.
    """
    session_id = agent_result.session_id
    if not session_id:
        return
    if len(session_id) > MAX_SESSION_ID:
        log.error(
            "a %d-character session id is longer than any backend issues; "
            "not pinning it", len(session_id),
        )
        return
    state.set(_LATE_SESSION_ID, session_id)


def _record_late_result(
    state: PinnedState, adjudication: _LateAdjudication,
) -> bool:
    """Record the whole of a completed adjudication, or record none of it.

    What each verdict decided is what gets written: a `single` needs only
    itself, a `question` its category and the sentence it asked, and a `split`
    the ordered child manifest that IS its decision. Recording all of it is
    what lets a crashed tick recover the answer instead of paying for a second
    agent run that may not even decide the same way.

    Returns whether it fit -- measured on the whole comment this write would
    produce, not on the outcome alone, because the comment is shared and what
    is already in it counts. An outcome past the budget is refused whole
    rather than shortened: a truncated question asks something nobody said,
    and a truncated manifest names children nobody proposed. A caller told
    False has an outcome it cannot make durable, which is a human's problem
    and not a thing to half-record.
    """
    recorded = _result_payload(adjudication)
    if not _fits_the_comment({**state.data, **recorded}, MAX_RECORDED_BODY):
        return False
    for key, written in recorded.items():
        state.set(key, written)
    return True


def _fits_the_comment(state_data: dict, ceiling: int) -> bool:
    """Whether a pinned comment holding exactly this would fit its ceiling.

    The prospective body is rendered by the owner that writes it, so what is
    measured is the write rather than an estimate of it. The ceiling is the
    caller's, because what has to fit AFTER a write differs by which write it
    is: a hold still owes the comment the record that starts the run, while a
    completed outcome owes it only what other stages add later.
    """
    return len(
        _pinned_state.pinned_state_body(state_data),
    ) <= ceiling


def _result_payload(adjudication: _LateAdjudication) -> dict:
    """The pinned fields one completed adjudication is written as.

    The children are rewritten from the three fields a child issue is created
    out of rather than copied, so nothing an agent put beside them travels
    into the pinned comment a human reads and every other stage shares.
    """
    recorded = {_LATE_RESULT_VERDICT: str(adjudication.verdict)}
    if adjudication.category is not None:
        recorded[_LATE_RESULT_CATEGORY] = str(adjudication.category)
    if adjudication.question:
        recorded[_LATE_RESULT_QUESTION] = adjudication.question
    if adjudication.children:
        recorded[_LATE_RESULT_CHILDREN] = [
            {
                "title": child.get("title"),
                "body": child.get("body"),
                "depends_on": list(child.get("depends_on") or []),
            }
            for child in adjudication.children
        ]
    return recorded


def _recovered_adjudication(run: _LateRun) -> _LateAdjudication:
    """Rebuild the adjudication a recorded outcome stands for.

    Everything a caller acts on comes back: the verdict, the category, the
    question to announce, and the manifest to create children from. Only the
    agent's rationale does not, because prose is the one part of a reply the
    pinned comment deliberately never kept.
    """
    return _LateAdjudication(
        verdict=run.verdict,
        category=run.category,
        question=run.question,
        children=run.children,
    )


def _spawn_record_for(
    state: PinnedState,
    generation: LateGeneration,
    *,
    resuming: bool = False,
) -> _LateRun:
    """The record a run over this generation would be started under.

    One definition, because two callers have to agree on it exactly: the hold
    measures whether the comment could still hold this beside a preserved
    pull-request body, and the spawn writes it. A locked spec is an operator's
    command line and is not bounded by anything here, so measuring anything
    other than the real one would be measuring the wrong write.

    `resuming` is the caller saying this run carries a human's answer to the
    question the pinned session asked. It is not enough on its own: the record
    also has to say that session really ran against THIS cycle, generation,
    and commit, because a session pinned before a revision replaced the
    candidate holds a conversation about work nobody is adjudicating. A run
    that fails either test opens a fresh conversation, and the session id goes
    with the record it belonged to.
    """
    recorded = _read_late_run(state)
    continues = resuming and recorded.ran_against(generation)
    return replace(
        recorded,
        cycle_id=generation.cycle_id,
        source_sha=generation.candidate_sha,
        generation=generation.generation,
        session_id=recorded.session_id if continues else None,
    )


def _holdable(state_data: dict, generation: LateGeneration) -> bool:
    """Whether a comment holding this could still record the run beside it.

    Asked before a held PR's description is replaced, because the write that
    starts the run has no safe failure of its own: parking is another write of
    the same oversized comment, so a refusal there would strand the pull
    request held with nothing recorded and every retry raising again.

    What it measures is the real thing -- the locked spec, this generation's
    identities, and the bounded session id a finished run pins -- rather than
    a reserve standing in for them. The phase is the hold's own, which is the
    longer of the two spellings a late write puts there, so the measurement
    errs toward refusing.
    """
    written = PinnedState(data=dict(state_data))
    _record_late_spawn(written, _spawn_record_for(written, generation))
    written.set(_LATE_SESSION_ID, "s" * MAX_SESSION_ID)
    return _fits_the_comment(written.data, MAX_RECORDED_BODY)


def _spawn_late_adjudicator(
    context: _LateContext, run: _LateRun, worktree: Path,
) -> AgentResult:
    """Run the late adjudicator in the worktree holding the candidate.

    The candidate's own checkout, because the diff being adjudicated is
    between two commits this host holds and nothing has been pushed: a
    scratch checkout of the base branch could not show the agent the work it
    is being asked about.

    A session id on the record is one this run continues -- the record decided
    that, not this call -- so an answer to a categorized question reaches the
    agent that asked it. `None` opens a fresh conversation, which is what
    every run that is not answering one gets.
    """
    return _usage._run_agent_tracked(
        context.gh, context.issue.number,
        agent_role=run.role,
        stage=_DECOMPOSING_STAGE,
        backend=run.backend,
        prompt=_prompt._build_late_decompose_prompt(
            context.spec,
            context.issue,
            _comments._recent_comments_text(context.issue),
            context.generation,
            config.default_repo_specs(),
        ),
        cwd=worktree,
        agent_spec=run.spec,
        resume_session_id=run.session_id,
        extra_args=run.extra_args,
        retry_count=context.state.get(_RETRY_COUNT),
    )
