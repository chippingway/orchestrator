# chipping-orchestrator vs. Agent Orchestrator

## Executive summary

These repositories solve adjacent problems, but they are not drop-in substitutes.

- **chipping-orchestrator** is an automation-first delivery engine. GitHub Issues are its queue and durable state,
  and a fixed, auditable workflow takes an issue through decomposition, implementation, independent review,
  documentation, and a human merge. It is strongest when a Linux-hosted solo or small team wants work to proceed
  unattended under explicit policy.
- **Agent Orchestrator (AO)** is an interaction-first agent workspace. A Go daemon, Electron desktop app, mobile
  client, local persistence, terminal and Chat controllers, browser previews, and a broad adapter catalog let a user
  create and supervise many agent sessions. It is strongest when a user wants a polished, cross-platform control
  plane and chooses or delegates tasks interactively.

For this project's stated mission, the recommendation is to **keep chipping-orchestrator focused rather than turn it
into an AO clone**. Its GitHub-native state machine, unattended delivery loop, independent review gate, minimal
runtime dependency set, and security/supply-chain controls are real differentiators. Selectively borrow AO's provider
adapter discipline, live session visibility, and user-facing diagnostics. Do not absorb Electron, mobile, cloud, or a
second local state model unless the product mission explicitly changes.

The short comparative verdict by requirement is:

- **Unattended issue-to-PR delivery — chipping-orchestrator.** It has a complete fixed lifecycle; AO's tracker lane is
  not yet active at runtime.
- **Interactive supervision and UX — AO.** It provides desktop Kanban, terminal/Chat, browser preview,
  notifications, mobile, and packaged installers.
- **Agent and platform breadth — AO.** It advertises 26 agents and macOS/Windows/Linux distribution, versus
  Codex/Claude on Linux.
- **Workflow auditability — chipping-orchestrator.** Human-visible state, mandatory stages, size gates, and manual
  merge make policy explicit.
- **Repository supply-chain controls — chipping-orchestrator.** It has SHA-pinned Actions, Dependabot, dependency
  review, lockfile audit, CodeQL, Scorecard, and a security policy.
- **Desktop/application hardening — AO.** Electron sandboxing, CSP, navigation controls, browser-profile isolation,
  listener guards, and macOS signing checks are substantive.
- **Runtime agent containment — neither.** Both ultimately trust the host; AO has experimental host-trusted
  reviewers, while chipping-orchestrator invokes agents with sandbox bypass.
- **Test and architecture enforcement — close, with stronger verified evidence for chipping-orchestrator.** Both are
  test-heavy. This checkout passed 5,115 tests; AO has race tests, strict types, and strong linting but could not be
  run in this environment.
- **Development throughput and contributor depth — AO.** It has roughly twice the 30-day commits, fourteen times the
  author emails, daily activity, and more frequent stable releases.
- **Simplicity and operability — chipping-orchestrator.** It is one Python service with two direct runtime
  dependencies, no inbound server in the core polling service, and no required database.
- **Productized installation and upgrades — AO.** It has native downloads and automatic updates;
  chipping-orchestrator remains a manual Linux service deployment.
- **Cost/trajectory analytics — chipping-orchestrator.** Usage, cost, skill, trajectory, JSONL, Postgres, and
  dashboard surfaces are first-class.
- **Roadmap clarity — mixed.** chipping-orchestrator has an explicit but stale/non-authoritative list; AO has a fresh
  status ledger but no prioritized roadmap.

Security needs one qualification: chipping-orchestrator has the stronger **repository and unattended-bot security
posture**, but neither product should run beside unrelated secrets without an OS/container/VM boundary. AO's desktop
surface is thoughtfully hardened, yet its much larger attack surface, ambient environment inheritance, accepted
plaintext LAN mode, mutable Action tags, and missing checked-in vulnerability policy lower the overall confidence.

## Scope, snapshots, and limitations

The path requested for the comparison, `~/git/chipping/orchestrator/`, did not exist for the `geser` user. This report
uses `/home/geser/git/agent-orchestrator`, the only plausible peer checkout. Its remote is
`https://github.com/Untrivial-ai/agent-orchestrator.git`, and both repositories contain reciprocal untracked
`docs-compare/` directories, which further supports that interpretation.

Snapshot date: **2026-09-01**.

- **chipping-orchestrator:** `/home/geser/git/chipping-orchestrator` at
  `8eed5c6a0687827a9fe86c6dc17b9b2b81916842`; `main` had no recorded ahead/behind count against the existing
  `origin/main` ref.
- **Agent Orchestrator:** `/home/geser/git/agent-orchestrator` at
  `be0fe0b322d2b88ea1fdeea72b59cc1597dcef43`; `main` had no recorded ahead/behind count against the existing
  `origin/main` ref.

The audit used the checked-out files and local Git history only; it did not fetch either remote. Existing untracked
`docs-compare/` content was excluded and left untouched. `analytics-db/data/` was not traversed or read.

The report combines source/document review, tracked-file metrics, local Git history, configuration inspection, and
available executable checks. It is not a penetration test, dependency-advisory lookup, performance benchmark, or
audit of GitHub organization settings. In particular:

