# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Turning a committed worktree into a pushed branch, a PR, and a handoff.

The order here is what makes the step re-runnable. The push comes first and a
failed push parks instead of continuing, because the commits stay in the
worktree and would otherwise keep `_has_new_commits` true and re-comment on
every poll. The PR is then reused if one is already open on the branch, so a
tick that died between `open_pr` and the relabel recovers instead of 422-ing on
a duplicate. Only then is the handoff written -- `pr_number` AND `branch`
together, because a state that arrived here without a branch (an awaiting-human
resume that opened the PR without passing the fresh-spawn persist site) would
leave the next tick's branch resolution falling back to the legacy name while
the live PR sits on the slug-namespaced one.

Resetting the counters is part of the same write, not bookkeeping beside it: the
issue moved forward, so the review round, the retry budget, the silent-park
streak, and the timeout watermark are all spent, and any of them left behind
would mis-fire a later hop back into implementing.

None of it happens without ONE named commit, which is what the first line
here establishes: a push named against nothing sends whatever the branch has
become by the time git runs it, records no receipt, and leaves both proofs
around it with nothing to compare against -- so a checkout that cannot say
what it is on publishes nothing rather than publishing unnamed.

What that checkout IS gets proved twice around all of it, and each proof has
two halves. The commit is one: a head that moved off the approved candidate is
refused before the push and again once the pull request is open. The tree is
the other, and it is why the disposition's own reading is not enough -- work
can appear beside a commit without moving it, so the head proof passes while
the checkout stops being the thing that was measured. Everything past the
handoff reads that checkout and none of it measures again.

