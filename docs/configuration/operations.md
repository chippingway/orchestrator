# Operations

How the orchestrator is checked, launched, supervised, and reconfigured: what continuous integration enforces on
every push, the run modes the polling loop starts under, the systemd user service that supervises it in production,
and when an edited `.env` takes effect. The environment-variable reference these procedures apply to is in
[`../configuration.md`](../configuration.md), which also routes to the observability settings beside this page.

## Continuous integration

[`../../.github/workflows/ci.yml`](../../.github/workflows/ci.yml) runs `ruff check orchestrator tests`,
`flake8 orchestrator tests --select=WPS`, and `pytest tests` as three separate mandatory steps on Python 3.12 for
every push to `main` and every pull request, installing from the committed [`../../uv.lock`](../../uv.lock) via
`uv sync --locked`.
Ruff rules live in [`../../pyproject.toml`](../../pyproject.toml) under `[tool.ruff.lint]`; WPS is selected inline so
Flake8 does not duplicate Ruff's checks; dev tools are declared in `[dependency-groups]`. The only on-disk Flake8
config is [`../../.flake8`](../../.flake8), which scopes `WPS412` and `WPS410` per-file ignores to
`orchestrator/config/__init__.py` because the package initializer deliberately invokes the `environment` resolver and
binds its results at import time (so a reload re-runs resolution) and publishes its narrow public surface through an
explicit `__all__` there.

The agents package adds a second scope: `orchestrator/agents/__init__.py` (`WPS412`, `WPS410`) is the API an agent run
is driven through. It re-exports the model types, the runner owner's `run_agent`, and the process owner's
`terminate_all_running`, and publishes that narrow public surface through an explicit `__all__` (`WPS410`); `run_agent`
reaches the `agents.backends` command modules (`codex`, `claude`) directly at dispatch time, so nothing private is
published above them. `WPS412` is waived for that import-time logic.

The github package adds a third scope: `orchestrator/github/__init__.py` (`WPS412`, `WPS410`) re-exports the composed
`GitHubClient` and the pinned durable-state model from their owner modules and publishes that narrow public surface
through an explicit `__all__` (`WPS410`); every other GitHub surface — labels, events, issues, pull requests, reviews,
checks — is imported from its owner directly, so nothing private is published above them. `WPS412` is waived for that
import-time logic.

The scheduler package adds a fourth scope: `orchestrator/scheduler/__init__.py` (`WPS412`, `WPS410`) re-exports the
concrete `IssueScheduler` from the `service` owner and the caller-facing `SubmissionRequest` from the `models` owner,
and publishes that narrow public surface through an explicit `__all__` (`WPS410`); the layers the scheduler is composed
from stay private to `service`, so nothing private is published above them. `WPS412` is waived for that import-time
logic.

The workflow package adds another: `orchestrator/workflow/__init__.py` (`WPS412`, `WPS410`) is the package API. It
re-exports five names from the `state` owner beside it — the `WorkflowLabel` / `ControlLabel` vocabularies, the
`guard_transition` write guard and the `is_allowed_transition` predicate under it, and the `IllegalTransition` an
illegal write raises — and defines the per-repo `tick` entry point, publishing all six through an explicit `__all__`
(`WPS410`). `tick` resolves `workflow/engine/tick.py` inside the call rather than binding it at module scope: the
GitHub and git layers import `workflow/state.py` beside this initializer for the label vocabulary they are typed by,
and a submodule import runs the initializer first, so an engine import here would route them back into the modules
they are still initializing. `WPS412` is waived for that import-time logic. Two more scopes are the `observability/`
publishers — the usage parsers and the analytics recorders — waived on the same grounds.

The eighth scope fronts no owner at all: `orchestrator/__init__.py` (`WPS412`, `WPS410`) is the whole of the
root package. It declares the distribution version and the explicit `__all__` naming it and binds nothing else, so
`import orchestrator` costs that module and no owner behind it. Both names are module-level metadata (`WPS410`) and
both assignments read as logic in an initializer (`WPS412`), so each rule is waived there.