- chipping-orchestrator's Ruff, WPS, and pytest checks were run successfully. Pytest collected 5,163 tests: 5,115
  passed and 48 skipped because Plotly/pandas or a disposable live Postgres were not installed/configured.
- AO's Go and frontend suites could not be executed: Go was not on `PATH`, `frontend/node_modules` was absent, and no
  dependency installation was performed. Its test conclusions therefore rely on checked-in tests and CI definitions,
  not a green local run.
- AO test-call counts are static approximations. Go `Test...` function counts are exact for tracked files; JavaScript
  `test(`/`it(` calls can include helper patterns and do not equal a runner's collected count.
- “Security level” below means evidence visible in these checkouts for the documented deployment model. It does not
  certify that operator-owned controls are enabled or that no vulnerability exists.

## Product and workflow comparison

- **Primary abstraction:** chipping-orchestrator moves a GitHub Issue through one label and pinned state comment. AO
  keeps durable project, worker, and orchestrator sessions in a local daemon. GitHub state is universally visible;
  local sessions support richer interaction.
- **Task intake:** chipping-orchestrator automatically polls eligible issues and supports backlog, pause, Q&A, and
  design flows. AO's user or project orchestrator creates workers. The former automates a queue; the latter supports
  deliberate delegation.
- **Delivery policy:** chipping-orchestrator fixes the decomposition, implementation, validation, documentation, and
  human-merge sequence. AO supervises agent-native work with lifecycle and SCM observations. Fixed policy is easier
  to audit; AO is more flexible.
- **Planning:** chipping-orchestrator can split issues or publish a discussion plan PR. AO maintains a persistent
  project-level planning/delegation conversation and provides the richer experience.
- **Review and merge:** chipping-orchestrator requires a fresh reviewer, bounded fixes, a cumulative size gate, final
  docs, and manual merge. AO offers broad interactive reviewers and direct merge actions. The former emphasizes
  enforced independence; the latter emphasizes supervision and speed.
- **State:** chipping-orchestrator is process-stateless over GitHub. AO uses SQLite facts, migrations, CDC, SSE, and
  derived status under `~/.ao`. GitHub adds API coupling; SQLite adds local backup and migration duties.
- **Concurrency:** both isolate Git work with worktrees. chipping-orchestrator bounds repositories/issues and
  serializes issue families; AO coordinates multiple durable workers and runtime observers.
- **Agent support:** chipping-orchestrator supports configurable Codex/Claude roles. AO advertises 26 agents with
  native Chat and terminal adapters. AO wins breadth; the smaller matrix is easier to test deeply.
- **Interfaces:** chipping-orchestrator has a service/CLI and Streamlit analytics viewers. AO has Electron, CLI,
  structured Chat, native terminal, browser/DevTools, mobile, and cloud-related surfaces. AO is more usable and much
  more complex.
- **SCM/tracker:** GitHub is chipping-orchestrator's queue and source of truth. AO documents a shipped GitHub core and
  contains GitLab adapters, but equivalent end-to-end status is less clear. Its tracker observer/mirroring lane is not
  active, which is the largest replacement gap.
- **Browser/UI testing:** chipping-orchestrator has no agent browser. AO provides per-worker ephemeral profiles,
  bounded commands, previews, screenshots, console/error access, and DevTools.
- **Observability:** chipping-orchestrator is stronger for workflow economics and forensic trajectories. AO's live
  Kanban, notifications, session history, and telemetry are stronger for immediate supervision.
- **Deployment:** chipping-orchestrator is a Linux/Python service. AO is packaged for macOS, Windows, and Linux and
  has automatic updates and mobile. AO wins accessibility; chipping-orchestrator wins headless simplicity.

### Architectural strengths and costs

chipping-orchestrator's strongest architectural choice is that the state machine and its state are the same things a
human sees on GitHub. There is no reconciliation between a hidden scheduler database and the issue tracker. The
single-process polling model, bounded schedulers, per-issue worktrees, authenticated pinned state, and compatibility
tests make restart behavior understandable. The cost is deep coupling to GitHub vocabulary, API limits, comment
semantics, and long-lived compatibility fields. Polling also imposes latency and a rate-limit floor.

AO's strongest architectural choice is its fact-oriented daemon: durable facts in SQLite, display status derived at
read time, DB-triggered CDC, explicit service/port/adapter boundaries, and separate TUI/Chat controllers. This is a
sound base for a responsive multi-client product. The costs are a much larger state space, migrations, multiple
transports, release platforms, generated API contracts, process/runtime adapters, and more failure boundaries. The
architecture is sophisticated because the product surface demands it, not because the two systems implement the same
job differently.

An architectural rewrite of chipping-orchestrator around AO's SQLite daemon would discard one of this project's main
advantages: GitHub-visible, externally durable workflow state. A lightweight read-only UI over the existing GitHub
and analytics surfaces would capture much of the operator value without introducing a competing source of truth.

## Pros and cons

### chipping-orchestrator

Pros:

- Complete unattended GitHub issue-to-PR loop, including decomposition, dependent child issues, conflict handling,
  independent review, fix rounds, final documentation, and manual acceptance.