The title is chosen from the branch's own first commit subject, falling back to
a prefix inferred from recent base history, so the PR reads like the repository
it lands in rather than like the orchestrator.
"""
from __future__ import annotations

import logging
from pathlib import Path

from github.Issue import Issue

from orchestrator import config
from orchestrator.agents import AgentResult
from orchestrator.git import authentication as _authentication
from orchestrator.git.measurement import commits as _measurement_commits
from orchestrator.git.publication import (
    probes as _publication_probes,
    titles as _titles,
)
from orchestrator.git.verification import probes as _verification_probes
from orchestrator.git.worktrees import paths as _worktree_paths
from orchestrator.github import client as _client, pinned_state as _pinned_state
from orchestrator.workflow.engine import (
    comments as _comments,
    guards as _guards,
    retry_budget as _retry_budget,
)
from orchestrator.workflow.stages.discussion.state import (
    _PLAN_SHA as _DISCUSSION_PLAN_SHA,
)
from orchestrator.workflow.stages.implementing import (
    late_parks as _late_parks,
    models as _models,
    session_read as _session_read,
    state as _state,
)
from orchestrator.workflow.state import WorkflowLabel

log = logging.getLogger("orchestrator.workflow")

# How the checkout's own head is named for this comparison. It goes
# through the same proof the size gate read it with -- resolved, peeled,
# and hardened -- so the two cannot disagree about what commit a worktree
# is on while one of them decides the other may publish.
_HEAD = "HEAD"

_MOVED_AFTER_PUSH_PARK = (
    "{mentions} this issue's branch was published at `{published}` and its "
    "pull request carries it, but the worktree moved to `{head}` while that "
    "was happening -- so the issue was not handed to review. What review "
    "reads is the checkout, and every stage past the handoff rewrites it: a "
    "worktree left on a commit nobody measured reaches a merge through a "
    "squash or a docs pass, one force-push later. Nothing was discarded and "
    "the published branch is untouched. Put the worktree back on "
    "`{published}` and the handoff finishes by itself on the next tick, with "
    "nothing re-run and no agent spawned, or leave it where it is and reply "
    "with the change you want made."
)

# How many loose paths a refusal names before it starts counting instead.
_NAMED_PATHS = 10

_DIRTIED_BEFORE_PUSH_PARK = (
    "{mentions} this issue's worktree is on {commit} -- the commit this "
    "publication was about -- but {loose}, so nothing was published. What a "
    "push sends is the COMMIT, and every stage past the handoff reads the "
    "CHECKOUT: review would be handed a tree carrying work the pull request "
    "does not show, and the squash and the docs pass would commit it or "
    "destroy it. Nothing was discarded and the branch is untouched. Commit "
    "the loose work as its own candidate, or clear it, and this one publishes "
    "by itself on the next tick with nothing re-run and no agent spawned -- "
    "or leave it and reply with the change you want made."
)

_DIRTIED_AFTER_PUSH_PARK = (
    "{mentions} this issue's branch was published at `{commit}` and its pull "
    "request carries it, but {loose} -- so the issue was not handed to "
    "review. What review reads is the checkout, and every stage past the "
    "handoff rewrites it: uncommitted work beside a published branch is "
    "squashed away or committed on top, one force-push later, with nothing "
    "having measured it. Nothing was discarded and the published branch is "
    "untouched. Commit the loose work as its own candidate, or clear it, and "
    "the handoff finishes by itself on the next tick with nothing re-run and "
    "no agent spawned -- or leave it and reply with the change you want made."
)

_UNPROVABLE_HEAD_PARK = (
    "{mentions} this issue's worktree could not say which commit it is on "
    "({failure}), so nothing was published. A push named against no commit "
    "sends whatever the branch has become by the time git runs it, and leaves "
    "nothing on the issue afterwards saying which commit that was -- so the "
    "two proofs taken around the push have nothing to hold the checkout to "
    "either, and review is handed whatever is there. Nothing was discarded, "
    "the commit is still in the worktree, and the branch is untouched. Clear "
    "what is stopping the read, then reply and the orchestrator will resume "
    "the session."
)

_MOVED_CHECKOUT_PARK = (
    "{mentions} this issue's worktree is on `{head}`, not the commit the size "
    "gate measured and approved (`{approved}`), so nothing was published: "
    "handing review a checkout the gate never saw is how an unmeasured "
    "implementation reaches a merge. Nothing was discarded and the branch is "
    "untouched. Put the worktree back on `{approved}` and it publishes by "
    "itself on the next tick, with nothing re-run and no agent spawned, or "
    "leave it where it is and reply with the change you want made."
)


def _format_pr_agent_message(
    message: str, *, cap: int = _state._PR_BODY_AGENT_MESSAGE_CAP
) -> str:
    """Return the agent's final message ready to embed in a PR body.

    A message within `cap` is returned verbatim. A longer one is trimmed on the
    nearest paragraph -> line -> word boundary before `cap` and an explicit
    `_…(message truncated)_` marker is appended, so the PR body reads as
    intentionally clipped rather than severed mid-sentence. A dangling code
    fence in the trimmed region is closed first so the marker (and any following
    body) renders outside the half-open block instead of being swallowed by it.
    """
    if len(message) <= cap:
        return message
    head = message[:cap]
    # Prefer a paragraph break, then a line break, then a word boundary, so the
    # cut lands somewhere readable instead of mid-token.
    for sep in ("\n\n", "\n", " "):
        idx = head.rfind(sep)
        if idx > 0:
            head = head[:idx]
            break
    head = head.rstrip()
    # An odd count of ``` fences means the cut landed inside a fenced block;
    # close it so GitHub doesn't swallow the marker into the open code block.
    if head.count("```") % 2:
        head = f"{head}\n```"
    return f"{head}\n\n{_state._PR_BODY_TRUNCATION_MARKER}"


def _derive_pr_title(spec: config.RepoSpec, issue: Issue, wt: Path) -> str:
    """PR title for a freshly opened dev PR.

    Prefers the first commit's conventional subject; when that carries no
    recognizable `<type>:` prefix, one is inferred from recent base-branch
    history (`_infer_subject_prefix`) and applied to the issue title.
    """
    first_subject = _publication_probes._first_commit_subject(spec, wt)
    fallback_prefix = _titles._infer_subject_prefix(spec, wt, issue)
    return _titles._pr_title_from_commit_or_issue(
        issue, first_subject, fallback_prefix,
    )


def _dev_pr_attribution(state: _pinned_state.PinnedState) -> str:
    """Which dev session the branch on this PR was written by.

    Its own line because two owners need it: the body that states it, and the
    reuse below, which reads a PR of unknown provenance for it before adopting
    that PR as this implementation's.
    """
    _, dev_backend, _, dev_sid = _session_read._read_dev_session(state)
    session_id = dev_sid or "?"
    return f"Generated by orchestrator ({dev_backend} session `{session_id}`)."


def _build_pr_body(
    state: _pinned_state.PinnedState, issue: Issue, agent_result: AgentResult,
) -> str:
    """PR body: the `Resolves #N` line, the generating session's identity, and
    the (capped) final agent message when the run produced one."""
    body_parts = [
        f"Resolves #{issue.number}",
        "",
        _dev_pr_attribution(state),
    ]
    if agent_result.last_message.strip():
        body_parts += [
            "", "---", "_Last agent message:_", "",
            _format_pr_agent_message(agent_result.last_message),
        ]
    return "\n".join(body_parts)


def _reuse_or_open_pr(
    gh: _client.GitHubClient,
    spec: config.RepoSpec,
    issue: Issue,
    state: _pinned_state.PinnedState,
    work: _models._PRWork,
):
    """Return the PR for `branch`, reusing an open one or opening a new one.

    Recovers gracefully if a previous tick crashed between `open_pr` and the
    relabel: an existing open PR is reused instead of 422-ing on a duplicate.
    Opening a new PR posts the ":sparkles: PR opened" comment and emits the
    `pr_opened` event; reuse only logs.
    """
    pr = gh.find_open_pr(branch=work.branch, base=spec.base_branch)
    if pr is not None:
        log.info(
            "issue=#%s reusing existing PR #%d for %s",
            issue.number, pr.number, work.branch,
        )
        _attribute_reused_pr(gh, issue, state, work, pr)
        return pr
    pr = gh.open_pr(
        branch=work.branch, base=spec.base_branch,
        title=_derive_pr_title(spec, issue, work.worktree),
        body=_build_pr_body(state, issue, work.agent_result),
    )
    _comments._post_issue_comment(gh, issue, state, f":sparkles: PR opened: #{pr.number}")
    gh.emit_event(
        "pr_opened",
        issue_number=issue.number,
        stage=_state._IMPLEMENTING_STAGE,
        pr_number=pr.number,
        branch=work.branch,
        sha=getattr(pr.head, "sha", None) or None,
        retry_count=state.get(_state._RETRY_COUNT),
    )
    return pr


def _attribute_reused_pr(
    gh: _client.GitHubClient,
    issue: Issue,
    state: _pinned_state.PinnedState,
    work: _models._PRWork,
    pr,
) -> None:
    """Make a PR opened elsewhere describe the work now pushed onto it.

    What `find_open_pr` returns is only known to be open on this branch. The
    sharpest case is the `discussion` stage's plan PR: an issue relabeled here
    arrives with it open on the very branch the dev commits go to, so a silent
    reuse leaves a body saying the branch is one Markdown file and changes
    nothing else -- a claim the push just made false -- under the decomposer's
    session rather than the developer's, and with no `Resolves #N` to close
    the issue when it merges. An operator's own PR on the branch is the same
    problem with different words.

    The dev attribution is what decides. Its absence means the body is about
    something other than this implementation and is rewritten; its presence
    means this stage already wrote it (a tick that died between `open_pr` and
    the relabel), and everything it says -- including what a human added
    underneath -- is left alone.
    """
    if _dev_pr_attribution(state) in (getattr(pr, "body", "") or ""):
        return
    log.info(
        "issue=#%s rewriting reused PR #%d body to name this implementation",
        issue.number, pr.number,
    )
    gh.edit_pr_body(pr, _build_pr_body(state, issue, work.agent_result))


def _advance_to_validating(
    gh: _client.GitHubClient, issue: Issue, state: _pinned_state.PinnedState, pr, branch: str
) -> None:
    """Record the published PR/branch, reset the per-PR budgets, and hand off
    to `validating`.

    The docs pass runs only as the final-docs handoff after the reviewer agent
    approves, so a fresh commit goes straight to validating.

    What this staged goes out DURABLY before the label does, and that ordering
    is the whole of why the write is here rather than left to the caller. The
    label is the last thing on this road that another stage reads, and past it
    the issue is no longer implementing's: nothing here runs on it again. So
    every record this line spends -- the plan SHA, the certified baseline, the
    handoff anchor, and above all the commit an approval said was still owed a
    push -- has to be spent before the label, or a tick that died in between
    strands it on an issue that has moved on. A stranded approval is the
    sharpest: nothing under `validating` spends it, implementing never sees
    the issue again, and the record goes on freezing the branch out of the
    ordinary base refresh for the rest of the issue's life.

    The cost is one pinned write per publication, and the window it leaves is
    the one the commit this line records exists for. A relabel that failed --
    or a process that died between the two -- leaves an implementing issue
    whose branch is pushed and whose pull request is open, and whose every
    gate record is already spent. Read as work nobody has ruled on, that
    branch is measured again on the next tick, against a base that has moved
    or a ceiling that was retuned since, and an oversized answer would route
    it to adjudication with the push and the pull request already made. So the
    pushed commit goes down in this same write: the next tick recognizes it,
    publishes it without a reading, reuses the pull request that already
    carries it, and finishes the relabel this one could not.
    """
    state.set(_state._PR_NUMBER, pr.number)
    # Whatever this issue's recorded PR was before, it is an implementation's
    # now. The `discussion` stage records the commit its plan PR carried so
    # implementing's merged-PR terminal does not read a design being agreed to
    # as work having landed; that record is spent here. It is hygiene rather
    # than the guard itself -- the guard asks the PR's head, so it answers
    # right even for the tick that pushed and died before reaching this line.
    state.set(_DISCUSSION_PLAN_SHA, None)
    # And the handoff that record was written by is spent with it. It says the
    # relabel was accepted and nothing here has published since, which stops
    # being true on this line: it is what freezes base sync for the branch and
    # what has the reconcile keep re-anchoring the checkout onto the plan PR,
    # and an issue leaving for `validating` still carrying it would take both
    # with it.
    state.set(_state._READ_ONLY_BASELINE_SHA, None)
    state.set(_state._HANDOFF_ANCHOR_SHA, None)
    # Persist the pushed branch alongside `pr_number` so the next tick's
    # `_resolve_branch_name` can recover it directly. Without this, a state
    # that lacked `branch` going in (e.g. an awaiting-human resume that opened
    # the PR here without first passing through the fresh-spawn branch-persist
    # site) would leave `pr_number` set with `branch` unset; the legacy-PR
    # fallback in `_resolve_branch_name` would then misroute every downstream
    # tick to `orchestrator/issue-<n>` while the live PR is on the
    # slug-namespaced branch this push just published.
    state.set(_state._BRANCH, branch)
    _reset_implementing_counters(state)
    gh.write_pinned_state(issue, state)
    gh.set_workflow_label(issue, WorkflowLabel.VALIDATING)


def _reset_implementing_counters(state: _pinned_state.PinnedState) -> None:
    # Reset the review counter every time we (re-)open a PR so the validating
    # handler starts fresh on the new branch state.
    state.set("review_round", 0)
    # Issue moved forward; reset the implementing retry budget so any future
    # bounce back into implementing (e.g. validating -> implementing in a
    # later stage) starts with a fresh window.
    state.set(_state._RETRY_COUNT, 0)
    state.set(_state._RETRY_WINDOW_START, None)
    # The attempts a continuation left go with the accounting they replaced:
    # they are what a human bought this issue under the budget just reset, and
    # kept past that they would hold a shipped issue to the grant rather than
    # to the budget it now has again.
    state.set(_retry_budget.RETRY_CAP_CONTINUED, None)
    # The session just produced commits, so it isn't poisoned -- reset the
    # silent-park streak so a future blip doesn't tip an otherwise-healthy
    # session past the fresh-session threshold.
    state.set(_state._SILENT_PARK_COUNT, 0)
    # The commit shipped, so any agent-timeout park watermark is spent -- clear
    # it (and the stale reason) so it cannot linger into `validating` or
    # mis-fire the next-tick timeout recovery on a later implementing hop.
    if state.get(_state._PARK_REASON) == _state._AGENT_TIMEOUT:
        state.set(_state._PARK_REASON, None)
    state.set(_state._PRE_IMPLEMENT_SHA, None)
    # The commit an approval said was still owed a push: this IS that push,
    # so the debt is paid -- and the head it was pinned against with it, since
    # a lease outliving the publication it was frozen for would pin the next
    # one to a head this push has already moved. Spent here rather than after
    # the relabel because past the relabel the issue belongs to another stage,
    # and a record left behind would freeze this branch out of the base
    # refresh with nothing in implementing ever coming back to drop it.
    _late_parks._forget_approval(state)


def _moved_off_the_candidate(
    gh: _client.GitHubClient,
    issue: Issue,
    state: _pinned_state.PinnedState,
    approved: _models._ApprovedWork,
    worktree: Path,
) -> bool:
    """Refuse a handoff whose checkout is not the commit that was approved.

    The window is small and the consequence is not: the size gate reads the
    worktree, and between that reading and this write a descendant the timeout
    cleanup raced, a second process, or an operator can move `HEAD`. The push
    itself is safe -- it names the approved commit -- but the checkout is what
    every stage past this one works from, and one sitting on an unmeasured
    descendant is an implementation that reaches review, a squash, and a merge
    without the gate ever having seen it.

    So the tick stops here. Nothing is pushed and no pull request is opened,
    which keeps the recovery cheap: the commit is still in the worktree, the
    branch is untouched, and a checkout put back on the approved commit
    republishes it unchanged -- while one deliberately left on the descendant
    is measured as the fresh candidate it is on the next run.

    Asked only where the GATE approved a commit. A candidate the switch kept
    out of it was never proved there, so there is nothing this proof could
    compare a head to -- the intent owner beside this one resolves the head
    itself, and the proof taken once the pull request is open holds the
    checkout to whichever of the two named the commit that went out.
    """
    if not approved.candidate_sha:
        return False
    proved = _measurement_commits._prove_candidate_commit(worktree, _HEAD)
    head = proved.sha
    if proved.is_frozen and head == approved.candidate_sha:
        return False
    log.error(
        "issue=#%s worktree is on %s rather than the approved commit %s; "
        "refusing to hand an unmeasured checkout to review",
        issue.number, head or "an unreadable head", approved.candidate_sha,
    )
    _guards._park_awaiting_human(
        gh, issue, state,
        _MOVED_CHECKOUT_PARK.format(
            mentions=config.HITL_MENTIONS,
            approved=approved.candidate_sha,
            head=head or "an unreadable head",
        ),
        reason=_state._CANDIDATE_MOVED,
    )
    state.set(_state._PARK_REASON, _state._CANDIDATE_MOVED)
    # What the refusal is waiting on, written where something can act on it.
    # Nothing else on the issue still names this commit -- the record it came
    # from was retired ahead of the effects it licensed -- so without it the
    # park names a SHA in prose and the operator who does exactly the right
    # thing gets no acknowledgement for it: ordinary ticks stay parked and a
    # bare continue is refused as one with no guidance on it.
    state.set(_state._APPROVED_SHA, approved.candidate_sha)
    return True


def _publication_intent(
    gh: _client.GitHubClient,
    issue: Issue,
    state: _pinned_state.PinnedState,
    approved: _models._ApprovedWork,
    worktree: Path,
) -> str | None:
    """The one commit this publication is about, durable before it is pushed.

    Everything past this line is named against what it returns: the push, the
    record the handoff leaves, and the proof taken once the pull request is
    open. Deciding it once and up front is what keeps those three about the
    same commit -- a checkout re-read at any of them is a checkout that may
    have moved since.

    The gate names it wherever it proved one. Where it did not -- a candidate
    the switch kept out of the gate -- the checkout names it, because the
    alternative is a push that names nothing and therefore publishes whatever
    the branch has become by the time git runs it, with nothing on the issue
    afterwards saying which commit that was. The switch keeps candidates out
    of the MEASUREMENT; it does not make them unnameable, and it is an
    operator's to turn back on between one tick and the next.

    Then it is made durable, and only where the record does not already say
    it. Between this line and the handoff the branch goes to the remote and a
    pull request opens over it, and a tick that died in there would leave an
    issue whose branch is published and whose record says nothing was owed --
    which the next tick reads as work nobody has ruled on. The roads that
    were approved or adjudicated already wrote this commit down and pay
    nothing here; the ones that were not pay one write.

    None is the answer that stops the publication, and both roads reach it.
    The checkout is not on the commit the gate approved, so nothing may be
    pushed from it -- or the checkout cannot say what it is on at all, which
    is a repository to look at rather than a commit to name. Neither publishes
    anything.

    That second one is a refusal rather than a fallback because of what a
    nameless push COSTS. Named against nothing, git sends whatever the branch
    has become by the time it runs, and nothing goes on the issue saying which
    commit that was -- so the receipt the handoff leaves is empty, the proof
    taken once the pull request is open has no commit to hold the checkout to,
    and the one taken before the push has none either. Every guarantee this
    owner exists to make is about one named commit, and a publication with no
    name is outside all of them at once.
    """
    if approved.candidate_sha:
        if _moved_off_the_candidate(gh, issue, state, approved, worktree):
            return None
        return _recorded_intent(gh, issue, state, approved.candidate_sha)
    proved = _measurement_commits._prove_candidate_commit(worktree, _HEAD)
    if proved.is_frozen:
        return _recorded_intent(gh, issue, state, proved.sha)
    log.error(
        "issue=#%s worktree cannot name the commit it is on (%s); refusing to "
        "publish a branch under no commit", issue.number, proved.failure,
    )
    _park_for_the_checkout(
        gh, issue, state,
        _UNPROVABLE_HEAD_PARK.format(
            mentions=config.HITL_MENTIONS, failure=proved.failure,
        ),
    )
    return None


def _recorded_intent(
    gh: _client.GitHubClient,
    issue: Issue,
    state: _pinned_state.PinnedState,
    published: str,
) -> str:
    """Make the commit about to be pushed durable, if it is not already.

    It is recorded as the commit this issue owes a push, because that is what
    it is right up to the moment the push lands -- the same field an approval
    writes, spent by the same handoff, and read by the same pre-spawn proof if
    this tick does not get that far. A record already naming it is left alone,
    which is every road the gate proved and decided a commit on.
    """
    if _late_parks._approved_commit(state) == published:
        return published
    state.set(_state._APPROVED_SHA, published)
    gh.write_pinned_state(issue, state)
    return published


def _loose_work(tree: _verification_probes._WorktreeStatus) -> str:
    """Say what a tree reading refused on, in the words the refusal needs.

    A reading that never HAPPENED is the one an operator would otherwise be
    told nothing about. It names no paths, so a message built from the list
    alone reads as "0 uncommitted changes" and sends them looking through a
    tree for a file that was never the problem -- while what they have to
    clear is a `git status` that will not run or an index bit that makes what
    it does report worthless.
    """
    if not tree.paths:
        return (
            "its state could not be read (`git status` failed, or an index "
            "entry is marked `assume-unchanged`/`skip-worktree`)"
        )
    shown = tree.paths[:_NAMED_PATHS]
    named = ", ".join(f"`{path}`" for path in shown)
    elided = len(tree.paths) - len(shown)
    if elided:
        named = f"{named}, … ({elided} more)"
    return f"it now carries uncommitted changes: {named}"


def _park_for_the_checkout(
    gh: _client.GitHubClient,
    issue: Issue,
    state: _pinned_state.PinnedState,
    message: str,
) -> None:
    """Hold the issue for a checkout nothing may be handed over from.

    Under the reason a moved checkout earns, because every refusal that
    reaches here is the same one a field over: what stops is the HANDOFF,
    what settles it is the worktree rather than words, and the recovery that
    watches for it asks the checkout the questions this stage publishes on --
    the commit it is on, and whether what is around that commit can be proved
    to be nothing. The comment is what tells an operator which of them it is;
    the reason is the control field, and a second one would need a second
    recovery to mean anything different.

    The refusal with no commit to record is the one that stays put: the
    quiet republication is keyed off the commit a park writes down, and a
    checkout that could not say what it is on writes none -- so that park
    waits for a human, and their reply resumes the session as any other
    unpublishable checkout's does.
    """
    _guards._park_awaiting_human(
        gh, issue, state, message, reason=_state._CANDIDATE_MOVED,
    )
    state.set(_state._PARK_REASON, _state._CANDIDATE_MOVED)


def _dirtied_before_the_push(
    gh: _client.GitHubClient,
    issue: Issue,
    state: _pinned_state.PinnedState,
    published: str,
    worktree: Path,
) -> bool:
    """Refuse a publication whose tree stopped being provably clean.

    The half of the same race the head proof cannot see. Cleanliness was
    proved once, at the top of the disposition, and everything between that
    reading and this one is time an agent's descendant, a second process, or
    an operator can write in -- with `HEAD` never moving, so every proof taken
    against the commit passes. What goes out is right; what is wrong is the
    CHECKOUT, and the checkout is what the handoff passes on. Review reads a
    dirty tree as work to publish, the squash rewrites what is on it, and the
    docs pass commits over it, so uncommitted work that slipped in here
    reaches a merge with nothing having measured it -- and the stage this
    hands to takes no reading of its own.

    So the tick stops before the push rather than after: nothing is on the
    remote, no pull request is open, and the commit is exactly where the
    developer left it. The commit was made durable a line above, so a checkout
    whose tree is cleaned republishes it on the next tick with nothing re-run.
    """
    tree = _verification_probes._worktree_status(worktree)
    if tree.is_clean:
        return False
    loose = _loose_work(tree)
    log.error(
        "issue=#%s worktree carries work no push would publish (%s) while on "
        "%s; refusing to publish an unproven checkout",
        issue.number, loose, published,
    )
    _park_for_the_checkout(
        gh, issue, state,
        _DIRTIED_BEFORE_PUSH_PARK.format(
            mentions=config.HITL_MENTIONS,
            commit=f"`{published}`",
            loose=loose,
        ),
    )
    return True


def _dirtied_after_the_push(
    gh: _client.GitHubClient,
    issue: Issue,
    state: _pinned_state.PinnedState,
    published: str,
    worktree: Path,
) -> bool:
    """Refuse the handoff when the tree stopped being clean around the push.

    The window the pre-push reading cannot cover, asked of the tree the way
    the proof beside it is asked of the head: the push, the pull-request
    lookup, and the open are three requests long, and the worktree is writable
    for all of them. A descendant the timeout cleanup raced is the commonest
    thing to write there, and it does not have to commit to do damage -- an
    unstaged edit beside a published branch is squashed away or committed on
    top by the stages past the handoff, neither of which measured it.

    So the publication stands and the handoff stops, exactly as it does for a
    head that moved: the branch is on the remote, its pull request carries the
    commit, and the label does not move. What the commit is RECORDED as is the
    caller's, because the two sides promise different things about the remote:
    an initial publication's push opens the pull request and reads the remote
    for itself, while a push onto one the remote already carries knows exactly
    which head it left the branch on and can pin the republication to it.
    """
    tree = _verification_probes._worktree_status(worktree)
    if tree.is_clean:
        return False
    loose = _loose_work(tree)
    log.error(
        "issue=#%s worktree carries work no push published (%s) after %s went "
        "out; refusing to hand an unproven checkout to review",
        issue.number, loose, published,
    )
    _park_for_the_checkout(
        gh, issue, state,
        _DIRTIED_AFTER_PUSH_PARK.format(
            mentions=config.HITL_MENTIONS,
            commit=f"`{published}`",
            loose=loose,
        ),
    )
    return True


def _moved_after_the_push(
    gh: _client.GitHubClient,
    issue: Issue,
    state: _pinned_state.PinnedState,
    published: str,
    worktree: Path,
) -> bool:
    """Refuse the handoff when the checkout left the commit that was pushed.

    The window the pre-push proof cannot cover. The push, the pull-request
    lookup, and the open are all requests, and the worktree is writable while
    they run -- a descendant the timeout cleanup raced is the commonest thing
    to move it. What went out is exactly the commit that was named, so the
    branch and the pull request are right; what is wrong is the CHECKOUT, and
    the checkout is what every stage past this one works from. The reviewer
    reads a head ahead of the pushed branch as unpushed work to publish, the
    squash rewrites what is on it, and the docs pass commits on top -- so a
    worktree left on an unmeasured descendant reaches a merge through a
    force-push no measurement ever saw.

    So the handoff stops rather than the publication being taken back. The
    commit is on the remote and its pull request carries it, which is what the
    record written a line above says; the label does not move, so review never
    reads the descendant; and the park names the commit the checkout has to go
    back to. Putting it back republishes with nothing re-run, and leaving it
    there measures it as the fresh candidate it is on the next run.

    What the commit is RECORDED as owing is the caller's, for the reason the
    dirty reading beside this one gives: the two sides of the gate promise
    different things about the head the republication would be pinned to.
    """
    proved = _measurement_commits._prove_candidate_commit(worktree, _HEAD)
    if proved.is_frozen and proved.sha == published:
        return False
    head = proved.sha or "an unreadable head"
    log.error(
        "issue=#%s worktree moved to %s after %s was pushed; refusing to hand "
        "an unmeasured checkout to review", issue.number, head, published,
    )
    _guards._park_awaiting_human(
        gh, issue, state,
        _MOVED_AFTER_PUSH_PARK.format(
            mentions=config.HITL_MENTIONS, published=published, head=head,
        ),
        reason=_state._CANDIDATE_MOVED,
    )
    state.set(_state._PARK_REASON, _state._CANDIDATE_MOVED)
    return True


def _on_commits(
    gh: _client.GitHubClient,
    spec: config.RepoSpec,
    issue: Issue,
    state: _pinned_state.PinnedState,
    approved: _models._ApprovedWork,
) -> None:
    """Push the branch, open or reuse its PR, and hand off to validating.

    One commit is decided on before any of this runs, and the push, the
    record the handoff leaves, and the proof taken once the pull request is
    open are all about that one. The commit on `approved` is it wherever the
    size gate proved one; where the gate proved none -- a candidate the switch
    kept out of it -- the checkout names it instead. A checkout that cannot
    name one publishes nothing at all, because a push that names nothing sends
    whatever the branch has become by the time git runs it and leaves every
    proof past this line with no commit to hold it to.
    `_publication_intent` is where that is settled and made durable.

    Naming the commit is only half of it, because what the handoff passes on
    is the CHECKOUT. Every stage past this one reads that checkout: the
    reviewer treats a head ahead of the pushed branch as unpushed work to
    publish, the squash rewrites what is on it, and the docs pass commits on
    top. So a worktree sitting on a descendant would hand review an
    implementation the size gate never saw, one publication later and with no
    measurement between. That is asked twice, because the window is the three
    requests in between: before the push nothing is published and the commit
    stays where it is, and after the pull request is open the publication
    stands while the HANDOFF stops, so review never reads the descendant.

    Both boundaries ask it of the TREE as well as of the head, because the
    head answers only half of what "this checkout" is. Uncommitted work can
    appear while `HEAD` never moves, so every proof about the commit passes
    over it -- and the stage this hands to takes no reading of its own, so a
    tree carrying work the pull request does not show reaches the squash and
    the docs pass, which commit it or destroy it. Cleanliness proved at the
    top of the disposition is a fact about a moment that has passed by the
    time either effect runs.
    """
    agent_result = approved.agent_result
    wt = _worktree_paths._worktree_path(spec, issue.number)
    published = _publication_intent(gh, issue, state, approved, wt)
    if published is None:
        return
    if _dirtied_before_the_push(gh, issue, state, published, wt):
        return
    branch = _worktree_paths._resolve_branch_name(state, spec, issue.number)
    if not _authentication._push_branch(
        spec, wt, branch, revision=published,
        # The head an approval taken on the PUBLISHED side was frozen
        # against, where there is one. A candidate a settled adjudication
        # sends back here was measured against a pull request the remote
        # already carries, and the reading it was measured under is only worth
        # what the head it was taken over still is -- so the push is pinned to
        # that head and a pull request somebody moved during the adjudication
        # rejects it instead of being force-overwritten. None for an initial
        # publication, whose push reads the remote for itself as it always
        # did: there was no pull request to freeze.
        force_with_lease=_late_parks._approved_lease(state) or None,
    ):
        # Park on awaiting_human like the timeout/question paths. Otherwise the
        # worktree's commits keep _has_new_commits() true, so every poll would
        # re-enter _on_commits() and re-comment indefinitely until a human acts.
        _guards._park_awaiting_human(
            gh, issue, state,
            f"{config.HITL_MENTIONS} git push failed; see orchestrator logs.",
            reason="push_failed",
        )
        # _handle_implementing writes pinned state after we return.
        return
    pr = _reuse_or_open_pr(
        gh, spec, issue, state, _models._PRWork(agent_result, wt, branch),
    )
    # The push landed, so what was an intent is now a receipt: staged here so
    # the handoff write below carries it, and so a relabel that does not land
    # leaves the next tick something to recognize an already published branch
    # by rather than work nobody has ruled on. It names no head it replaced --
    # an initial publication froze none and reads the remote for itself -- and
    # says so rather than leaving whatever the last published-side push wrote,
    # which would date this receipt to an attempt it was not made under.
    _late_parks._record_publication(state, published, "")
    if _moved_after_the_push(gh, issue, state, published, wt):
        _owes_the_handoff(state, published)
        return
    if _dirtied_after_the_push(gh, issue, state, published, wt):
        _owes_the_handoff(state, published)
        return
    _advance_to_validating(gh, issue, state, pr, branch)


def _owes_the_handoff(
    state: _pinned_state.PinnedState, published: str,
) -> None:
    """Record the commit a checkout this stage may not hand on still owes.

    The commit and no lease, which is what an INITIAL publication can promise:
    the push above is the one that opened this pull request, and the head the
    quiet republication would be pinned to is whatever that push reads off the
    remote for itself when it runs. A pull request the remote already carried
    is the other side of the gate, and it records both -- the reconciliation
    ahead of every handler reads the pair as the claim it is, and half of one
    there is damage rather than a debt.
    """
    state.set(_state._APPROVED_SHA, published)
