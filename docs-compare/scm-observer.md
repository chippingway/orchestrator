# GitHub workflow observation and control

Chipping Orchestrator polls GitHub, but its GitHub integration is not an observation-only SCM adapter. GitHub is the
workflow authority: labels route work, one authenticated pinned comment stores durable state, issue/PR comments carry
trusted input, and branches, checks, reviews, and merge state determine later transitions.

This page normalizes the behavior documented in [`../docs/architecture.md`](../docs/architecture.md),
[`../docs/state-machine.md`](../docs/state-machine.md), and [`../docs/workflow.md`](../docs/workflow.md).

## Per-tick flow

For each configured repository, a tick:

1. refreshes repository-level facts and performs the bounded closed-issue cleanup sweep when due;
2. lists issues eligible for orchestration and classifies them into family-serialized or per-issue work;
3. schedules only the repository slug and issue number;
4. creates a worker-local GitHub client and refetches the issue;
5. reads the current workflow label and authenticated state comment;
6. dispatches the fixed handler for that state; and
7. persists remote state before later effects whenever a workflow seam requires recovery evidence.

The long-lived scheduler enforces global and per-repository caps. Parent/child stages share a serialized family bucket;
ordinary issue stages can fan out.

## Observed and mutated GitHub objects

| Object | Read purpose | Write purpose |
|---|---|---|
| Issue labels | select the current stage and operator controls | advance, park, resume, or finalize workflow |
| Pinned state comment | recover schema-versioned session, retry, family, PR, and late-split facts | durably record the next recoverable state |
| Issue comments | consume trusted commands, answers, discussion turns, and retry input | post receipts, questions, parks, and human mentions |
| Branches and custom refs | prove remote heads, leases, snapshots, and cleanup preconditions | publish exact commits and late-split snapshots |
| Pull requests | find the active delivery surface and external terminal outcome | create/update PRs and supersede a PR after a split |
| Reviews, checks, and PR comments | detect fresh human or CI feedback | no automated approval or merge |

Pinned state is accepted only when the comment is state-only and authored by the authenticated orchestrator account.
Human input is separately restricted by the trusted-comment-author policy.

## Publication boundary

Agents modify and commit within per-issue worktrees, but do not receive the orchestrator GitHub token. Before a push,
the orchestrator proves the intended worktree/commit, freezes any required remote-head lease, and publishes an explicit
refspec through temporary askpass credentials and hardened Git configuration. Failed or unreadable proof parks the
issue; it is not converted into a permissive default.

The orchestrator never merges a PR. In `workflow:in_review`, a human merge advances the issue to `workflow:done`, a
human close without merge advances it to `workflow:rejected`, and fresh feedback routes it back to fixing.

## Identity and provider scope

Durable identities use GitHub-native coordinates such as repository slug, issue/PR number, comment id, branch/ref,
commit SHA, and snapshot generation. The documented implementation is GitHub-specific through PyGithub; it does not
claim a provider-neutral GitHub/GitLab observer contract.

## Polling and failure semantics

The main cadence is `POLL_INTERVAL` (60 seconds by default). Rate-limit-aware behavior and a bounded closed-issue sweep
reduce unnecessary calls. Network errors, malformed state, ambiguous refs, and unsafe git observations are surfaced or
parked conservatively. Observability JSONL and analytics stores are never consulted to repair or steer workflow state.

## Architectural distinction

There is no separate semantic-delta observer that writes an internal change feed. The polling handlers both observe
GitHub and perform workflow mutations. GitHub labels plus authenticated pinned state—not a local database—are the
durable dispatch boundary.