- Human-readable durable state with no required internal database and strong restart/recovery semantics.
- Explicit safety policy around cumulative PR size, publication ordering, snapshot refs, trusted comments, pinned
  state authorship, and hardened authenticated Git operations.
- Very strong repository self-checks: package inventory, import layering, public exports, documentation links, lint
  suppressions, Action pins, CI timeouts, and test collection are tested as code.
- Small default runtime dependency surface: two direct Python dependencies; analytics UI dependencies are optional.
- Deep test inventory and a green local run at the audited commit.
- Rich cost, token, skill, and trajectory observability that directly answers whether autonomous work is economical.
- Minimal inbound attack surface: it is a polling client/service, not a local HTTP application.
- Explicit vulnerability-reporting policy and unusually thorough operator hardening guide.

Cons:

- Agents run with sandbox/approval bypass; the host is the real security boundary. This is incompatible with a shared
  workstation containing unrelated secrets unless an external sandbox is supplied.
- `ALLOWED_ISSUE_AUTHORS` is empty by default. That is convenient for private repositories but unsafe for public
  unattended deployments unless the operator actively configures it.
- Fine-grained PATs remain high-value, write-capable credentials; GitHub App migration and container/VM isolation are
  still future work.
- Linux-only and limited to Codex/Claude. There is no rich operational UI, mobile client, browser automation, or
  packaged installer.
- GitHub polling and closed-issue sweeps can consume rate limits, especially in multi-repo deployments.
- The source is no longer small despite the focused product: 75.5k production code lines, 26 production modules over
  500 lines, five over 1,000 lines, and several late-split owners over 1,500 lines.
- WPS is strong, but many production files carry targeted WPS201/WPS202 complexity waivers. Passing lint therefore
  does not mean the workflow hotspots are simple.
- No enforced static type checker such as mypy/pyright is configured for the Python code.
- Development and maintenance are highly concentrated. The security policy describes the project as solo-maintained,
  and one automation-named account authored 700 of 864 non-merge commits in the 90-day window.
- The explicit roadmap is non-authoritative, dated 2026-08-19, and still uses the old “Agent Orchestrator” title after
  the chipping-orchestrator rename.
- There is no contributor guide, issue template set, or automated release/publish workflow. Tags are annotated but the
  latest inspected tag was not cryptographically signed.

### Agent Orchestrator

Pros:

- Strong, polished product experience across desktop, terminal, structured Chat, browser preview, notifications, and
  mobile, with native packages and auto-update.
- Broad agent ecosystem: 26 advertised coding agents and a leaf-adapter architecture for runtime/reviewer/provider
  integrations.
- Sound daemon model: ports and adapters, durable facts, derived status, conservative lifecycle termination, SQLite
  migrations, CDC, generated OpenAPI, and thin clients.
- Strong language-level correctness tools: Go's compiler and race tests, `go vet`, a broad golangci-lint set including
  `gosec`, and strict TypeScript with unused/return/fallthrough checks.
- Large test estate across backend, renderer, CLI, Playwright smoke/E2E, mobile, packaging, and update behavior.
- Electron hardening is concrete: renderer sandbox, context isolation, disabled Node integration, CSP, navigation and
  popup restrictions, per-worker ephemeral browser partitions, and bounded/redacted network observation.
- Conservative data-loss rules: never infer death from a failed probe, never force-delete dirty worktrees, and keep
  app state under one explicit data root.
- macOS artifact verification covers code-signing validity, Gatekeeper assessment, notarization/stapling, and updater
  behavior. Build workflows compute artifact digests.
- Much stronger contributor/community capacity, with issue forms, a PR template, contribution guidance, a Discord
  workflow, 42 distinct author emails in 30 days, and 72 in 90 days.
- Development status is fresh: `docs/STATUS.md` changed on the audit date and distinguishes shipped behavior from
  incomplete acceptance/runtime work.

Cons:

- It does not currently provide chipping-orchestrator's unattended, label-driven issue lifecycle. The tracker lane is
  explicitly documented as inactive at runtime.
- The trusted computing base is large: Electron, Go daemon, SQLite, SSE/WebSocket, terminal runtimes, browser bridge,
  many agent adapters, mobile, updater/release tooling, telemetry, and tracked cloud code.
- Coding agents and several reviewers remain host-trusted. The accepted reviewer-gateway ADR says platform isolation
  is still required before experimental reviewers can be called contained/read-only.
- Runtime implementations build child environments from `os.Environ()` plus configured values. No equivalent to
  chipping-orchestrator's repository-wide secret-shaped environment stripping was found, so a host process environment
  can become agent-visible.
- The optional LAN listener deliberately uses plaintext HTTP with an eight-character bearer password. It is default
  off, authenticated, lockout-protected, and documented as home-network-only, but an untrusted-network observer can
  still capture credentials and traffic.
- The loopback API is unauthenticated by design. CORS and local-control guards reduce browser/DNS-rebinding risk, but
  any already-compromised local process shares the host trust boundary.
- Checked-in supply-chain governance is uneven: Gitleaks and Go `gosec` are present, but no `SECURITY.md`, Dependabot
  configuration, CodeQL workflow, dependency-review workflow, or standing dependency-vulnerability scan was found.
