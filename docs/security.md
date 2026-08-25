# Security checklist and operator-owned controls

This page maps the project security checklist to the `agent-orchestrator` repo: what the repo files already enforce and
what is **operator-owned** (GitHub or org settings that no file in the repo can set).

The orchestrator gives `codex` / `claude` CLI subprocesses sandbox-bypass flags on the host, so the host is the real
trust boundary — see [`architecture.md`](architecture.md#design-constraints).

## Checklist mapping

- **Required human reviews for dependency changes** — operator-owned. Branch protection + `CODEOWNERS`. See
  [Required human reviews for dependency-touching changes](#required-human-reviews-for-dependency-touching-changes).
- **Vulnerability reporting channel** — in repo + operator-owned to switch on. [`../SECURITY.md`](../SECURITY.md) is
  the external-facing policy: report privately through GitHub Private Vulnerability Reporting, never as a public
  issue, which on this repository is also an agent-workflow input. See
  [Private vulnerability reporting](#private-vulnerability-reporting).
- **Automated dependency vulnerability scan** — in repo + operator-owned to enforce. Two complementary scans.
  [`../.github/workflows/dependency-review.yml`](../.github/workflows/dependency-review.yml) gates what a PR
  *changes*, on every PR (see [Required checks](#required-checks));
  [`../.github/workflows/vulnerability-scan.yml`](../.github/workflows/vulnerability-scan.yml) audits every pin in
  [`../uv.lock`](../uv.lock) weekly and on demand
  ([`configuration.md#continuous-integration`](configuration.md#continuous-integration)). The standing scan is what
  sees an advisory published against a version nobody is touching — a diff gate never looks at it again after the pin
  lands. It runs on a schedule rather than on a PR, so it cannot be a required check; enabling
  [Dependabot security updates](#dependabot-security-updates) is what turns one of its findings into a patch PR.
- **Static analysis of the code itself** — in repo + operator-owned to enforce.
  [`../.github/workflows/codeql.yml`](../.github/workflows/codeql.yml) runs CodeQL advanced setup for Python; a ruleset
  decides which findings block a merge. See [CodeQL advanced setup](#codeql-advanced-setup).
- **2FA for all maintainers** — operator-owned. See [2FA](#2fa).
- **Secret scanning + push protection** — operator-owned. See
  [Secret scanning and push protection](#secret-scanning-and-push-protection).
- **`main` (and any release branch) protected, no force-push** — operator-owned. See
  [Branch protection](#branch-protection).
- **Required status checks** — operator-owned. See [Required checks](#required-checks).
- **Fork PRs cannot read repository secrets** — in repo + operator-owned. Every workflow declares
  `permissions: contents: read` at the top level and references no secrets
  ([`configuration.md#continuous-integration`](configuration.md#continuous-integration)). See
  [Fork-PR secret policy](#fork-pr-secret-policy).
- **No CI publishing / deploys unless run on a protected ref** — N/A today, policy below. No package-publishing or
  deploy workflow exists yet; see
  [No CI publishing / deploys outside protected refs](#no-ci-publishing--deploys-outside-protected-refs)
  before adding one.
- **Backup / restore drills** — operator-owned. See [Backup and restore drills](#backup-and-restore-drills).
- **Review / tests / scans for AI-generated code** — in repo. See
  [AI-generated code review, tests, and scans](#ai-generated-code-review-tests-and-scans).
- **Package-registry hygiene (lockfiles, registry pinning)** — in repo. Runtime deps (`PyGithub`, `psycopg[binary]`)
  are declared in [`../pyproject.toml`](../pyproject.toml); exact versions are pinned in [`../uv.lock`](../uv.lock); CI
  installs via `uv sync --locked`
  ([`configuration.md#continuous-integration`](configuration.md#continuous-integration)). Dependabot covers the `uv`
  and `github-actions` ecosystems in [`../.github/dependabot.yml`](../.github/dependabot.yml), stamping every update PR
  it opens with `workflow:dependencies` plus `workflow:github_actions` or `workflow:python:uv`, so the queue a
  maintainer has to triage is one label filter. For routine version updates, `github-actions` uses its supported
  ecosystem-wide window to hold every release for 30 days; `uv` holds a major or unclassified release for 30 days and
  a minor or patch for 14 days. These cooldowns do not delay security updates. Dependabot allows only direct
  dependencies by default, so a transitive package is in scope only once the `uv` entry's `allow:` rules name it:
  `gitpython` is named there because GitPython reaches the lockfile through Streamlit, and its advisories would
  otherwise leave the grouped security job with nothing it is allowed to update. An advisory against any other
  transitive dependency needs its own rule added before a PR can open for it
  ([`configuration/operations.md#continuous-integration`](configuration/operations.md#continuous-integration)).
- **Actions pinned to immutable commit SHAs** — in repo. Every `uses:` in
  [`../.github/workflows/`](../.github/workflows/) names a full 40-character commit SHA with the release it belongs to
  in a trailing comment, so a retagged release cannot change what a run executes; Dependabot's `github-actions` updates
  rewrite the SHA and that comment together
  ([`configuration.md#continuous-integration`](configuration.md#continuous-integration)).
  [`../tests/repository/test_workflow_action_pins.py`](../tests/repository/test_workflow_action_pins.py) fails the
  suite on a `uses:` that names a tag instead.
- **Continuous supply-chain grading (OpenSSF Scorecard)** — in repo.
  [`../.github/workflows/scorecard.yml`](../.github/workflows/scorecard.yml) grades this repo's supply-chain posture
  weekly, on every push to `main`, and on demand, publishing the results the README badge and the public viewer read
  and uploading the SARIF to code scanning, where the findings become the repo's own alerts
  ([`configuration.md#continuous-integration`](configuration.md#continuous-integration)).

## Operator-owned controls (GitHub / org settings)

The items below cannot be enforced by files inside this repo — an operator must configure them once on GitHub. Walk
this list when bootstrapping a fork, an org migration, or a new release branch.

### 2FA

- Require 2FA for every maintainer's GitHub account.
- For org-owned repos, enable **"Require two-factor authentication for everyone in your organization"** at
  `https://github.com/organizations/<org>/settings/security`. Members without 2FA are removed when this is turned on.
- Prefer hardware security keys (WebAuthn) or a TOTP app over SMS.

### Secret scanning and push protection

Enable both at `Settings → Code security`:

- **Secret scanning** — alerts on tokens found in the repo's history.
- **Push protection** — blocks pushes that introduce a detected secret pattern. The orchestrator never reads
  `GITHUB_TOKEN` from `.env` ([`.env.example`](../.env.example)), so push protection is defense-in-depth against an
  accidental paste.

On org-owned repos, set the same defaults at the org level.

### Private vulnerability reporting

Enable **Private vulnerability reporting** at `Settings → Code security`.

[`../SECURITY.md`](../SECURITY.md) is the reporting policy this repository publishes, and it sends a reporter to the
Security tab's "Report a vulnerability" button — which exists only while the setting is on. With it off, the policy
names a channel that is not there, and the reporter's remaining options are a public issue (which this repository
feeds to coding agents as workflow input, so the report is acted on in the open before a fix exists) or no report at
all.

- The private advisory draft it opens carries the discussion, the temporary private fork the fix is written on, the
  CVE request, and the publication, so nothing about an unfixed vulnerability has to touch a public branch.
- It is a repository setting; org owners can turn it on for every repository at once from the org's
  `Settings → Code security`.

### Dependabot security updates

Enable **Dependabot alerts** and **Dependabot security updates** at `Settings → Code security`. These are a different
mechanism from the weekly version-update PRs [`../.github/dependabot.yml`](../.github/dependabot.yml) configures:
alerts fire when a published advisory matches a version pinned in [`../uv.lock`](../uv.lock), and security updates
open the PR that bumps that one dependency to the fixed version.

- **They are not subject to the cooldown windows** the `uv` entry declares — 30 days for a major, 14 for a minor or
  a patch. Those windows are there to let a routine version update age before a maintainer has to look at it; a
  security patch is the case where waiting is the cost, and the cooldown applies to version updates only.
- They are the acting half of the standing scan:
  [`../.github/workflows/vulnerability-scan.yml`](../.github/workflows/vulnerability-scan.yml) reports a vulnerable
  pin every week, but nothing inside this repository can open the bump PR that clears it. What such an update may
  bump is still bounded by the `uv` entry's `allow:` rules — direct dependencies plus `gitpython` — so a finding
  against any other transitive pin needs its own rule before a PR can open for it
  ([`configuration/operations.md#continuous-integration`](configuration/operations.md#continuous-integration)).
- Alerts are visible to maintainers only, so enabling them discloses nothing about an unpatched pin.

### CodeQL advanced setup

[`../.github/workflows/codeql.yml`](../.github/workflows/codeql.yml) is the CodeQL advanced setup. It is the one scan
here that reads the repository's own code rather than its dependencies.

- The workflow runs CodeQL's default queries for Python on pushes to `main`, pull requests targeting `main`, and a
  weekly schedule. Python uses `build-mode: none`, so the scan neither installs dependencies nor executes project
  code.
- The workflow declares `contents: read` at the top level. Its analysis job restates that grant and adds only
  `security-events: write` for the result upload; it reads no secrets. The checkout and CodeQL actions are SHA-pinned
  and covered by the same Dependabot and repository-test policy as every other workflow action.
- Findings land on the Security tab, and once the baseline is clean a merge can be made to wait on them — through a
  **ruleset**, not through the required-check list. At `Settings → Rules → Rulesets`, target `main` with the
  **Require code scanning results** rule, select **CodeQL** as the tool, and set the two alert thresholds ([GitHub
  docs](https://docs.github.com/en/code-security/how-tos/find-and-fix-code-vulnerabilities/manage-your-configuration/set-merge-protection)).
  There is no status check named `code-scanning` to require in [Required checks](#required-checks); typing one in
  would name a check nothing ever reports, which blocks every merge instead of gating on the analysis.
- If default setup is already active, GitHub rejects this workflow's CodeQL SARIF upload, so the run ends red. At
  `Settings → Code security → Code scanning`, switch CodeQL to advanced setup, then rerun the failed workflow.

### Branch protection

Add a branch-protection rule for `main` (and any release branch) at `Settings → Branches`:

- **Require a pull request before merging.** The orchestrator only ever opens PRs; humans click Merge
  ([`architecture.md`](architecture.md)).
- **Require status checks to pass before merging** — list the checks in [Required checks](#required-checks).
- **Require branches to be up to date before merging** — keeps the per-tick base-sync auto rebase +
  [`workflow:resolving_conflict`](state-machine/delivery-stages.md#_handle_resolving_conflict-label-workflowresolving_conflict)
  (for
  actual rebase conflicts) flow honest.
- **Do not allow force pushes.**
- **Do not allow deletions.**
- **Restrict who can push** to `main`. The restriction applies to every protected-branch update including PR merges
  (see [GitHub
  docs](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)).
  The allowlist is the small named set of maintainers permitted to merge or push break-glass fixes. The orchestrator's
  personal access token does **not** belong here — granting it direct-push access would only widen blast radius if the
  token leaked.

### The snapshot ref namespace

The late size gate preserves a superseded candidate under
`refs/orchestrator/late-split/issue-<n>/cycle-<c>/gen-<g>` — a **custom ref namespace**, deliberately outside
`refs/heads/` and `refs/tags/`. Three things follow for an operator:

- **It is not a branch.** Nothing in the branch protection above applies to it, and nothing about it is meant to:
  the ref is written once, verified, and later deleted by the orchestrator, and no pull request, review, or merge
  ever touches it. Ruleset authors adding a catch-all `refs/**` rule should exclude
  `refs/orchestrator/**`, or the orchestrator will be unable to preserve a candidate it is
  about to supersede — which parks the issue rather than losing the work, but blocks every split until the rule is
  fixed.
- **The token needs to write and read it.** The same personal access token that pushes issue branches creates,
  fetches, and deletes these refs. It needs no *additional* scope, but a ruleset or a token permission that permits
  `refs/heads/orchestrator/*` and nothing else will refuse them. Prove it before enabling the gate:
  [`configuration/snapshot-capability-check.md`](configuration/snapshot-capability-check.md) is the
  disposable-repository runbook, and a failure there blocks rollout rather than being answered by weakening a rule.
- **Nothing is ever overwritten, and only our own content is deleted.** Every write is lease-pinned: a create leases
  the ref as absent, and a ref already carrying a different commit is reported and left alone. A delete is leased at
  the commit the split *preserved* rather than at whatever a fresh read observes — leasing against the reading would
  delete a re-pointed ref as readily as ours, and this is the one operation whose blast radius is somebody else's
  content rather than a refused push. A snapshot ref outside the namespace — anything a hand-edited ledger entry
  could name — is refused before the remote is contacted at all, so this path can neither clobber nor delete a
  branch, a tag, or a pull-request ref. Being *in* the namespace is not enough to be deleted, either: the target has
  to equal the ref this issue's own identity mints, because every generation in a lineage names the same commit and
  a sibling's ref would otherwise pass both the namespace and the lease. The **branch** cleanup beside it is held to
  the same rule from the other direction: its target also comes off a ledger a human can edit, and it has to be one
  of the exact names this repository publishes this issue under — not merely inside `orchestrator/` with a matching
  `/issue-<n>` tail, which is also another repository's branch — so a hand-edited entry naming an unprotected
  default branch, or a neighbouring repository's work, deletes nothing and holds the umbrella open instead.

- **Agent-declared content may not carry a receipt of ours.** Every hidden marker this orchestrator writes — the
  pinned state comment, the split's forward-link and supersession notices, the marker a child issue is stamped with —
  starts with `<!--orchestrator-`, and each is a claim that a step already happened. Those claims are matched as
  substrings, because that is all a body or thread search can do, so text that merely quotes one is indistinguishable
  from one this orchestrator stamped. A split manifest whose declared title or body carries such a marker is refused
  before anything is created, and an issue a receipt lookup returns is checked for carrying exactly one receipt of
  that kind — otherwise one issue could be adopted as two children of the same split, each seeded with the other's
  scope. The comment-side check is the author one: a receipt on a thread counts only when this orchestrator wrote it.

The refs hold objects, so they hold *content*: a snapshot is a copy of a candidate that was never published. It
lives in the same repository under the same visibility as the branch it came from, and it is deleted once every
recorded direct consumer has ended — at the umbrella's own terminal, on the park a rejected or hand-closed child
earns that parent, or in the closed-owner cleanup sweep for an issue a human closed mid-cycle. A ref whose delete
the remote refuses holds that terminal open rather than being silently abandoned. It is not a place to put
anything the repository itself may not hold.

This host keeps its own copy under `refs/orchestrator/late-split-local/<repository>/…`, qualified so that two
configured repositories sharing one clone cannot read each other's, and it is taken down **first** — the remote ref
is not touched until this copy has provably gone, and a copy that cannot be proved gone refuses the whole
reclamation. That order is what lets a child read a surviving copy as "nothing has been reclaimed" without spending
a request, and it is only sound because the copy is read for the exact commit it carries: the ref store belongs to
the clone the agents' own worktrees share, so a name that merely resolves proves nothing about what is under it.
One consequence for an operator: deleting a snapshot ref on the remote by hand leaves this host's copy behind, and a
child on that host goes on working from it until the copy is deleted too.

### Required human reviews for dependency-touching changes

A PR that adds, removes, or pins a dependency — or that edits a workflow file pulling actions — should not merge on
green CI alone. The automated [Dependency Review scan](#required-checks) flags known-vulnerable versions; a human
reviewer covers license, maintainership, and supply-chain judgment calls the scanner cannot.

Two GitHub-side controls combine to enforce this:

1. **Branch protection — "Require approvals" ≥ 1** in the `main` branch-protection rule.
2. **`CODEOWNERS` for the dependency surface.** Add `.github/CODEOWNERS` listing the dependency-touching paths against
   the maintainer set, then enable **"Require review from Code Owners"** in the same rule. Recommended pattern set:

   ```
   /pyproject.toml          @<maintainer-handle>
   /uv.lock                 @<maintainer-handle>
   /.github/dependabot.yml  @<maintainer-handle>
   /.github/workflows/      @<maintainer-handle>
   ```

   Replace `@<maintainer-handle>` with the GitHub login(s) or team slug that should sign off. The right reviewer set
   varies by deployment (solo maintainer vs. team vs. org), so the orchestrator does not create or maintain this file.

### Required checks

Mark these checks **required** in the branch-protection rule (job names as they appear on the PR):

- `ci` from [`../.github/workflows/ci.yml`](../.github/workflows/ci.yml) — Ruff, WPS
  (`flake8 orchestrator tests --select=WPS`), and pytest with an informational coverage report on Python 3.12,
  installed from [`../uv.lock`](../uv.lock).
- `dependency-review` from [`../.github/workflows/dependency-review.yml`](../.github/workflows/dependency-review.yml)
  — fails when a PR introduces a vulnerable or non-compliant dep.

`ci` and `dependency-review` both run on `pull_request` and declare `permissions: contents: read`, so the
`GITHUB_TOKEN` minted for each run is read-only. Scorecard and the vulnerability scan belong on neither list, because
no pull-request event triggers either one, so neither reports a check a PR could wait on.
[`../.github/workflows/scorecard.yml`](../.github/workflows/scorecard.yml) reports what it finds as a code-scanning
alert rather than as a failing run
([`configuration.md#continuous-integration`](configuration.md#continuous-integration)), and
[`../.github/workflows/vulnerability-scan.yml`](../.github/workflows/vulnerability-scan.yml), triggered by `schedule`
/ `workflow_dispatch`, is watched on the Actions tab — a red run is triaged there rather than by a blocked merge.

CodeQL is the one scan off this list that can still hold a merge, and it does so beside the list rather than on it:
its results are enforced by the **Require code scanning results** ruleset rule with CodeQL selected, which is a
separate mechanism from the required-status-check names above. See [CodeQL advanced setup](#codeql-advanced-setup).

### Fork-PR secret policy

- Workflows already use no secrets, and `contents: read` is the top-level grant in each of them. The Scorecard job's
  `security-events: write` + `id-token: write` elevation is on a workflow no pull-request event triggers. The CodeQL
  analysis job adds `security-events: write` and does run on `pull_request`; GitHub downgrades a fork PR token to read
  only but still accepts code-scanning uploads from the `pull_request` event. Do **not** enable write tokens for fork
  PRs or add `pull_request_target` triggers, `secrets.*` references, or higher token permissions without a written
  justification.
- At `Settings → Actions → General → Fork pull request workflows from outside collaborators`, set **"Require
  approval for first-time contributors who are new to GitHub"** (or stricter).
- For org-owned repos, mirror this default at the org level.

### No CI publishing / deploys outside protected refs

No package-publishing or deploy workflow exists in [`../.github/workflows/`](../.github/workflows/) today. The
Scorecard workflow's `publish_results` is the one thing any run publishes, and it publishes only this repo's own score
to the OpenSSF API, authenticated by OIDC rather than a secret and reachable from `main`, the weekly schedule, and
`workflow_dispatch` alone. If a real publishing or deploy workflow is added:

- Run it only on `push` to `main` (a protected branch) or on pushes of tags covered by a **protected tag ruleset**
  (`Settings → Rules → Rulesets → New tag ruleset`). Never on `pull_request` or `pull_request_target`, and never
  on an unprotected tag pattern. Without a protected tag ruleset, drop the tag trigger and publish from `push` to `main`
  only.
- The protected tag ruleset must restrict tag creation / update / deletion to the same named maintainer set as the
  `main` rule, so an attacker who lands a benign PR cannot then push a release tag to trigger the deploy.
- Put the credentials behind a GitHub **environment** with required reviewers, and scope the environment to the
  protected branch / tag patterns (`Settings → Environments → Deployment branches and tags`) so secrets cannot be
  read from any other ref.
- Keep `permissions:` minimal — only the scopes the job actually needs (`id-token: write` for OIDC, `contents: read`
  for checkout, etc.).
- Do not call `actions/upload-artifact` with sensitive content from a fork-PR-triggered job.

### Backup and restore drills

GitHub holds the durable state:

- **Code and history** — the git repository on github.com.
- **Per-issue workflow state** — the workflow label + pinned `<!--orchestrator-state ...-->` JSON comment on each
  Issue (schema in [`state-machine/labels-and-state.md`](state-machine/labels-and-state.md#pinned-state)).

The orchestrator process is stateless; restoring an Issue restores progress.

Operator drill checklist (run at least once after setup, then on a recurring cadence):

1. Confirm a current clone of the repo exists off the orchestrator host, tracking `main`.
2. Export open / recently-closed Issues via the GitHub API (`gh issue list --state all --json …`) off-host. The
   pinned-state JSON comment is part of the export.
3. Verify that re-cloning the repo and re-running `./run.sh` against a fresh `WORKTREES_DIR` recovers in-flight Issues
   from their labels + pinned comments — the documented restart contract
   ([`configuration.md#what-survives-a-restart`](configuration.md#what-survives-a-restart)).
4. Confirm `~/.config/<owner>/<repo>/token` (or whatever `ORCHESTRATOR_TOKEN_FILE` points at) is backed up out-of-band;
   the personal access token is not stored in the repo and not recoverable from a code restore alone.

Worktrees under `WORKTREES_DIR` are cache, not state — losing them only forces the next tick to re-create the worktree
from `origin/<base>`.

### AI-generated code review, tests, and scans

Every PR opened by the orchestrator is AI-generated, so the policy is the workflow's normal path, not an extra step:

- **Independent reviewer agent.** The `validating` stage spawns a fresh reviewer against `git diff
  origin/<base>...HEAD`
  ([`state-machine/delivery-stages.md#_handle_validating`](state-machine/delivery-stages.md#_handle_validating-label-workflowvalidating)). It uses a
  different agent role from the implementer (`REVIEW_AGENT` vs. `DEV_AGENT`) and starts with no shared session state.
- **Local verify gate.** When the reviewer says `APPROVED`, the orchestrator runs `VERIFY_COMMANDS` in the per-issue
  worktree before relabeling to `workflow:documenting`
  ([`configuration.md#local-verification-gate`](configuration.md#local-verification-gate)). Set
  `VERIFY_COMMANDS=python3 -m pytest -q;ruff check .` (or your project equivalent) so an AI-produced regression is
  caught locally before the PR is advertised to humans for merge.
- **CI on every PR.** [`../.github/workflows/ci.yml`](../.github/workflows/ci.yml) re-runs Ruff, WPS, and tests with a
  report-only coverage summary;
  [`../.github/workflows/dependency-review.yml`](../.github/workflows/dependency-review.yml) blocks vulnerable /
  non-compliant deps. Mark both **required** in branch protection (see [Required checks](#required-checks)).
- **Human merge by default.** The orchestrator is permanently manual-merge-only — it pings HITL handles when a PR is
  mergeable but never calls `gh.merge_pr`. A human clicks Merge on every PR that lands.
- **Sandboxing reminder.** Agents are spawned with sandbox-bypass flags; the host (or container / VM) is the real trust
  boundary. Agent env is stripped of GitHub tokens, production-secret-shaped vars, and credential-file locators, but a
  hostile dependency executed inside a verify command still runs as the orchestrator's OS user. Keep the orchestrator on
  its own host or in a dedicated VM / container; do not co-locate it with other workloads' secrets on the same user
  account.

## Comment trust boundary (`ALLOWED_ISSUE_AUTHORS`)

The orchestrator feeds issue- and PR-thread comments to coding agents as workflow-driving instructions. On a public
repo that is a prompt-injection surface: any account can post a comment that steers an agent, resumes a parked session,
or re-triggers work. `ALLOWED_ISSUE_AUTHORS` is the operator's control. It defaults unset; setting it to the maintainer
logins turns the pickup allowlist into a comment trust boundary enforced by the shared `github/comments.py` helpers
(`is_trusted_author` / `filter_trusted`). The env-var reference is in
[`configuration.md#agent-roles`](configuration.md#agent-roles); the full per-surface filter list is in
[`state-machine/delivery-stages.md#user-content-drift-detection`](state-machine/delivery-stages.md#user-content-drift-detection).

The security posture:

- **Opt-in, legacy-safe by default.** Unset (the default) trusts every author, preserving the single-user behavior a
  private-repo deployment expects. The boundary exists only once an operator lists the trusted logins, so enabling it is
  a deliberate act, not a silent behavior change.
- **Visible, not deleted.** An untrusted comment stays on the GitHub thread for humans to read; the orchestrator never
  hides, edits, or deletes it. What changes is only its *use as workflow input* — it is omitted from agent prompts,
  the `user_content_hash` drift signal, every awaiting-human resume signal (including the base-sync auto-rebase
  retry-unpark and the `/orchestrator add-review-rounds` review-cap command), and the `in_review` / `fixing`
  PR-feedback loop. So an outsider on a public repo cannot inject instructions into an agent, resume a parked session,
  retry a parked rebase, route `in_review` to `workflow:fixing`, or shift the drift hash, while the audit trail of
  what they said stays intact.
- **One retention, and it is the orchestrator's own words.** The `discussion` stage rebuilds the whole conversation
  into a prompt whenever a round has no session to resume, and it is itself half of that conversation: with the
  allowlist naming the maintainers and not the account the token belongs to — the shape an operator lands on by
  writing down only the humans — the rebuild would otherwise hand a fresh agent the human's answers by number with
  the numbered questions they answer missing. So that one prompt keeps comments the orchestrator *posted*, and only
  those. The evidence is the `orchestrator_comment_ids` recorded at post time, never the `_ORCH_COMMENT_MARKER` in
  the body: the marker identifies the same comments to the scans that DROP them, where anyone pasting it costs only
  themselves their own comment, whereas admitting a comment on it would be an allowlist bypass any author could write.
  No third-party comment is retained anywhere, and no other prompt retains anything. The recovery follow-up's own
  `<!--orchestrator-recovery-followup-->` marker is read the same drop-only way, and is bounded the same way: it is
  how a self-recovered park recognizes the notice it already posted, so pasting it suppresses one "no action needed"
  follow-up and leaves the operator's original @-mention standing — noisier, never more permissive.
- **Filtering is fail-safe.** A comment whose author failed to load (empty login) is untrusted. On the awaiting-human
  resume paths (and the auto-rebase retry-unpark) the filter runs on the whole comment batch up front, so an untrusted
  comment there never advances the consumed-watermark nor is marked read — it is re-filtered on each later tick
  rather than silently absorbed as a new baseline. The late size gate's own content fingerprints read the same way:
  they are taken over the trusted thread alone, and both the watermark they advance and the shared
  `last_action_comment_id` they mark read stop at the highest TRUSTED comment, so an outsider posting above one is
  neither folded into a baseline nor marked read on their behalf. The `in_review` drift path instead excludes untrusted
  PR-conversation comments from the drift prompt but still advances its watermarks past them, so a later tick does
  not re-scan them as fresh feedback.
- **Third-party Bot/App handling is deliberate.** Two distinct mechanisms apply. The `user_content_hash` drift hash,
  the late size gate's local content fingerprints beside it, and the community-contribution PR sweep exclude Bot /
  GitHub-App accounts (Dependabot, Renovate, CI bots) structurally via GitHub's `user.type == "Bot"` flag, independent
  of the allowlist. The comment trust boundary itself does not: on the
  prompt / resume / PR-feedback surfaces a bot is gated like any other author — trusted while the allowlist is empty
  (legacy behavior), and under a populated allowlist trusted only when its own login is explicitly listed. So an
  intentionally allowlisted automation account still works; an unlisted one does not.
- **The pickup half has exactly one bypass, and it is a repository permission.** The allowlist's other job is gating
  *automatic pickup* of an unlabeled issue — the one route a stranger reaches by filing one. The restart of a late
  split whose cancellation completed does not ask it. That path is reachable only by an operator **removing** the
  `rejected` label from a reopened issue, which GitHub grants only to accounts with write access to the repository,
  and it is decided against the orchestrator's own authenticated pinned comment
  ([below](#pinned-state-authentication)) rather than against anything the issue's author wrote. So the authorization
  is the gesture plus that record, and an outsider acting alone reaches none of it — while an outsider's issue an
  operator has deliberately restarted does run. This is the same standing a human already has by applying a workflow
  label by hand, which is the documented way to drive any issue the allowlist would otherwise skip
  ([`configuration/operations.md`](configuration/operations.md#restarting-an-issue-whose-cycle-was-cancelled)).
- **Scope is comment content, not capability.** This boundary keeps untrusted *words* out of agent prompts and workflow
  signals; it is not a sandbox. Agents still run as the orchestrator's OS user with sandbox bypass, so the host remains
  the real trust boundary (see [above](#ai-generated-code-review-tests-and-scans) and
  [`architecture.md#design-constraints`](architecture.md#design-constraints)).

## Pinned-state authentication

The workflow's durable state — the `<!--orchestrator-state ...-->` JSON comment — is authenticated separately from the
`ALLOWED_ISSUE_AUTHORS` boundary above. That allowlist decides which comments are *workflow input*; it does **not**
decide which comment holds *authoritative state*. `read_pinned_state` trusts a comment as state only when **both** hold:
it is authored by the account backing the orchestrator's token (resolved once from `GET /user` and threaded into
worker-thread clients), **and** its entire body is the state marker — exactly what `write_pinned_state` emits.

- **Author, not marker presence.** Any account can post — or edit an older comment to carry — the hidden state marker.
  Trusting the first marker by document order would let an outsider preempt the real pinned state and steer agent
  session fields, branch / PR selection, and terminal branch cleanup (CWE-345). A foreign author's marker is skipped
  before its body is parsed, so it cannot even shadow state with malformed JSON.
- **State-only body, not embedded substring.** The author check alone is not enough: the orchestrator posts ordinary
  comments (e.g. decomposer rationale via `_post_issue_comment`) whose text is attacker-influenced, and does so before
  the real state comment exists on a manually-labeled issue. Such a comment that merely embeds a marker in prose is not
  state-only, so it is never mistaken for state — only a comment that is *nothing but* the marker qualifies.
- **Legacy-safe, no migration.** Existing pinned comments were written by this same account and are state-only by
  construction, so both checks keep honoring them; state writes keep targeting the trusted comment id once found.
- **Independent of the comment boundary.** This authenticates *which comment is state*; `ALLOWED_ISSUE_AUTHORS`
  authenticates *which comments are input*. Both are enforced independently, and the state boundary applies even when
  the allowlist is unset.

## Cross-repo awareness disclosure (`EXPOSE_TRACKED_REPOS`)

When more than one repo is configured (`REPOS`) and `EXPOSE_TRACKED_REPOS` is on (the default), working-agent prompts
carry a compact block naming the *other* tracked repos — each repo's slug, its local `target_root` checkout, and its
base branch — so an agent reasoning about a sibling repo knows it is monitored and where its source lives. The env-var
reference is in [`configuration.md#agent-roles`](configuration.md#agent-roles); the prompt content is in
[`workflow/conversations.md`](workflow/conversations.md#tracked-repository-awareness-in-working-agent-prompts).
The security posture:

- **Disclosure, not escalation.** Agents already run as the orchestrator's own OS user with sandbox bypass, so the host
  is the trust boundary (above, and [`architecture.md#design-constraints`](architecture.md#design-constraints)). Every
  other repo's `target_root` is already on that host and already readable by the agent — it could enumerate the
  checkouts by walking the filesystem today. Naming the paths is information disclosure of data the agent could already
  obtain; it grants no new capability.
- **No secrets in the block.** The block carries only slugs, base branches, and the `target_root` paths the operator
  themselves wrote into `REPOS`. No tokens, no `ORCHESTRATOR_TOKEN_FILE`, no provider keys, no remote URLs — there is
  nothing secret-shaped to redact because nothing secret is included by construction.
- **Write-containment is unchanged.** The orchestrator pushes only the *current* issue's branch from the current
  worktree, via an explicit `<commit>:refs/heads/<branch>` refspec under the hardened git envelope — `HEAD` for a
  caller publishing work it just made, and the exact validated SHA where the decision to push came from inspecting a
  commit, as the discussion stage's plan publication does
  ([`architecture.md#push-path`](architecture.md#push-path-gitauthentication_push_branch)). If a misled agent edits a
  sibling
  checkout, nothing the orchestrator does publishes it — it surfaces as a dirty foreign tree, never as a PR. The
  block's framing also states every listed path is read-only.
- **Prompt-injection blast radius.** Untrusted issue / comment text could now point an agent at a named sibling path,
  but (a) the path was already discoverable and (b) exfiltration still needs an egress channel, and
  `agents.environment.filter_agent_env` already strips the GitHub token, secret-shaped vars, and credential /
  write-credential locators, leaving the agent only its own model-provider auth. The net-new exposure is a *map*,
  not a new *door*.
- **Local paths in GitHub.** An agent could quote a `target_root` into a PR body or park comment. Paths are not secret,
  but an operator who treats them as sensitive flips `EXPOSE_TRACKED_REPOS=off` to suppress the disclosure globally.

The feature defaults on but is **inert for single-repo hosts** — the block is emitted only when more than one repo is
configured — so a default deployment discloses nothing. `EXPOSE_TRACKED_REPOS=off` is the operator kill switch and
reverts to today's behavior with zero added prompt content.