Those eight are the whole publishing set: every other initializer in the tree imports nothing at all, so naming one of
those packages loads no owner behind it and the submodules that show up on it are what other modules' imports planted.
`tests/repository/test_package_exports.py` reads each initializer's source for that half — an eager sibling import is
invisible in the namespace, which holds the same submodule either way — and compares the packages carrying an
`__all__` against the list above, so a ninth publisher is a deliberate edit here and a scope in
[`../../.flake8`](../../.flake8) rather than a silent widening of what a package answers for.

`orchestrator/github/pull_requests.py` (`WPS214`) owns the whole pull-request surface — branch/base lookup, creation,
comments, labeling, retrieval, the SHA-pinned merge, and the head-branch delete — so its client mixin carries 8
methods past the ceiling of 7. Splitting the merge-side mutations out would hand the composed client two mixins for
one owner, so the method count is waived there instead.

Ruff and the line-length test enforce a repository-wide 120-column target set once as `line-length` under
`[tool.ruff]` in [`../../pyproject.toml`](../../pyproject.toml). Ruff applies it to Python via the opted-in `E501`
rule; the first-party
[`../../tests/repository/test_line_length.py`](../../tests/repository/test_line_length.py) reads the same value and
applies it to tracked Markdown/text files, exempting fenced code blocks, single unbreakable tokens (e.g. long URLs),
binary assets, the lockfile, and the verbatim `LICENSE`.

The workflow declares `permissions: contents: read` so the run's `GITHUB_TOKEN` is read-only and cannot publish
artifacts, push tags, or comment on PRs. The job uses no repository secrets, so PRs from forks run safely under the same
scope.

[`../../.github/dependabot.yml`](../../.github/dependabot.yml) opens weekly update PRs for the `github-actions` and `uv`
(Python `pyproject.toml` + `uv.lock`) ecosystems with a 30-day `cooldown.default-days` window. Each entry declares the
service labels GitHub stamps on the PRs it opens: `workflow:dependencies` on every update PR, so the whole dependency
queue is one label filter, plus `workflow:github_actions` or `workflow:python:uv` naming which ecosystem moved. Those
three share the `workflow:` prefix with the labels the orchestrator writes but are not workflow states — nothing in
the tree reads them, so a PR carrying one is not an issue in a stage. `github-actions` and `uv` above name the
ecosystems Dependabot updates, not labels.
[`../../.github/workflows/dependency-review.yml`](../../.github/workflows/dependency-review.yml) runs
`actions/dependency-review-action` on every PR and fails the check when a PR introduces a vulnerable or non-compliant
dependency.

## Run modes