- The golangci configuration globally excludes `gosec`'s variable-file, traversal-taint, SSRF-taint, and computed
  subprocess findings (`G304`, `G703`, `G704`, and matching `G204` reports) with project-specific rationale. Since
  AO legitimately handles paths, URLs, and commands, focused validation tests and review must carry that burden.
- Of 45 checked-in `uses:` references, only three used full commit SHAs and one container used a digest; the remaining
  references used mutable action tags. Only two of roughly nineteen workflow jobs declare explicit timeouts.
- Dependency surface is much larger: 83 unique modules appear in the backend Go sums, the frontend lock contains
  1,328 package entries, and mobile adds 660 entries, before other package locks.
- Core modules/components are large. About 13% of classified Go and TypeScript production files exceed 500 lines and
  roughly 4% exceed 1,000 lines; examples include a 4,535-line session manager, 3,309-line agent-switching owner,
  3,116-line conversation store, and 2,965-line Chat workspace component.
- The tracked `cloud/` slice contains roughly 29.3k Go lines across 85 Go files, but no Go `_test.go` files were found,
  and no checked-in workflow runs cloud Go tests on pull requests. It should be treated as less mature than the core
  daemon unless another private gate exists.
- Documentation shows transfer/velocity drift: current and legacy GitHub organizations/domains are mixed in links,
  and the architecture's load-bearing list still says “127.0.0.1 only” despite the accepted opt-in LAN listener.
  These gaps weaken confidence in invariants during rapid change.
- Remote telemetry is on in production desktop/mobile. It is well documented and redacted, but it sends a GitHub owner
  segment that can identify a personal account; desktop opt-out requires three environment variables, and the
  production mobile app has no in-app telemetry opt-out.
- Root licensing says Apache-2.0 while seven package manifests report MIT and one reports Apache-2.0. Several of the
  MIT manifests are distributable platform/npm packages rather than private workspaces. This may be intentional per
  package, but distribution/license intent should be explicit.

## Roadmap comparison

### Existing roadmap signals

chipping-orchestrator's [`plans/roadmap.md`](roadmap.md) says the original scope is feature-complete and lists five
future areas:

1. a spec-first/failing-test stage;
2. repository memory across issues;
3. container or VM isolation plus GitHub App credentials;
4. an architectural review pass; and
5. repository-local policy overrides and lifecycle hooks.

That list is useful because it is explicit, but it is a working note rather than specification, was last updated on
2026-08-19, predates three subsequent stable releases, and has no priority, owner, acceptance metric, or target
release.

AO's [`docs/STATUS.md`](../../agent-orchestrator/docs/STATUS.md) is more current and more precise about what exists.
Its open edge is concentrated around:

- cross-platform release acceptance for browser automation;
- limits in importing raw terminal history during interface handoff;
- inability to transfer an in-flight tool invocation between controllers;
- the inactive tracker observer/mirroring lane; and
- incomplete surfacing of raw PR/tracker facts.

The reviewer-security ADR adds another important prerequisite: experimental host-trusted reviewers need a fail-closed
platform sandbox before they can be represented as contained/read-only. This is a security roadmap item even though it
is not in the short `STATUS.md` “in flight” list.

AO's status ledger is fresher than chipping-orchestrator's roadmap, but it is not a product roadmap: there is no clear
ordering, capacity allocation, release target, or definition of which product surface is being consolidated versus
expanded. Numerous dated plans exist under `docs/plans/` and `docs/superpowers/`, but they are implementation notes,
not one decision surface.

### Recommended roadmap for chipping-orchestrator

The comparison suggests this order. It deliberately preserves the project's automation-first identity.

#### Now: reduce existential deployment and maintenance risk

1. **Make external containment the first product-level milestone.** Provide and test one supported container/VM
   deployment profile, with a documented filesystem/network/credential boundary. Keep the warning that prompt-level
   permissions are not containment.
2. **Default-deny public intake or make the unsafe default impossible to miss.** A startup diagnostic should treat an
   empty `ALLOWED_ISSUE_AUTHORS` on a public repository as a high-severity deployment decision, not a quiet default.
3. **Move from long-lived PATs toward a GitHub App.** Use short-lived installation tokens and keep the current
   per-repository least-privilege model.
4. **De-risk the late-split subsystem.** Put explicit size/complexity budgets around the five >1,000-line production
   owners and reduce the WPS201/WPS202 waiver footprint without changing the public state contract.
5. **Refresh the roadmap and release identity.** Rename the note, date it to the current release, mark each item
   `now`/`next`/`later`, and separate shipped release history from future proposals.
6. **Harden releases.** Add a reproducible build/publish design, signed tags or attestations, checksums, and a minimal
   rollback story before distribution broadens.

#### Next: borrow high-value AO capabilities without importing its platform

1. **Formalize a provider capability interface.** Preserve the current two deeply tested providers, but make session,
   resume, usage, permission, and output capabilities explicit so a third backend does not create scattered branches.
2. **Add a lightweight read-only operations view.** Build on existing analytics/GitHub facts to show active issues,
   parks, session age, pending human actions, and cost. Do not create a second workflow database.
