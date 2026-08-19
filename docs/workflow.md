# Workflow — agent roles and command specs

This file documents the agent-role side of the workflow: which stage invokes which role, how the role command specs
(`DEV_AGENT` / `REVIEW_AGENT` / `DECOMPOSE_AGENT`) are parsed, and how the spec used by an in-flight issue is pinned
for the life of its session.

For the full stage-by-stage state machine (label semantics, per-stage handler internals, per-tick flow), see
[`state-machine.md`](state-machine.md). For the higher-level design (multi-repo dispatch, push hardening, agent
subprocess shape), see [`architecture.md`](architecture.md). For the audit event log, analytics sink, and usage parser,
see [`observability.md`](observability.md). For env vars and the operator runbooks beside them, see
[`configuration.md`](configuration.md). For the user-facing summary, see [`../README.md`](../README.md).

Stage and label names are spelled apart here as they are in
[`state-machine.md`](state-machine.md#workflow-labels): a bare tag names the **stage** — the handler, the subpackage
under `orchestrator/workflow/stages/` holding it, and the identifier a session's analytics row is attributed to —
while `workflow:<tag>` is the **wire label** the GitHub issue carries. `in_review`, `question`, `discussion`, and the
`done` / `rejected` terminals were never namespaced, so those read the same on both sides.

## Roles and the workflow stages that invoke them

The workflow has three agent roles, each spawned by a different set of stage handlers. Roles are independent: each can
use `codex` or `claude` and each carries its own optional CLI args.

- **Decomposer** (`DECOMPOSE_AGENT`, default `claude`) — spawned by `_handle_decomposing` (and its `awaiting_human`
  resume); `_handle_question` (and its `awaiting_human` resume) and `_handle_discussion` reuse the same backend.
  Session: locked per issue after first spawn (decomposing → `decomposer_agent`; question → `question_agent`;
  discussion → `discussion_agent`, each a separate pin).
- **Implementer / dev** (`DEV_AGENT`, default `claude`) — spawned by `_handle_implementing`, `_handle_documenting`,
  `_handle_validating` (awaiting-human resume; the `CHANGES_REQUESTED` dev fix is dispatched here but relabels to
  `workflow:fixing` BEFORE the spawn and records `stage="fixing"` analytics, so the dev-fix subphase reads as fixing
  rather than validating on both the wire label and the analytics row), `_handle_fixing` (in_review-route PR-feedback
  resume + validating-route awaiting-human rescan), `_handle_resolving_conflict` (conflict resume + awaiting-human
  resume). Session: locked per issue after first spawn.
- **Reviewer** (`REVIEW_AGENT`, default `codex`) — spawned by `_handle_validating` (fresh every round). Session: fresh
  per round; current config always wins.

The defaults (`claude` decomposes, `claude` implements, `codex` reviews) use both backends; both CLIs need to be
authenticated on the host before the orchestrator starts.

Every stage handler lives on responsibility-named owners under `orchestrator/workflow/stages/`, which own entry
checks, session execution, drift handling, persistence, and terminal routing (see the module map in
[`architecture.md#top-level-layout`](architecture.md#top-level-layout)). Every handler is reached on the owner that
defines it; `orchestrator.workflow` publishes six names and nothing else — `WorkflowLabel`, `ControlLabel`,
`guard_transition`, `is_allowed_transition`, `IllegalTransition`, and `tick`.
Between owners the caller names the owner it borrows — documenting, validating, in_review, fixing, and
conflicts all
reach the implementing dev resume, documenting, validating, and conflicts also its question / dirty-tree parks,
documenting and validating its session read and fixing its poisoned-session drop, documenting reaches validating's
watermark walk, in_review and conflicts its body-edit disposition, and
fixing its dev-fix disposition, stranded-fix probe, and transient-park recovery plus in_review's comment timestamp;
decomposition reaches the implementing handler for a `single` verdict and its retry budget for a fresh decomposer
spawn; and implementing, validating, in_review, conflicts, documenting, and fixing all name base-sync's auto-rebase
park reasons on `git/base_sync/state.py` —
so a patch meant to intercept one of those has to land on the owner. The git a stage runs on is named the same way:
the worktree, HEAD, fetch, push, and PR-title helpers live on owners under `orchestrator/git/`, and the tracked spawn
every role goes through dispatches on `orchestrator/agents/runner.py`. All nine stages live under
`orchestrator/workflow/stages/`: the `decomposing` / `ready` / `blocked` / `umbrella` handlers on owners in
`orchestrator/workflow/stages/decomposition/`, `_handle_implementing` on owners in
`orchestrator/workflow/stages/implementing/`, `_handle_documenting` in `orchestrator/workflow/stages/documenting/`,
`_handle_validating` in `orchestrator/workflow/stages/validating/`, `_handle_in_review` in
`orchestrator/workflow/stages/in_review/`, `_handle_fixing` in `orchestrator/workflow/stages/fixing/`,
`_handle_resolving_conflict` in `orchestrator/workflow/stages/conflicts/`, `_handle_question` in
`orchestrator/workflow/stages/question/`, and `_handle_discussion` on owners in
`orchestrator/workflow/stages/discussion/`. Nothing answers for a stage beside those owners, so each handler is
reached on the one module that holds it, and the dispatcher and the same-tick pickup start name that module directly.
The per-stage behavior is documented in [`state-machine.md#stage-handlers`](state-machine.md#stage-handlers). What
follows is the role-specific glue.

- **Dev session reuse.** The implementer session is spawned once in `_handle_implementing` and then resumed by
  `_handle_documenting`, `_handle_validating`, `_handle_fixing`, and `_handle_resolving_conflict` whenever they need the
  dev to make a change. The locked `(backend, args)` spec is re-parsed on every resume from pinned `dev_agent` so a
  config flip mid-flight cannot retarget the session. `_resume_dev_with_text` on
  `workflow/stages/implementing/resume.py` is the one module every one of those resumes goes through; it declares the
  call signature its callers were written against, then binds those arguments into a typed request/context before
  executing the resume.
- **Reviewer freshness.** `_handle_validating` spawns a fresh reviewer subprocess every round with no resume, so
  `REVIEW_AGENT` changes take effect on the next validating tick. The current value is recorded in `review_agent` for
  traceability only.
- **Decomposer reuse.** `_handle_decomposing` spawns the decomposer once and resumes it on every awaiting-human reply.
  The `question` stage reads `DECOMPOSE_AGENT` only as the *fallback* on the first-ever question spawn, then pins what
  it ran under to `question_agent` (a separate key) so a multi-turn Q&A keeps its own lock independent of any
  decomposing session on the same issue. The `discussion` stage borrows the same role on the same terms and pins to
  `discussion_agent` + `discussion_session_id`, a third independent pair, and resumes that session on every human
  reply — so the pin protects both which backend and args a later round runs under and the conversation it continues,
  since a session id is only meaningful to the CLI that issued it.

### Question stage — read-only Q&A on the `question` label

The `question` workflow label is operator-applied: there are no automatic transitions in or out. `_handle_question` runs
the configured `DECOMPOSE_AGENT` backend in the issue's per-issue worktree (recreated from `<remote>/<base>` each spawn)
with a read-only prompt that forbids modifying, committing, or pushing files. The agent's answer (or its own clarifying
follow-up question) is posted as a comment pinging `HITL_HANDLE`; no PR is opened. Subsequent human replies resume the
locked session, so a multi-turn Q&A keeps the same backend + args.

A read-only violation (commits, dirty tree, timeout) parks awaiting human AND preserves the worktree for operator
inspection; the per-tick base sync is skipped while the label is `question` so `<remote>/<base>` is not merged over that
inspection state. Closing the issue is the terminal signal: the closed-`question` sweep flips the issue to `done` and
tears down the worktree.

For the per-`park_reason` semantics and the implementing-side relabel guard
(`read_only_relabel`, which answers for the `discussion` stage's parks too), see
[`state-machine.md#_handle_question-label-question`](state-machine.md#_handle_question-label-question).

### Discussion stage — architecture discussion on the `discussion` label

The `discussion` label is operator-applied like `question`: nothing routes an issue in, and the only transitions out
the orchestrator makes for itself are the two terminals it drains once the humans have decided somewhere it can read
— the verdict they leave on the plan PR below, and a close of the issue before one exists. It reuses the
decomposer's configured backend — a discussion is the decomposer reasoning about a design before anything is
decomposed. `_handle_discussion` runs it once in the issue's per-issue worktree (`issue-N`, on the issue's own branch)
with a prompt that tells it to research the repository itself, explore the design as a tree rather than a single
answer, raise architecture decisions, unconventional alternatives, and worthwhile research rather than implementation
trivia, and close with a NUMBERED list of the questions answerable right now — each with the agent's own recommended
answer — so a human can agree or overrule by number. Nothing is written, and nothing is implemented, until a human
states on the thread that they and the agent understand the design the same way.

Where the two stages part is what a round may leave behind. `question` is read-only for its whole life — a commit or
a dirty tree is a violation it parks on — it opens no PR, it tears its worktree down on every safe exit, and closing
the issue finishes it `done`. A discussion is read-only only up to the confirmation: after it the agent may commit
exactly one file, the stage publishes that file as a pull request, the `issue-N` checkout is preserved on every round
exit instead, and the ending is the verdict the humans leave on that pull request — merged is `done`, closed unmerged
is `rejected` — with a close of the issue before a plan exists the only other ending the stage takes for itself.

Answering by number resumes the pinned session for another round. Only issue comments past the consumed
`last_action_comment_id` that are neither from an untrusted author nor the orchestrator's own count as an answer, so
an empty or all-untrusted batch is a no-op that writes nothing and leaves the reply for the tick after the allowlist
changes. The resume quotes those replies to the live session
(`_build_discussion_followup_prompt`) and asks for the tree redrawn around what they settled and the frontier
recomputed, then parks again — as many rounds as the humans keep replying. A round with no `discussion_session_id` to
resume gets the full prompt instead, since it reaches a fresh agent that would otherwise arrive with no design to
fold an answer into; a round that was not itself a resume records the absence of an id as well as the presence of one,
so a stale pin cannot outlive the conversation it belonged to. That rebuilt context keeps the orchestrator's own
posted analyses even when `ALLOWED_ISSUE_AUTHORS` does not list the bot's account, so the fresh agent reads the
human's answers together with the numbered questions they answer.

Each round consumes exactly what its own prompt read, so a comment posted while the agent was running survives to
earn the next round instead of being stamped past by the park. The `issue-N` worktree is reused rather than rebuilt
across the whole conversation, and a reply arriving into a checkout that has moved off the round anchor or is holding
edits opens no round on it: reported once with the paths and the reset command when nothing on the thread had said
so yet, held in silence when the standing park already did. The answer stays unconsumed through both, so resetting
the tree is the whole of what the operator has to do.

The run is recorded under `agent_role="decomposer"` with `stage="discussion"`. Two records are written BEFORE the
spawn: `discussion_agent`, so the conversation's identity survives a CLI that hands back nothing and a replayed round
stays on the backend that opened it rather than on whatever `DECOMPOSE_AGENT` says now, and
`discussion_round_branch` + `discussion_round_sha`, the branch the round opened on and the SHA it was at. That pair
is the crash-recovery anchor — a round can end with no disposition at all (a mid-run `paused` withholds every one by
contract, a crash takes them with it) and the next tick reuses the same checkout, so without the anchor a commit the
ended round made would become the new round's baseline and read as work the branch arrived carrying.

No park withdraws it, including the two that report a commit. On a parked issue the same pair is what the
implementing relabel guard reads — a branch still at that SHA carries only what the issue arrived with — which is how
a discussion held on a branch that already had its dev's commits is relabeled without being accused of them, and how
one that *was* committed to gets back: the park names that SHA as the reset target, and resetting to it drops the
agent's commit while leaving the PR's underneath. Resetting to base or deleting the branch would take the PR with it,
so the anchor is what makes a non-destructive recovery exist at all. The successful relabel is what finally clears
the pair. `discussion_session_id` rides the park's write instead, so it never outlives the analysis it points at.

The clean response is posted as a comment pinging `HITL_HANDLE` and the issue parks awaiting human; the worktree is
preserved on every round exit — only the plan PR reaching a terminal ever reaps one — and the per-tick base sync skips
the `discussion` label as it does `question`, so nothing rebases `<remote>/<base>` over it. No developer or reviewer
is ever spawned. A parked issue's next tick costs one comment read and nothing else until somebody answers — the round
on the thread is the humans' turn. A relabel to `workflow:implementing` goes through the same read-only guard the
question stage uses, so a park that left unpublished commits or edits is refused as `discussion_unsafe_relabel` rather
than pushed as dev work. See
[`state-machine.md#_handle_discussion-label-discussion`](state-machine.md#_handle_discussion-label-discussion).

#### The plan PR the confirmation earns

Both prompts also carry the one write the confirmation unlocks: `plans/issue-<number>.md`, holding the resolved
decisions, the evidence and research behind them, the alternatives and why they lost, the risks, and the
implementation plan — committed alone, with no push and no PR of the agent's own. The path is spelled by the stage's
own key owner and handed to the prompt builders, so what the agent is told and what the check looks for cannot drift.

The check is what publication turns on, since no orchestrator can verify that a human agreed to anything: a round that
moved HEAD has its branch read once, by four probes, and every one has to answer. The worktree status has to have been
read and be clean — an unreadable tree is not a clean one, and a corrupt index fails `git status` while a
commit-to-commit diff still succeeds. The paths its commits change have to be exactly the plan path — measured
against the base commit the round pinned before it spawned, not against `<remote>/<base>`: the per-issue checkout is a
linked worktree sharing the clone's refs, so an agent can commit code, repoint that ref onto the code commit, and
commit the plan, leaving a ref-relative diff that names one path while the push carries two commits. And the plan has
to be in HEAD as a regular file, because deleting a file the base branch carries changes exactly the path writing it
would — and a symlink or a submodule pointer left at that path resolves there while carrying no document to read.
A missing plan, a deleted one, a second one, a code or configuration change, edits left loose, a
tree that could not be inspected, or a round whose base was never recorded park `discussion_plan_invalid` with the
offending paths and the anchor to reset to, and push nothing. A valid one is pushed through the same hardened
`_push_branch` every stage uses, with the lease pinned to a tip the remote was just read at and that this commit
contains — a branch the remote lacks, or an ancestor of the plan commit; anything else parks
`discussion_push_failed` (after the in-flight marker, so the reply that retries it has a publication to reach) rather
than sending an older commit over somebody's push or over history the branch was reset off. Its PR is
found-or-opened so a tick
that died between `open_pr` and the pinned write
recovers into a reuse rather than a duplicate, and the PR body names the decomposer session that wrote the plan
without any closing keyword: what a merge meant is the stage's own terminal to record, and the keyword outlives the
label it was written under, so on a PR a relabel hands to a developer it would let a merge of the plan alone close the
issue as finished work. What the body says instead is what deciding it does — merging finishes the issue `done`,
closing it unmerged finishes it `rejected`, and having the plan built is a relabel made before either.
A reused PR is only known to be open
on the branch — as is one ADOPTED for already carrying the plan commit, which is what a crash before `pr_number` was
written leaves the recovery to find, and which the lookup proves nothing about the provenance of — so one whose body
does not already name that session has it rewritten; one that does keeps whatever else it says. A failed push parks
`discussion_push_failed` with the commit intact. The marker's write is also what supersedes a standing
`discussion_push_failed` with `discussion_publishing`, since it spends the reply that asked for the retry: left as it
was, a crash right after it would leave a publication the recovery refuses to resume and no unread answer to resume it
with.

Every one of those readings names the tip that was read first rather than asking `HEAD` again, and so does the push,
since each is a separate git invocation and a branch that moves between them would publish work no check ever saw.
It is also handed a session to name: `discussion_session_id` is pinned before a resumed round spawns and recorded
from what a fresh one opens, and a plan whose round left neither parks `discussion_plan_unattributed` rather than
going out under a body that cannot say which conversation produced it.

Publication writes twice. `discussion_publishing_sha` goes first and alone, naming the tip about to be pushed, because
everything after it can change the world: it is what lets a later tick tell a commit this stage began publishing from
one that merely looks like a plan. It is also what says where to rebuild a checkout that has gone: `pr_number` is
written after the PR is open, so between the two writes only the marker knows the branch may already be pushed, and a
tick that rebuilt it from the base branch instead would refuse the publication for a tip it cannot find and open
another round over the top of the PR. While it stands, the remote is asked whether the branch is there — restored
from if it is, rebuilt from base if the push never landed. `discussion_base_sha` rides the pre-spawn write beside the
anchor:
it is what the remote said the base branch was at, read through the token before the agent could touch anything, and
it is persisted rather than re-read so a later tick recovering the round measures against the base that round was
given. It is also an id this clone can read, not just one the remote named: the base advances between the tick's own
fetch and the round that opens in it, and a local diff naming an absent commit fails and reports no paths — which is
how a plan written exactly as asked gets refused for changing nothing. One authenticated fetch of the base supplies a
missing object, and a base still unreadable after it is recorded as none.
Under a park, the publishing marker and `discussion_round_open` — written beside the anchor
before every spawn and cleared by every park, and by the adoption that records an already-decided pull request
without one — are the only two things that attribute a commit to this stage: the
first is finished on its own if a tick died mid-publication (that tick's write already spent the reply that would
otherwise carry the next one there) and on the reply itself when the push is what failed — a reply that retry then
consumes, or a failure would be asked for again by the same comment every poll; the second covers a resumed
round that committed the confirmed plan and was paused or cut short before it could report, which is judged exactly as
the same crash on an unparked issue is. The marker is asked first and answers for the branch either way: a tip it does
not name parks `discussion_stale_publication` rather than being read as the round's, and is spent only by the next
round opening or by the branch going back to the round's anchor over a remote that no longer carries the commit it
names — the push sends the SHA it validated rather than `HEAD`, so a local ref that never moved says nothing about
whether the plan went out. Anything neither record accounts for is reported as the
commit it is, so neither a stray session's plan-shaped commit nor a human's rejection of the design can publish one.

The second write is the park's, and it
carries `discussion_plan_path`, `branch`, `pr_number`, `discussion_plan_sha` (the two records implementing tells a
design from a build by, so its merged-PR terminal does not read a plan being agreed to as work having landed: the path
answers while it stands, whatever the humans' own edits did to that PR's head, and the commit answers past the handoff
that retires it — which is why that handoff re-reads the PR and records the head it is on THEN, and brings the
developer's checkout onto it, rather than leaving the developer on a design its reviewers have moved past), the
round anchor moved onto the published tip, and the retired
marker, alongside the `pr_opened` event emitted with `stage="discussion"`. The label stays `discussion` —
no `validating`, no `documenting`, no `in_review` — and every later tick with that record polls that PR before
anything else: no agent and no round whatever it says. While it is open the tick writes nothing at all and keeps the
checkout and both branches, since they are what the humans are reading the plan on. Merged, the design was taken and
the issue finalizes to `done`; closed without merging, it was turned down and finalizes to `rejected`. Either way the
shared terminal tail runs under `stage="discussion"` — the timestamp, the label, the cumulative usage receipt posted
before the single pinned write, the `pr_merged` / `pr_closed_without_merge` event, the issue close — and only then
does `_cleanup_terminal_branch` take the worktree and the local and remote branches, which is the one thing that ever
tears a discussion checkout down.

A human closing the issue is a terminal too, and `discussion` is in the closed-issue sweep so a closed one keeps
being polled. With the plan PR still open, the close says nothing about the design: the stage keeps its label — which
is what leaves it inside that sweep — and its checkout until the PR itself resolves. With no plan PR at all there is
nothing to wait for, so the close finalizes to `rejected` outright, ahead of the publication recovery and every
turn-taking gate, and tears nothing down: the branch under it may carry an unpublished plan commit or belong to a PR
the issue merely arrived here holding.

"No plan PR" is decided by a lookup, not by the absence of a record, because the two come apart for one tick. The
publication opens its pull request before it writes the number down, so a tick that dies in between leaves a real one
with nothing pinned pointing at it — and a human can close the issue, or decide that pull request, inside the same
window. So a standing `discussion_publishing_sha` is looked up by its commit across every state first: a merged or
closed one finalizes the issue there and then, an open one holds it exactly as a recorded open one does, and only
"nothing carries that commit" reaches the pre-PR ending. The publication side of the same window refuses to push at a
pull request the humans have decided, for the same reason from the other end — a push there would open a REPLACEMENT
proposing the design they just turned down.

Moving the anchor is what lets the operator relabel to `workflow:implementing` before any of that: the guard
measures the branch against it, so an anchor left behind would convict the branch of the commit this stage just
published.

The plan is an artifact, not a specification anything downstream reads. Nothing in the workflow parses it: the
relabel spawns the developer with the ordinary `_build_implement_prompt` built from the issue body and the trusted
thread, on the branch the plan PR is open against, and the final-docs pass that follows is told not to inspect or
modify the `plans/` tree at all. So the plan file rides along on the branch and lands with the implementation as the
human-readable record of what was agreed — the issue is still what the developer is briefed from and judged against.

### Tracked-repos awareness in working-agent prompts

When the orchestrator drives more than one repo (`REPOS`) and `EXPOSE_TRACKED_REPOS` is on (the default), the
reasoning-prompt builders prepend a compact, read-only awareness block naming the *other* repos this process tracks. It
lets an agent implementing an issue in one repo know that a sibling repo is also monitored and where its source is
checked out locally. The block is built once by `_build_tracked_repos_context(current, specs)` in
`workflow/engine/comments.py` from `config.default_repo_specs()` — no GitHub round-trip, no pinned state, no new
config surface.

Shape of the block:

- One line per *other* repo (`- owner/name — source at <target_root> (base <base>)`), excluding the current repo, with
  a closing `Your task is on owner/name.` marker. The list is capped at 20 entries with an `… and N more` overflow
  line so a host driving dozens of repos cannot blow the prompt.
- Only the durable `target_root` checkout is exposed — never the ephemeral per-issue `issue-N` worktrees. No tokens,
  no remote URLs — see [`security.md`](security.md#cross-repo-awareness-disclosure-expose_tracked_repos) for the full
  disclosure analysis.
- The framing is deliberately **stage-neutral**: it says only that the sibling checkouts are read-only references and
  explicitly defers the question of whether the agent may write in its *own* working directory to the surrounding stage
  prompt. So the same block is safe in the write-granting prompts (implementer / documentation), in the read-only ones
  (reviewer / decomposer / question), and in the discussion prompts, whose single write a human's confirmation
  unlocks — none of them widens what the surrounding prompt granted.

Which prompts carry it (every builder below lives in `workflow/engine/prompts.py`):

- **Embedded** in `_build_implement_prompt`, `_build_documentation_prompt`, `_build_review_prompt`,
  `_build_decompose_prompt`, `_build_question_prompt`, `_build_discussion_prompt`, and
  `_build_fresh_respawn_preamble`. The fresh-respawn preamble
  matters because a transcript-less respawn (proactive `DEV_SESSION_MAX_RESUMES` rotation, the consecutive-silent-park
  fallback, poisoned-session recovery, or an operator `/orchestrator continue` command that drops a session-failure
  park's poisoned dev session before replaying the preserved PR-feedback batch) never saw the original spawn's block, so
  the re-grounding text must re-feed it alongside the issue body and conversation.
- **Omitted** from the bare resume / followup builders (`_build_fix_prompt`, `_build_conflict_resolution_prompt`,
  `_build_pr_comment_followup`, `_build_question_followup_prompt`, `_build_discussion_followup_prompt`): those text
  payloads resume a live session that
  already received the block at spawn time, so repeating it would only burn tokens.

The default single-repo deployment (or any host with `EXPOSE_TRACKED_REPOS=off`) gets an empty string here — **zero
added prompt tokens and zero behavior change**. See [`configuration.md#agent-roles`](configuration.md#agent-roles) for
the env var.

### Local verify gate (not an agent)

After the reviewer emits `VERDICT: APPROVED`, `_handle_validating` runs the configured `VERIFY_COMMANDS` directly in
the per-issue worktree — these are plain shell commands, not an agent role, so no `*_AGENT` env var applies. The gate
runs before the approval comment, the squash, the watermark seeding, and the `workflow:documenting` (final-docs) label
flip. A clean run advances the issue; any failure parks on `workflow:validating` with a typed `park_reason`
(`verify_failed` / `verify_timeout` / `verify_dirty` / `verify_head_changed`). See
[`configuration.md#local-verification-gate`](configuration.md#local-verification-gate) for the env-var reference.

## Spec format

`config._parse_agent_spec` runs `shlex.split` over each role's env value and yields `(backend, extra_args)`:

- **First token rule** — must match `codex` or `claude` case-insensitively (`_parse_agent_spec` compares
  `tokens[0].lower()`, so `CODEX`, `Claude`, and `codex` all parse to the same backend). The lowercased form is used
  only for dispatch (`agents.run_agent` keys off it).

  Pinned state stores the **raw spec string verbatim** with its original casing — `DEV_AGENT=CODEX -m gpt-5.5` is
  persisted as the literal `"CODEX -m gpt-5.5"`, and the re-lowercase happens again on every resume when
  `_parse_agent_spec` re-parses the stored value.

  Anything else (full path, alias, typo, empty string, unbalanced quotes) aborts at import with a `SystemExit` so a
  misconfiguration cannot silently fall back to a default backend on the next restart. `DECOMPOSE_AGENT` is parsed at
  import even when `DECOMPOSE=off`, so toggling the kill switch back on never surfaces a fresh "that env var was always
  invalid" failure.
- **Remaining tokens** — forwarded verbatim as backend-CLI args on every spawn for that role. Quoting follows shell
  rules, so values containing `=`, spaces, or nested quotes survive (e.g.
  `codex -m gpt-5.5 -c 'model_reasoning_effort="xhigh"'`).

  For codex the args are placed before the `exec` subcommand (they are codex global options); for claude they are placed
  right after the binary, before the orchestrator's own `-p` / `--dangerously-skip-permissions` / `--output-format`
  flags. The safety/output flags and the prompt stay where they are so operator args cannot silently displace them.
- **`CODEX_BIN` / `CLAUDE_BIN` interaction** — the first token is only a backend selector. It picks the codex vs.
  stable API in `agents/`; command construction lives in `agents/backends/codex.py` and `agents/backends/claude.py`, and
  session / final-message parsing in `agents/sessions.py`. The actual executable launched is `CODEX_BIN` when the
  first token is `codex` and `CLAUDE_BIN` when it is `claude`. Set those to a full path when the CLI is not on
  `$PATH`. Writing a full path as the first token
  of `DEV_AGENT` / `REVIEW_AGENT` / `DECOMPOSE_AGENT` is rejected (it would not match `codex` / `claude`).

### Examples

Both backends accept model selection plus a reasoning-effort flag. Any of the lines below is a valid value for any of
the three role env vars.

```dotenv
# bare backends (defaults)
DEV_AGENT=claude
REVIEW_AGENT=codex
DECOMPOSE_AGENT=claude

# claude with model selection
DEV_AGENT=claude --model claude-opus-4-7
REVIEW_AGENT=claude --model claude-sonnet-4-6

# claude with model + effort
DEV_AGENT=claude --model claude-opus-4-7 --effort high
DECOMPOSE_AGENT=claude --model claude-opus-4-7 --effort medium

# codex with model + reasoning effort
DEV_AGENT=codex -m gpt-5.5 -c 'model_reasoning_effort="xhigh"'
REVIEW_AGENT=codex -m gpt-5.5-codex -c 'model_reasoning_effort="high"'
```

## In-flight session lock — pinned full spec until the session ends

The parsed spec is persisted to pinned state as the **durable role identity** for an issue. The point of pinning the
full spec (backend AND args, not just the backend) is that the orchestrator can resume mid-flight without losing the
model / reasoning-effort the session was started with — a `DEV_AGENT` flip between ticks cannot silently retarget the
next resume at a different backend, and it cannot silently drop the args either.

How it works per role:

- **Implementer (`DEV_AGENT`).** `_handle_implementing` writes the current spec verbatim to `dev_agent` (e.g.
  `"codex -m gpt-5.5 -c 'model_reasoning_effort=\"xhigh\"'"`) BEFORE invoking `run_agent`. The write happens
  unconditionally on every fresh spawn, so a backend hiccup that produces commits without surfacing a session id (empty
  codex `-o` file, unparseable claude JSONL line) still anchors the role for the next tick.

  On a resume, `_read_dev_session` re-parses `dev_agent` via `config._parse_agent_spec` to recover `(backend,
  extra_args)` and passes the args through to `run_agent`. `_handle_documenting`, `_handle_validating`,
  `_handle_fixing`, and `_handle_resolving_conflict` all resume the dev session via the same path, so the locked spec
  applies to every dev-side resume for the lifetime of the issue. `_handle_in_review` does not resume the dev itself —
  fresh PR feedback routes the issue to `workflow:fixing` instead.
- **Decomposer (`DECOMPOSE_AGENT`).** Same mechanic in `_handle_decomposing`: the spec is persisted to
  `decomposer_agent` before the spawn and re-parsed via `_read_decomposer_session` on every resume. The same backend
  (not the same session) also drives the question stage — `_handle_question` reads `DECOMPOSE_AGENT_SPEC` as the
  *fallback* on the first-ever question spawn, then pins what it ran under to `question_agent` (a separate key, parsed
  by `_read_question_session`).
- **Reviewer (`REVIEW_AGENT`).** Spawned **fresh every round** by `_handle_validating`, so changes to `REVIEW_AGENT`
  take effect on the next validating tick (no migration step needed). The current value is recorded in `review_agent`
  for traceability only; it is not used for resumes.

**Net effect:** flipping `DEV_AGENT` or `DECOMPOSE_AGENT` in env only affects fresh issues. Any issue with a live
session keeps the original backend AND args until it reaches a terminal label (`done` / `rejected`); only then will a
config change apply to a follow-up issue. Flipping `REVIEW_AGENT` takes effect on the next round of any issue in
`workflow:validating`.

### Backward compatibility

- Legacy bare-backend values written before the spec rewrite (`"codex"` / `"claude"` in `dev_agent` /
  `decomposer_agent`) round-trip to `(backend, ())` — no args, matching what those deployments had at the time.
  Persisting them again is a no-op rewrite.
- The pre-spec key `codex_session_id` (written before `dev_agent` existed) is still honored on read and yields
  `spec="codex"`. A config flip to claude cannot strand that session — it stays on codex with no args.

## Quick reference

- The spec format is parsed once at import (`config._parse_agent_spec`) and again at resume time from pinned state, so
  the same validation rules apply to both paths.
- `CODEX_BIN` / `CLAUDE_BIN` are the only knobs for the executable path; the spec's first token is a backend selector,
  not a path.
- The reviewer is fresh per round; the implementer and decomposer are pinned for the life of the issue session.
- For per-stage handler internals (worktree management, prompt construction, post-spawn branching) see
  [`state-machine.md#stage-handlers`](state-machine.md#stage-handlers).