- `./run.sh` — production. Continuous polling. `run.sh` does `git pull --ff-only origin "$ORCHESTRATOR_BASE_BRANCH"`
  (read from `.env`, default `main`) and re-launches the orchestrator after each clean exit, so a self-modifying merge
  picks up new code automatically. If a non-base branch is checked out the pull is skipped, and if the fast-forward
  fails (diverged base, rebase in progress, network error) the wrapper logs a loud warning to stderr and launches the
  existing working tree anyway instead of exiting — under `Restart=always` a stale-but-running orchestrator beats a
  silent crash loop. See [`../architecture.md#process-model`](../architecture.md#process-model) for the full
  skip-and-warn contract.

  Ctrl+C (or `SIGTERM`) stops the wrapper: the orchestrator exits with `128 + signum` and `run.sh` skips the restart
  loop. A second Ctrl+C terminates immediately.
- `python -m orchestrator --once` — single tick then exit. Useful for tests and debugging.
- `python -m orchestrator --log-level DEBUG` — verbose logs.

Both forms above call `orchestrator/cli.py`, which is also what the `agent-orchestrator` console script declared in
[`../../pyproject.toml`](../../pyproject.toml) runs (`uv run agent-orchestrator --once`). The module form is what
`run.sh` launches and what the systemd unit below therefore supervises; the console script is the equivalent for an
install that has the project on its `PATH`.

On first start the orchestrator creates the workflow labels and the `backlog` / `paused` /
`workflow:community_contribution` control labels on the repo, then begins polling open issues every `POLL_INTERVAL`
seconds. On a repo it drove before the labels were namespaced, each pre-namespace label is renamed in place instead.

## Running under systemd (user service)

`run.sh` does not survive a reboot, a `tty` logout, or the user manager being torn down. The recommended production
deployment is a systemd **user** service that supervises `run.sh` directly.

A detached `screen` / `tmux` session wrapped in a `Type=forking` unit looks similar but is the wrong shape: systemd ends
up supervising `screen`, not the orchestrator; `ExecStop` races the screen session's own lifecycle; logs split; and the
unit silently does nothing at boot unless linger is enabled. Keep `screen` / `tmux` for interactive debugging.

### Unit file

Drop this at `~/.config/systemd/user/agent.service`, replacing the working directory and the `PATH` entries:

```ini
[Unit]
Description=Agent orchestrator
After=network-online.target

[Service]
Type=simple
WorkingDirectory=/path/to/agent-orchestrator
ExecStart=/path/to/agent-orchestrator/run.sh
Restart=always
RestartSec=5
Environment=PATH=/home/<user>/.local/bin:/usr/local/bin:/usr/bin:/bin

[Install]
WantedBy=default.target
```

- `Type=simple` because `run.sh` stays in the foreground — systemd tracks the wrapper PID, and `SIGTERM` from
  `systemctl stop` propagates to the wrapper, then to the orchestrator (exit `143`, no restart loop).
- `Restart=always` covers machine-level events (reboot, OOM, host crash). Application-level self-restart after a
  self-modifying merge is still handled inside `run.sh`.
- A non-interactive systemd service does not inherit your shell's `PATH`. If `codex` or `claude` lives under
  `~/.local/bin`, add it to `Environment=PATH=…`, or set `CODEX_BIN` / `CLAUDE_BIN` to absolute paths via additional
  `Environment=` lines.

### Enabling

```sh
systemctl --user daemon-reload
systemctl --user enable --now agent.service
loginctl enable-linger <user>
```

`enable-linger` is **required for boot-time start**: without it the per-user systemd manager only runs while the user
has an active login session.

### Operating

```sh
systemctl --user status agent.service        # current state and last log lines
systemctl --user restart agent.service       # bounce the orchestrator
systemctl --user stop agent.service          # SIGTERM the wrapper (exits 143, no restart)
journalctl --user-unit agent.service -f      # tail the wrapper's stdout/stderr
```

systemd's journal captures `run.sh` and orchestrator stdout/stderr (process lifecycle, exit codes, restart messages).
The orchestrator's own structured log lives at `logs/orchestrator.log` under `WorkingDirectory` (rotated, ~10 MiB × 5).
Check the journal first for "did it start / did it die", then `logs/orchestrator.log` for per-issue handler detail.

## Reclaiming what a split leaves on the remote

An issue whose committed implementation is adjudicated as a split leaves two things on the target repository: the
branch its superseded candidate was committed on, and an immutable snapshot ref under
`refs/orchestrator/late-split/issue-<n>/cycle-<c>/gen-<g>` holding the exact commit its children were told to reuse.
Both are recorded on the issue's own pinned obligation ledger, and the orchestrator reclaims them itself — there is
no TTL and no background garbage collection. Three passes do it, and between them every live ledger stays visited:

- the **umbrella's terminal**, which settles what is owed before it closes the parent (see
  [`../state-machine/delivery-stages.md`](../state-machine/delivery-stages.md#_handle_umbrella-label-workflowumbrella));
- the **umbrella's park**, on the way out of the two dispositions that stop the parent for a human — a child
  `rejected`, or one closed without reaching a terminal label. Both closed the child, which is the reading the rule
  takes, so the ledger is settled from the same scan that parked the parent; the park itself is unchanged and no
  terminal is decided. Nothing else revisits an issue parked this way, which is why it happens here;
- the **closed-owner cleanup sweep**, for an issue a human closed mid-cycle while it still carried
  `workflow:decomposing` or `workflow:umbrella` (see
  [`../state-machine/delivery-stages.md`](../state-machine/delivery-stages.md#closed-owner-cleanup-sweep-no-label-of-its-own)).

The sweep runs on the existing `CLOSED_ISSUE_SWEEP_EVERY_N_TICKS` cadence and adds no per-tick traffic of its own, so
raising that knob (the multi-repo rate-limit advice in
[`../configuration.md`](../configuration.md#github-rate-limits)) also stretches how long an unreclaimed branch or ref
survives, by the same factor. It is cleanup-only: it never spawns an agent, resumes a workflow, activates a child, or
changes a label.

**What to look at when something is not going away.** Three signals, and they mean different things:

- A `late_failure` carrying `snapshot_delete_failed` or `branch_cleanup_failed`, repeated on the same issue (see
  [`../observability/event-streams.md`](../observability/event-streams.md#late-split-records-both-sinks)), together
  with an umbrella that will not close, or a closed owner that keeps its label. The remote **refused** the delete.
  That is a permission or ruleset problem — a protected-ref rule over `refs/orchestrator/*`, or a token that lost
  push scope — and only an operator can clear it. Nothing is retried into success meanwhile; the retry itself is
  every visit.
- A snapshot ref that is simply still there, with no failure recorded, and an umbrella that will not close. It is
  **retained** on purpose: a ref is kept until every recorded direct consumer has ended — which means the consumer's
  issue is *closed*, since reaching `done`, being `rejected`, and a human closing it all close it, and reopening
  leaves the label where it was. Those readings are taken fresh on every visit rather than latched, and every
  obligation that is not `reconciled` holds the owner's terminal, so the umbrella stays open and logs what it is
  waiting for on each tick. A child that stays open forever keeps its ancestor's ref forever, which is the
  deliberate trade — invalidating a live child's only copy of the work it was told to reuse is worse. Closing (or
  finishing) the child is what lets both go.
- A `late_cleanup` carrying `outcome: reclaiming`, and an umbrella that will not close over a ref that is already
  **gone**. That state is progress, not failure: the decision is written down before the delete, so an entry left in
  it is one whose delete landed while a child it owes a receipt could not be reached. Every obligation short of
  `reconciled` holds the terminal, so the parent stays open until the next visit finishes the telling — which it
  does by finding the ref absent, which counts as reclaimed, and then saying so to the children that were missed. A
  child that stays unreachable is the one case that repeats, and the log line names it on every visit.

To list what a repository is holding:

```sh
git ls-remote origin 'refs/orchestrator/late-split/*'
```

Deleting one by hand is safe once you are sure no child still needs it, and it does not strand the ledger: an absent
ref counts as a successful reclamation, so the entry reconciles on the next visit at the cost of one read.

Do **not** recreate a ref the orchestrator has already reclaimed. Its value was that it provably carried one exact
commit, and a ref pushed again from whatever is reachable now proves nothing. The orchestrator does not do it either,
and it makes sure nothing resumes against one:

- **As the ref goes, each child cut from it gets one comment** saying so, carrying a hidden marker naming the owner,
  cycle, and generation so it is said once. That is *all* the owner does to a child. It never edits a child's pinned
  comment: that comment is written whole by whoever writes it, and a handler of the child's own that read it first
  and wrote it after would silently undo the edit — so the receipt is an appended comment, which nothing can lose.
- **The child refuses the work itself, at its own dispatch.** Before any handler runs, an issue whose recorded
  ancestry still names a snapshot looks for that receipt on its own thread — marked with the owner, cycle, and
  generation it was born of, and authored by the orchestrator — and refuses if it finds one. That answer is
  authoritative: it says the reclamation *happened*, which no later look at the ref can contradict. A thread the
  tick could not *read* is not a thread with no receipt on it, and stops the dispatch there rather than falling
  through to readings a receipt would have overruled.
- **Where the thread answered and carries none, the ref itself decides**, and its three answers are three different
  outcomes. Gone → park. Still there under **another commit** → park too, under `late_snapshot_repointed`: the name
  survived and what it stood for did not, and nothing here re-points or deletes that ref. Unreachable → the dispatch
  is *held* for the next tick, with nothing written, because an outage is evidence of nothing. A park drops the
  dangling pointer, marks the issue `awaiting_human`, and returns before the label's handler is reached — including
  for a reopened `done` / `rejected` child, which is otherwise a dispatch no-op.
- **The steady state costs nothing on the wire.** The ref reading asks this host's own copy first, and a reclamation
  takes that copy down *before* it touches the remote ref — refusing the whole reclamation if it cannot prove the
  copy gone — so a copy still here means nothing has been reclaimed. It is read for the exact commit it carries,
  since it lives in the object store the agents' own worktrees share, and it is trusted only for a pointer this
  binary wrote (children created before that ordering existed pay one `ls-remote` instead).

  A child the split recorded but never managed to seed — an ancestry write that failed after the issue existed —
  carries the split's marker in its **body**, and that marker is corroborated rather than believed: the owner's own
  generation is read fresh and has to name the same cycle and generation and carry this issue among its recorded
  consumers. Vouched, it hands over the ref *and* the commit the owner preserved, and the same three answers follow.
  Unvouched, the guard steps aside — a marker anyone can paste into a body parks nobody. Unreadable, opaque, or
  naming no candidate, the dispatch is held.

  This is also why deleting a snapshot ref by hand is not the same as the orchestrator reclaiming one: no receipt is
  written, so the children are never told — and on the host that already fetched the ref, its own copy is still
  there and is what a child reads first, so that child goes on working from the candidate until the copy goes too.

Continuing after such a park means either implementing the issue as an ordinary change or starting an explicit new
split cycle on the owner, which preserves a candidate of its own.

## Applying `.env` changes

`.env` is read once, when `python -m orchestrator` starts. The orchestrator process never reloads it, so most edits
take effect on the **next fresh Python start** — there is no signal to make a running process re-read configuration.
`run.sh` is the usual restart mechanism: each loop iteration launches a new Python process (and `git pull --ff-only`s
the orchestrator checkout to `ORCHESTRATOR_BASE_BRANCH` along the way).

### What survives a restart

Per-issue progress lives in the issue's pinned JSON comment on GitHub and in the per-issue worktree on disk. Restarting
between ticks loses nothing — the next tick picks each issue back up from its label and pinned state. Two restart-time
hazards are worth knowing:

- **A live `codex` / `claude` child.** Stage handlers spawn agent subprocesses that may run for as long as
  `AGENT_TIMEOUT`. On a SIGTERM/SIGINT stop the loop terminates in-flight agent process groups up front (and, as a hard
  backstop, the shutdown watchdog force-terminates them after `SHUTDOWN_GRACE_SECONDS` and exits), so the process leaves
  within the grace window instead of holding open for up to `AGENT_TIMEOUT` and being SIGKILLed at the systemd stop
  deadline. The interrupted child is still killed mid-session. The runner flags such a run `interrupted` (distinct from
  `timed_out`), and every dev-resume stage handler (`implementing`, `validating`, `fixing`, `documenting`, `in_review`,
  `resolving_conflict`) short-circuits on it — they ignore the partial result and leave durable GitHub state
  untouched, so the next process retries the resume from scratch rather than parking on `awaiting_human` or routing
  through timeout recovery. A dirty worktree may still remain on disk for the next tick to reconcile.
- **In-flight agent spec is pinned.** When a `codex` / `claude` session starts, the orchestrator writes the full
  `DEV_AGENT` / `DECOMPOSE_AGENT` spec into pinned state and re-parses it (not the current `.env`) on every resume.
  Flipping `DEV_AGENT` or `DECOMPOSE_AGENT` after a session is locked does nothing for that issue until it reaches
  `done` or `rejected`. The question and discussion stages each seed from `DECOMPOSE_AGENT` on their own first spawn
  and pin to `question_agent` / `discussion_agent` for the rest of that conversation. `REVIEW_AGENT` is not pinned —
  the reviewer spawns fresh each round.

### Safe restart guidance

- **Idle / between ticks — safe.** Restart freely; the next tick resumes from GitHub state.
- **Issue mid-stage with no agent child — generally safe.** Workflow state is on GitHub and in the worktree.
- **Live `codex` / `claude` child — avoid.** Wait for the agent to exit. Forcing a restart can park the issue or leave
  a dirty worktree behind.

Useful inspection commands:

```sh
pgrep -af 'python -m orchestrator|codex|claude|run.sh'
tail -f logs/orchestrator.log
journalctl --user -u agent.service -f   # systemd users
```

### Per launch style

**Foreground terminal (`./run.sh` in a shell).**

1. Edit `.env`.
2. Confirm no agent child is running (`pgrep -af 'codex|claude'`).
3. Ctrl+C the terminal (`run.sh` exits with code 130 and skips the restart loop).
4. Re-run `./run.sh`.

A second Ctrl+C while `run.sh` is mid-shutdown terminates immediately.

**`tmux` / `screen` session.**

1. Attach (`tmux attach -t orchestrator`, or `screen -r`).
2. Check live output for an in-flight stage handler; cross-check with `pgrep -af 'codex|claude'`.
3. At a safe point, Ctrl+C the orchestrator and re-run `./run.sh`.
4. Detach (Ctrl+B then D for tmux, Ctrl+A then D for screen).

**systemd user service.**

1. Edit `.env` in the unit's `WorkingDirectory=`.
2. **Skip `systemctl --user daemon-reload`** unless the `.service` unit file itself changed — `daemon-reload` reloads
   unit definitions, not `.env`.
3. When safe (no live agent child), `systemctl --user restart agent.service`.
4. Tail logs: `journalctl --user -u agent.service -f`.

When `GITHUB_TOKEN` is supplied via the unit's `EnvironmentFile=`, edit that file and restart the service. When the
token is hard-coded in an inline `Environment=` line, changing the value requires editing the unit *and* a
`daemon-reload` before the restart.

**Direct `python -m orchestrator --once`.**

Each `--once` invocation is a fresh Python process and reads the current `.env` on every call.

### Setting-by-setting expectations

When each setting's change takes effect:

- `POLL_INTERVAL`, `AGENT_TIMEOUT`, `REVIEW_TIMEOUT`, `SHUTDOWN_GRACE_SECONDS`, `MAX_REVIEW_ROUNDS`,
  `MAX_CONFLICT_ROUNDS`, `MAX_RETRIES_PER_DAY`, `MAX_ADDED_LINES`, `DEV_SESSION_MAX_RESUMES`,
  `IN_REVIEW_DEBOUNCE_SECONDS`, `DECOMPOSE`,
  `SQUASH_ON_APPROVAL`, `EXPOSE_TRACKED_REPOS`, `VERIFY_COMMANDS`, `VERIFY_TIMEOUT`, `LOG_DIR`, `EVENT_LOG_PATH`,
  `ANALYTICS_LOG_PATH`, `ANALYTICS_RETENTION_DAYS`, `TRACK_SKILL_TRIGGERS`, `TRAJECTORY_LOG_PATH`,
  `TRAJECTORY_RETENTION_DAYS`, `REPO` / `REPOS` / `TARGET_REPO_ROOT` / `BASE_BRANCH` / `REMOTE_NAME`, `HITL_HANDLE`,
  `ALLOWED_ISSUE_AUTHORS` — next Python start
- `ANALYTICS_DB_URL` — next `python -m orchestrator.observability.analytics.sync.cli` invocation, and next
  `uv run streamlit run orchestrator/apps/analytics_dashboard.py` start (the value is parsed once, when the analytics
  settings holder is first imported, so a browser reload is not enough — relaunch Streamlit). The polling loop does not
  read this setting.
- `DASHBOARD_PARALLEL_READS` — next `uv run streamlit run orchestrator/apps/analytics_dashboard.py` start. Parsed once
  per process, on the first render's import of the read-mode owner.
- `MAX_PARALLEL_ISSUES_PER_REPO`, `MAX_PARALLEL_ISSUES_GLOBAL` — next Python start. Per-`REPOS` `parallel_limit`
  overrides take precedence over `MAX_PARALLEL_ISSUES_PER_REPO`.
- `WORKFLOW_TRANSITION_GUARD` — next Python start (parsed at config import).
- `DEV_AGENT`, `DECOMPOSE_AGENT` — next Python start, **except** for issues whose pinned state already names a
  `dev_agent` / `decomposer_agent` / `question_agent` / `discussion_agent` — those keep the pinned spec until the
  issue reaches `done` or `rejected`
- `REVIEW_AGENT` — next reviewer spawn after the next Python start (not pinned per issue)
- `GITHUB_TOKEN` — not loaded from `.env`. Update the process environment or rewrite the file at
  `ORCHESTRATOR_TOKEN_FILE` (default `~/.config/<owner>/<repo>/token`) before the next start
- `ORCHESTRATOR_BASE_BRANCH` — `run.sh` captures this once before its restart loop, so editing it only takes effect
  after `run.sh` itself is restarted. The Python process picks it up on the same next start.