3. **Pilot spec-first work narrowly.** Measure defect/review-round improvement on suitable issue classes before adding
   another mandatory state-machine stage.
4. **Consider a webhook-assisted wake-up path.** Keep polling as recovery/reconciliation, but use events to reduce
   latency and GitHub rate pressure if deployment complexity remains acceptable.
5. **Improve project sustainability.** Add contribution guidance, issue/PR templates, and an ownership/review policy
   for security-sensitive dependency and workflow files.

#### Later: add context and policy only with measured need

1. Repository memory should be bounded, inspectable, redacted, and treated as untrusted prompt input.
2. Hooks and policy overrides should have a narrow schema, explicit trust model, timeouts, and secret filtering; they
   must not silently become arbitrary root-level execution hooks.
3. Architectural review should start as an optional lint/report pass with measurable findings, not a new unbounded
   agent loop.
4. AO integration could be explored when its tracker lane is active: chipping-orchestrator can remain the GitHub
   policy/queue engine while AO provides interactive supervision for a parked exception. Avoid letting both tools own
   the same branch or agent session.

### What not to copy without a strategy change

- A full Electron shell, mobile client, cloud control plane, or local conversation database.
- Dozens of provider integrations before capability contracts and containment exist.
- Default-on remote product telemetry for a headless operator tool.
- Direct merge actions that bypass the project's deliberate human-merge boundary.

## Development pace and project health

The following numbers use local Git history with fixed windows ending on 2026-09-01. “Churn” is gross additions plus
deletions across commits, not net repository growth. Commits are not equivalent units of effort, and automated/AI
authorship makes direct productivity conclusions especially unsafe.

| Metric | chipping-orchestrator | Agent Orchestrator |
| --- | ---: | ---: |
| First local-history commit | 2026-04-25 | 2026-02-13 |
| Total commits | 1,102 | 2,512 |
| Non-merge commits | 1,100 | 2,312 |
| Distinct author emails, all history | 5 | 109 |
| Commits in 30-day window | 278 | 531 |
| Distinct author emails in 30-day window | 3 | 42 |
| Active commit days in 30-day window | 24 | 30 |
| 30-day gross additions / deletions | 172,240 / 62,544 | 521,372 / 100,045 |
| Commits in 90-day window | 864 | 1,096 |
| Distinct author emails in 90-day window | 4 | 72 |
| Active commit days in 90-day window | 72 | 90 |
| Stable `vX.Y.Z` tags in 30-day window | 5 | 11 |
| Stable `vX.Y.Z` tags in 90-day window | 11 | 18 |

Interpretation:

- AO has the clearer throughput and community advantage: activity every day, a much wider contributor base, more
  product-facing feature/fix work, and twice as many stable releases in the last month.
- chipping-orchestrator is also moving extremely quickly for a focused solo-maintained tool. Its 30-day subjects were
  dominated by documentation and refactoring (115 `docs:` and 70 `refactor:` commits), which indicates deliberate
  hardening but also considerable architectural churn after the feature set was called complete.
- AO's 30-day history was dominated by 298 `fix:` and 145 `feat:` subjects. That demonstrates active delivery and a
  large feedback loop; it also implies a high stabilization load and makes release cadence alone a poor proxy for
  stability.
- In chipping-orchestrator's 90-day window, the account named `pichaautobot` authored 700 of 864 non-merge commits
  (81%). That can be excellent leverage, but it does not improve human bus factor by itself.
- Both projects are only months old and have very high churn. Neither should be evaluated like a slow-moving mature
  infrastructure project. Compatibility tests, release discipline, and regression gates matter more than raw commit
  volume at this pace.

## Code quality and maintainability

### Quantitative snapshot

`tokei` was used for code/comment/blank classification. Generated AO API TypeScript/OpenAPI and obvious generated
files were excluded where practical. Threshold counts use physical lines and are therefore a maintainability signal,
not a complexity proof.

| Measure | chipping-orchestrator | Agent Orchestrator |
| --- | ---: | ---: |
| Production source files measured | 474 Python | 692 Go + 493 TypeScript/JavaScript/CSS |
| Production code lines measured | 75,543 | 144,441 Go + 49,066 frontend/package code |
| Test files measured | 912 Python | 488 Go + 251 frontend/package test files |
| Test code lines measured | 128,538 | 157,275 Go + 29,587 frontend/package code |
| Production files over 500 physical lines | 26 (5.5%) | 157 (about 13.2%) |
| Production files over 1,000 physical lines | 5 (1.1%) | 50 (about 4.2%) |
| Python/Go test functions | 5,152; 5,163 pytest items collected | 5,037 |
| Approximate JS/TS `test`/`it` calls | N/A | 3,670 |
| TODO/FIXME/XXX/HACK matches | 3 | 25 |

chipping-orchestrator has the higher test-to-production code ratio and much smaller module-size tail. Its repository
tests enforce architecture in a way most Python projects do not. The trade-off is test volume and maintenance cost:
128.5k test code lines for 75.5k production lines can make safe refactors slow if tests over-specify implementation
details. The repository's explicit redundancy-review guidance is therefore important.

AO benefits from compile-time types across its main languages and checks API-generation drift. Its Go race suite,
frontend unit tests, renderer Playwright smoke tests, cross-platform CLI E2E, mobile tests, packaging checks, and macOS
updater E2E cover boundaries chipping-orchestrator does not have. The core Go test code is almost the same size as the
Go production code. The maintainability concern is concentration in very large owners and UI components, plus a
tracked cloud slice with neither Go tests nor a visible PR gate.

### Quality-system comparison

- **Formatting and lint:** chipping-orchestrator uses Ruff defaults plus E501 and WPS. AO uses gofmt/goimports,
  `go vet`, a broad golangci suite, and strict TypeScript.
- **Static types:** chipping-orchestrator has Python hints but no enforced mypy/pyright gate. AO has the Go compiler
  and TypeScript `strict` mode.
- **Concurrency:** chipping-orchestrator has focused scheduler/race tests. AO's CI runs `go test -race ./...` and has
  extensive lifecycle/runtime tests.
- **Architecture:** chipping-orchestrator executes package-inventory, layering, import, export, and test-mirror rules.
  AO documents port/adapter and service boundaries and gets normal compile/import enforcement.
- **Generated contracts:** chipping-orchestrator checks package/build smoke and repository rules. AO regenerates and
  drift-checks sqlc, OpenAPI, and TypeScript artifacts.
- **Integration:** chipping-orchestrator uses real-Git tests, an in-memory GitHub, and optional live Postgres. AO has
  CLI E2E, Playwright renderer, packaged-app/update gates, and test-server/fake-backed daemon adapters.
- **Coverage:** both report or exercise large suites, but no repository-wide minimum threshold was found in either.
- **Local result:** chipping-orchestrator's Ruff/WPS and 5,115 tests passed with 48 optional skips. AO was not run
  because its toolchain/dependencies were absent.

### Documentation quality

chipping-orchestrator has the more coherent internal documentation map. `docs/README.md` routes architecture,
state-machine, workflow, configuration, observability, and security detail; links and source layout are repository
tested. The downside is density: some landing pages duplicate stable summaries to preserve anchors, and the prose can
be harder to scan than the focused product warrants. The stale roadmap title/date is the most visible drift.

AO has excellent diagrams and detailed lifecycle, release, telemetry, daemon, and status explanations. Its top-level
README is far stronger product documentation. Rapid organization/product changes have left conflicting identities and
at least one stale security invariant in architecture documentation. Documentation should be consolidated around one
current owner/URL, and invariant tests should cover the loopback/LAN rule just as code tests do.

## Security assessment

### Relative maturity by layer

- **Repository and supply chain:** strong for a young chipping-orchestrator; mixed for AO.
- **Agent containment:** low for both without external isolation. chipping-orchestrator reduces child secrets; AO makes
  its host trust explicit.
- **Network surface:** chipping-orchestrator's core has outbound GitHub/model traffic but no app listener. AO has a
  larger, actively hardened loopback/LAN/browser/cloud/mobile surface.
- **SCM credentials:** chipping-orchestrator keeps a fine-grained PAT outside the repo, strips it from children, and
  hardens authenticated Git, but has not migrated to a GitHub App. AO uses `gh`/environment-backed credentials and
  real host Git behavior, maximizing compatibility within a broader host boundary.
- **Untrusted input:** chipping-orchestrator has an author allowlist and trusted-comment filtering, but the allowlist
  defaults empty. AO tasks are generally user-created, but repository/browser content still crosses host-capable
  agents.
- **State integrity:** chipping-orchestrator authenticates pinned state and guards transitions/markers. AO uses SQLite
  transactions, migrations, CDC, local data permissions, and controller fencing.
- **UI isolation:** chipping-orchestrator has little UI surface. AO has strong Electron sandbox, CSP, navigation, and
  profile isolation.
- **Release security:** chipping-orchestrator has no CI publisher and its latest inspected annotated tag was unsigned.
  AO verifies macOS signing/notarization/stapling and artifact digests, but uses an external conductor and many mutable
  CI action refs.
- **Vulnerability reporting:** chipping-orchestrator has a private channel, policy, supported versions, and response
  targets. AO has no root policy in the checkout.
- **Privacy:** chipping-orchestrator's detailed trajectories opt in and are locally controlled/redacted. AO defaults
  pseudonymous telemetry on in production; a GitHub owner can identify a user, and mobile lacks an in-app opt-out.

### chipping-orchestrator security level

For a **dedicated, access-controlled VM/container and private or author-restricted repositories**, the visible posture
is **moderate to strong** for a young autonomous tool. The strongest evidence is not a claim but a set of controls:
exact lockfile installs, all 12 Action references pinned to commit SHAs, five CI/security jobs with timeouts, weekly
full-lock auditing, dependency diff review, CodeQL, Scorecard, secret-filtered child environments, authenticated pinned
state, hardened Git configuration, custom-ref lease checks, independent review, and manual merge.

For a **shared developer workstation or an unrestricted public issue queue**, the level falls to **low** because a
sandbox-bypassed model can execute arbitrary host actions and an untrusted issue can become model input/work. The
documentation states this clearly, but documentation is not isolation. Container/VM support and safe public defaults
are therefore security work, not optional polish.

### Agent Orchestrator security level

For a **single-user workstation whose entire user account is already trusted to the selected agents**, AO's posture is
**moderate**. Its desktop/browser/network code contains thoughtful concrete protections, conservative lifecycle rules,
secret/telemetry redaction, Gitleaks, `gosec`, lockfiles, and signed macOS release verification.

It should not yet be described as a contained multi-tenant or hostile-repository platform. The accepted reviewer ADR
explicitly says the capability gateway is not a process sandbox; some adapters keep host-trust warnings; agent
environments inherit ambient host values; the loopback service trusts local processes; and LAN confidentiality is
deliberately absent. The checked-in supply-chain and disclosure gaps are material for an auto-updating desktop product
with a large dependency graph.

### Highest-priority security risks

For chipping-orchestrator:

1. **Sandbox-bypassed agents on a secrets-bearing host** can compromise host credentials/data. Supply a supported
   external sandbox with least-mounted files and an egress policy.
2. **An empty public-repository author allowlist** enables prompt injection and unauthorized work/cost. Detect
   visibility and default deny or require explicit acknowledgement.
3. **A long-lived write-capable PAT** can compromise repository content, issues, and PRs. Move to short-lived GitHub
   App installation tokens.
4. **Automated fast-forward/self-update from `main`** turns a source compromise into runtime deployment. Require a
   protected reviewed branch, signed provenance, and pinned/verified releases.

For AO:

1. **Host-trusted agents/reviewers and inherited environment** can expose local secrets/data. Implement the ADR's
   isolation providers and a default-deny child environment.
2. **Plaintext optional LAN access** permits interception on untrusted networks. Prefer pinned TLS or tunnel-only
   secure transport and per-device revocable credentials.
3. **Mutable Action refs and no standing dependency scan** increase CI/release and vulnerable-dependency risk. Pin
   Actions by SHA and add updater, dependency-review, CodeQL, and vulnerability workflows.
4. **No private vulnerability policy** can delay or publicize disclosure. Add `SECURITY.md`, supported versions, a
   private channel, and response targets.
5. **Default-on telemetry with incomplete mobile opt-out** creates privacy surprise/compliance burden. Add in-app
   controls to every client, clear first-run notice, and deletion guidance.
6. **An untested tracked cloud Go slice** risks correctness/security regressions in a networked service. Add tests and
   a dedicated PR workflow before calling it production-ready.

## Operations, reliability, and performance

### chipping-orchestrator

Operational advantages:

- One long-lived process and transient agent/verification children.
- No required local state database; restart recovery reads GitHub.
- Bounded issue concurrency, retry/review/conflict budgets, timeouts, and shutdown watchdog.
- Human-visible parks and recovery comments.
- Simple dependency model and headless/systemd deployment.
- Optional observability database cannot steer workflow behavior.

Operational disadvantages:

- GitHub availability, API semantics, rate limits, and poll interval are on the critical path.
- A 60-second default poll adds latency and every configured repository creates a request floor.
- Local worktrees/refs still require cleanup/recovery discipline despite remote workflow state.
- Self-updating a running orchestrator is convenient but couples production to the branch and wrapper behavior.
- Optional analytics adds Postgres and Streamlit only after the otherwise simple core has been deployed.
- Linux-only support narrows operator choice.

### Agent Orchestrator

Operational advantages:

- Native installers, automatic update, health/readiness endpoints, desktop daemon supervision, and cross-platform
  terminal implementations.
- Durable local sessions and conversations, controller fencing, restart recovery, CDC replay, and conservative reaper.
- Rich live status, notifications, PR/CI/review facts, and direct diagnostics.
- SQLite/WAL is appropriate for a single-user local daemon and avoids an external service.

Operational disadvantages:

- Many moving parts must agree: Electron/preload/renderer, daemon, database schema, generated API, agent runtime,
  terminal mux, browser runtime, update feed, and platform packaging.
- Auto-update raises the consequence of signing/feed/release mistakes; the repository documents a prior macOS release
  incident and mandates one publisher.
- Local state must be backed up, migrated, and protected; copying `~/.ao` also copies installation identity and other
  sensitive state.
- Mobile/LAN/cloud features add network failure and authentication modes to what was originally a local tool.
- Electron and the frontend dependency graph impose a materially larger disk, memory, update, and supply-chain cost.

Neither repository contains enough repeatable benchmark/load/SLO evidence to claim a performance winner. AO's Go
daemon and event-driven local reads should provide lower UI latency; chipping-orchestrator's workload is mostly remote
I/O and agent runtime, where Python execution speed is unlikely to dominate. GitHub rate consumption and maximum
reliable concurrent sessions/issues are more relevant benchmarks than microseconds in either core.

## Governance, sustainability, and release maturity

- **License:** both roots use Apache-2.0.
- **Contribution onboarding:** chipping-orchestrator has an agent guide but no general contributor guide/templates.
  AO has `CONTRIBUTING.md`, issue forms, a PR template, and community sync/Discord.
- **Security disclosure:** chipping-orchestrator has a clear private-report policy; AO has no checked-in policy.
- **Contributor breadth:** chipping-orchestrator is explicitly solo-maintained; AO's base is large and growing.
- **Dependency automation:** chipping-orchestrator has Dependabot cooldowns and security-update guidance. AO has no
  checked-in dependency updater.
- **Release frequency:** high for chipping-orchestrator's age and extremely high for AO, including nightlies.
- **Distribution:** chipping-orchestrator builds/smoke-tests source and wheels but has no publisher. AO has native
  artifacts/updater and an external single release conductor.
- **Provenance:** chipping-orchestrator SHA-pins CI, but its latest inspected tag was unsigned. AO verifies macOS
  signatures/notarization; its inspected stable tag was lightweight over a GitHub-signed commit.

AO has the healthier contributor funnel and much lower conventional bus-factor risk. chipping-orchestrator has stronger
security governance per line of code, but its controls and complex workflow knowledge still depend on very few humans.
Adding contributors without loosening its executable architecture contracts is a higher-leverage sustainability move
than adding another major product surface.

## Selection guidance

Choose chipping-orchestrator when most of these are true:

- GitHub Issues are already the work queue and audit surface.
- Work should progress without a person keeping a desktop app open.
- A fixed decomposition/review/documentation policy is a feature, not a constraint.
- Linux and Codex/Claude are sufficient.
- Manual merge and visible human escalation are required.
- Token/cost attribution and workflow trajectories matter.
- A dedicated host/VM/container can be provided.

Choose AO when most of these are true:

- Users want to start, steer, inspect, and resume agents interactively.
- macOS/Windows support, installers, automatic updates, and a polished UI matter.
- The team uses many agent CLIs or needs native terminal and structured Chat modes.
- Frontend/browser tasks benefit from isolated preview and browser automation.
- Local session history, notifications, Kanban, mobile access, and rich PR context are more important than a GitHub
  label state machine.
- The user's workstation is already the accepted trust boundary for agents.

Use both only with clear ownership:

- chipping-orchestrator owns GitHub issue state, branch publication policy, and readiness for human merge;
- AO is used for separate interactive tasks or, eventually, as a supervisor for explicitly handed-off parked work;
- never let both systems concurrently own the same branch/worktree/session;
- wait for or build an explicit AO tracker/handoff contract rather than inferring state from UI status.

## Bottom line

AO is the broader, faster-moving, better-funded-by-contributors product and the obvious winner for interactive agent
supervision. chipping-orchestrator is the sharper tool for autonomous GitHub delivery and currently shows the more
complete repository-level security/supply-chain discipline.

The best strategic path is not feature parity. It is to make chipping-orchestrator safer to deploy, easier for more
than one maintainer to evolve, and easier to observe live while preserving its fixed workflow and GitHub-native source
of truth. External agent containment, GitHub App credentials, safe public defaults, hotspot reduction, and a refreshed
roadmap should precede new workflow stages or UI/platform expansion.

## Evidence map

Primary chipping-orchestrator sources reviewed:

- [`README.md`](../README.md)
- [`docs/architecture.md`](../docs/architecture.md)
- [`docs/state-machine.md`](../docs/state-machine.md)
- [`docs/workflow.md`](../docs/workflow.md)
- [`docs/configuration.md`](../docs/configuration.md)
- [`docs/observability.md`](../docs/observability.md)
- [`docs/security.md`](../docs/security.md)
- [`SECURITY.md`](../SECURITY.md)
- [`pyproject.toml`](../pyproject.toml)
- [development conventions](../.agents/skills/develop/SKILL.md)
- [CI workflows](../.github/workflows/ci.yml)
- [roadmap working note](roadmap.md)

Primary AO sources reviewed at the local peer checkout:

- [`README.md`](../../agent-orchestrator/README.md)
- [`AGENTS.md`](../../agent-orchestrator/AGENTS.md)
- [`docs/STATUS.md`](../../agent-orchestrator/docs/STATUS.md)
- [`docs/architecture.md`](../../agent-orchestrator/docs/architecture.md)
- [`docs/stack.md`](../../agent-orchestrator/docs/stack.md)
- [`docs/development.md`](../../agent-orchestrator/docs/development.md)
- [`docs/telemetry.md`](../../agent-orchestrator/docs/telemetry.md)
- [reviewer isolation ADR](../../agent-orchestrator/docs/adr/0002-secure-interactive-reviewer-gateway.md)
- [LAN listener ADR](../../agent-orchestrator/docs/adr/0001-lan-listener-for-mobile.md)
- [identity-probe ADR](../../agent-orchestrator/docs/adr/0003-unauthenticated-identity-probe.md)
- [`backend/go.mod`](../../agent-orchestrator/backend/go.mod)
- [`frontend/package.json`](../../agent-orchestrator/frontend/package.json)
- [Go CI](../../agent-orchestrator/.github/workflows/go.yml)
- [frontend CI](../../agent-orchestrator/.github/workflows/frontend.yml)
- [Gitleaks CI](../../agent-orchestrator/.github/workflows/gitleaks.yml)
- [Electron renderer configuration](../../agent-orchestrator/frontend/vite.renderer.config.ts)
- [runtime environment implementation](../../agent-orchestrator/backend/internal/adapters/runtime/tmux/tmux.go)
