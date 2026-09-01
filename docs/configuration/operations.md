# Operations

How the orchestrator is checked, launched, supervised, and reconfigured: what continuous integration enforces on
every push, the run modes the polling loop starts under, the systemd user service that supervises it in production,
and when an edited `.env` takes effect. The environment-variable reference these procedures apply to is in
[`../configuration.md`](../configuration.md), which also routes to the observability settings beside this page.

## Continuous integration

[`../../.github/workflows/ci.yml`](../../.github/workflows/ci.yml) runs `ruff check orchestrator tests`,
`flake8 orchestrator tests --select=WPS`, `pytest tests --cov=orchestrator --cov-report=term-missing`, `uv build`, and
a launch of the console script from the wheel that build produced, as five separate mandatory steps for every push to
`main` and every pull request, installing from the committed [`../../uv.lock`](../../uv.lock) via `uv sync --locked`.
The pytest step prints coverage and missing lines for visibility but sets no minimum threshold.

The job is a two-leg matrix: that whole set runs once on Python 3.12 and once on Python 3.13. Those two are the
versions a run proves, not the whole of what [`../../pyproject.toml`](../../pyproject.toml) admits —
`requires-python = ">=3.12"` names a floor and no ceiling, so 3.14 and everything after it installs without CI having
run a line under it, and 3.12 is checked because it is the floor an installer reads. Both legs install the same pins
from the same lockfile — one resolution serves both, so neither leg needs a version of its own — and each names its
interpreter with `uv sync --locked --python <version>` rather than letting uv pick a compatible one off the runner,
which is what keeps a leg from reporting green for a version it never ran. `fail-fast: false` leaves the other leg
running when one fails, so a failure that belongs to one interpreter is reported as one instead of cancelling the
evidence that it does not belong to the other. A matrix leg carries its value in the check name, so the two report as
`ci (3.12)` and `ci (3.13)`, and those two names — not a bare `ci` — are what a branch-protection rule has to
require ([`../security.md#required-checks`](../security.md#required-checks)).

The last two steps are about the distribution rather than the tree. `uv build` builds the sdist and, from it, the
wheel; the step after installs that wheel into an environment created for it alone —
`uv run --no-project --isolated --python <version> --with <wheel> chipping-orchestrator --help` — and requires the
console script to exit successfully from there. `uv sync` above installs this project into `.venv` as an editable
install, so the console script does exist by then, but it reaches the package through the source tree and nothing
before this step reads what the build backend packaged. A wheel that ships no `orchestrator` package — the flat layout
is declared explicitly under `[tool.hatch.build.targets.wheel]` for that reason — an entry point naming a module the
wheel does not carry, or a runtime dependency supplied by the lockfile but omitted from `[project.dependencies]`,
passes every other step and fails for the first person to install the distribution. `--no-project` and `--isolated`
are what keep the answer honest: neither the project environment nor the lockfile is on the path the script imports
from. What answers `--help` is the wheel's own contents beside the dependencies it declares for itself, resolved fresh
from PyPI, which is the reading an installer of this distribution gets rather than the one `uv.lock` settles.

The job declares `timeout-minutes: 20`, generous next to the few minutes a green run takes and far under the six-hour
default GitHub would otherwise cancel it at; the reasoning that ceiling serves is the same one the scans below are
bounded by. The workflow also declares a `concurrency` group of
`${{ github.workflow }}-${{ github.event_name == 'pull_request' && github.ref || github.run_id }}` with
`cancel-in-progress: ${{ github.event_name == 'pull_request' }}`. A pull request runs in a lane per ref, and a second
push cancels the run its own earlier push started rather than leaving two runs racing for a runner and reporting
checks against a commit nobody is reviewing. Every other run — a push to `main` above all — is keyed on its own run
id, so it shares a group with nothing. That, rather than the flag, is what makes those runs uncancellable:
`cancel-in-progress: false` protects a run that has started, but GitHub keeps at most one pending run per group and
cancels the one each newcomer replaces, so under a shared group a third push would evict a queued `main` run while the
first still held the runner. A run on `main` is the record of what that commit does, and no later push may erase it,
waiting or started.
[`../../tests/repository/test_ci_workflow.py`](../../tests/repository/test_ci_workflow.py) holds that concurrency
block, the interpreter matrix and its floor against `requires-python`, the packaging steps, and this page's versions
against the matrix that proves them.

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

`[tool.ruff.lint.per-file-ignores]` in that same file carries one waiver, `PLC0414`, over six exact paths. The rule
reports `import X as X`, which is the spelling `F401` is answered with here: a name aliased to itself is a re-export
both Ruff and a reader can see, and the import that drops the alias reads as dead. Only one of the six is nothing but
a facade: `orchestrator/observability/dashboard/theme.py` implements nothing and reads the five style owners back
under one name, which is the theme object a dashboard page hands every panel. The other five seed and drive a stage's
scenarios and carry the re-export beside that work — the types, the mid-run effects, and the publication heads a
sibling test module reads a case back through, bound there and read only there. A waiver covers the whole file rather
than the import that earned it, so what holds the rest of the file to the rule is the check below rather than the
entry. `PLC0414` sits outside the selected set CI runs, so those entries answer the audit that opts into it
(`ruff check orchestrator tests --select=PLC0414`) rather than the default run; a package initializer needs no entry,
because Ruff never reports the rule there. Each key is an exact path rather than a glob, and
[`../../tests/repository/test_reexport_aliases.py`](../../tests/repository/test_reexport_aliases.py) holds the list
against the tree: a self-alias in a module the list does not name, one on a name its own module already reads, or a
key that globs fails there.

`BLE001` is answered a line at a time instead. The rule reports a blanket `except Exception` / `except BaseException`,
and like `PLC0414` it sits outside the selected set, so the audit that opts into it
(`ruff check orchestrator tests --select=BLE001`) is what the answers are written for. No per-file entry would fit:
what earns a waiver is one handler rather than the file around it, so each carries an inline
`# noqa: BLE001 - <reason>` naming what its blanket catch protects, and every other handler beside it stays held to
the rule. Three families earn one. The GitHub-API calls — the best-effort PR notices, the issue and pull-request
reads, and the child-issue create under `orchestrator/git/base_sync/` and `orchestrator/workflow/` — catch blind
because PyGithub raises its own `GithubException` and the transport errors underneath it alike, and a narrower
handler would turn a connection reset into a stranded run. The fail-open guards under
`orchestrator/observability/analytics/` and in `orchestrator/workflow/late_split/telemetry.py` catch blind so a parser
bug or an unwritable sink costs the record and never the tick that produced it. And two test helpers keep whatever
escapes a worker thread so the main thread can assert on it. Ruff exempts a blind handler that reports through a
logger it can resolve back to `logging` itself, which is why a guard logging through an imported `log` carries a
directive where the identical one beside its own `getLogger` call does not.

The CI workflow declares `permissions: contents: read` so the run's `GITHUB_TOKEN` is read-only and cannot publish
artifacts, push tags, or comment on PRs. The job uses no repository secrets, so PRs from forks run safely under the same
scope.

[`../../.github/workflows/codeql.yml`](../../.github/workflows/codeql.yml) runs CodeQL's default queries against the
Python source on every push to `main`, every pull request targeting `main`, and a weekly schedule. Its one-language
matrix fixes the language at `python` and uses `build-mode: none`, so the scan analyzes source without installing or
executing the project. The workflow keeps `contents: read` as its top-level token scope; the analysis job restates it
and adds only `security-events: write`, which the CodeQL action needs to upload its results. It reads no secrets.

[`../../.github/workflows/scorecard.yml`](../../.github/workflows/scorecard.yml) runs OpenSSF Scorecard — the
supply-chain grader behind the README badge — on a weekly `schedule`, on every push to `main`, and on
`workflow_dispatch`, which is how a maintainer can prove a change to it works without waiting a week. It sets
`publish_results: true`, so a run on `main` publishes the score the badge and the public
[viewer](https://scorecard.dev/viewer/?uri=github.com/chippingway/orchestrator) read, and hands the SARIF it
produces to `github/codeql-action/upload-sarif`, which files each finding as a code-scanning alert on this repo. It
declares the same top-level `contents: read` and reads no secrets; the job adds exactly the two grants those two
publications need — `id-token: write` for the OIDC token the publication is authenticated by, and
`security-events: write` for the SARIF upload — and restates `contents: read`, because a job-level `permissions:` block
replaces the top-level one rather than adding to it. Nothing gates on the grade: a low score is a set of alerts to
triage rather than a failing run, and the workflow is outside the required checks a merge waits on
([`../security.md#required-checks`](../security.md#required-checks)).

Every `uses:` in every workflow names a full 40-character commit SHA with the release it belongs to in a trailing
comment (`uses: owner/action@<sha> # v1.2.3`), so a retagged release cannot change what a run executes.
[`../../tests/repository/test_workflow_action_pins.py`](../../tests/repository/test_workflow_action_pins.py) holds that
shape for every workflow, but nothing checks the comment against the SHA it labels, so a hand edit has to move both
together; Dependabot's `github-actions` updates rewrite the pair.

Each security scan bounds its own job the same way: 30 for the CodeQL analysis, 20 for Scorecard and the
vulnerability scan, 15 for the dependency review. A job that hangs otherwise runs until GitHub's six-hour default
cancels it, and both halves of this set pay for that wait. The dependency review is a required check and CodeQL's
findings are enforced by a ruleset ([`../security.md#required-checks`](../security.md#required-checks)), so a hung job
holds a merge for those six hours instead of failing in the minutes the scan takes. Scorecard, the vulnerability scan,
and CodeQL's scheduled pass have nobody watching, so a hung one holds a runner while reading as a scan that has yet to
report rather than as one that failed.
[`../../tests/repository/test_workflow_job_timeouts.py`](../../tests/repository/test_workflow_job_timeouts.py) holds a
declared timeout, shorter than that default, on every job in all five workflows, and holds the list it walks against
the workflow directory, so a sixth workflow arrives with a timeout rather than outside every check.

[`../../.github/dependabot.yml`](../../.github/dependabot.yml) opens weekly update PRs for the `github-actions` and `uv`
(Python `pyproject.toml` + `uv.lock`) ecosystems. For routine version updates, `github-actions` uses the ecosystem-wide
cooldown GitHub supports and holds every release for 30 days. The `uv` entry holds a major release, and anything SemVer
does not classify, for 30 days; it holds a minor or a patch for 14 days. Cooldowns do not delay security updates. The
`uv` entry additionally declares `allow:` rules, which replace Dependabot's default rule rather than extend it —
`dependency-type: direct` restates that default, and `dependency-name: gitpython` names the single transitive dependency
it is widened for, because GitPython reaches the lockfile only through Streamlit and its advisories would otherwise
leave a grouped security job with no allowed dependency to update. Each entry also declares the service labels GitHub
stamps on the PRs it opens:
`workflow:dependencies` on every update PR, so the whole dependency queue is one label filter, plus
`workflow:github_actions` or `workflow:python:uv` naming which ecosystem moved. Those three share the `workflow:`
prefix with the labels the orchestrator writes but are not workflow states — nothing in the tree reads them, so a PR
carrying one is not an issue in a stage. `github-actions` and `uv` above name the ecosystems Dependabot updates, not
labels. [`../../tests/repository/test_dependabot_config.py`](../../tests/repository/test_dependabot_config.py) holds
the cooldown policies, the allow rules, and the labels against what the config declares.
[`../../.github/workflows/dependency-review.yml`](../../.github/workflows/dependency-review.yml) runs
`actions/dependency-review-action` on every PR and fails the check when a PR introduces a vulnerable or non-compliant
dependency.

[`../../.github/workflows/vulnerability-scan.yml`](../../.github/workflows/vulnerability-scan.yml) is the standing
scan beside that diff gate: a weekly `schedule` plus `workflow_dispatch`, the second so an edit to it is verifiable
from the Actions tab instead of a week away. It exports the pins from [`../../uv.lock`](../../uv.lock) with
`uv export --locked --all-groups --no-emit-project`, then audits them with `pip-audit` and fails the job when a
published advisory names one of them. Why the export and the audit are shaped that way:

- **`--all-groups`** covers the `dashboard` group as well as the runtime and `dev` ones, so the audit is the whole
  lockfile rather than the subset a default `uv sync --locked` installs.
- **Environment markers are stripped** from the export before the audit. A pin kept for another platform
  (`colorama` under Windows, `tzdata`) is a version this repository still ships, and an audit reading markers would
  skip it as inapplicable to the Linux runner — silently, and while reporting success.
- **The scanner is CI-only.** `uvx` runs `pip-audit` from a throwaway environment, so it audits the pins without
  becoming one: it appears in neither [`../../pyproject.toml`](../../pyproject.toml) nor the lockfile, and the
  version range there is what keeps a new major from changing the CLI under the job.
- **`--no-deps --disable-pip` and `--strict`.** The exported versions are already the complete pinned set, and the
  two collection flags are what have `pip-audit` read them as written. `--no-deps` on its own still hands the file to
  pip's resolver and audits whatever that resolves to — a fresh resolution, which is the step the lockfile exists to
  settle. `--strict` closes the one hole left in that reading: a pin PyPI has no record of is otherwise skipped and
  reported under a green run, while a line carrying no exact version fails the job with or without it. Neither flag
  is a claim about the advisory data — a service that errors out fails the run on its own, and a pin no advisory
  names is simply a clean result.

The job declares the same `permissions: contents: read` and uses no secrets. It is not a required check and cannot
be one — it never runs on a pull request — so a red run is triaged from the Actions tab. Turning one of its findings
into a bump PR is Dependabot's job, which is why enabling Dependabot security updates is on the operator list in
[`../security.md#dependabot-security-updates`](../security.md#dependabot-security-updates). The audit reads the whole
lockfile while those updates reach only what the `allow:` rules above name, so a finding against a transitive pin
those rules do not name is cleared by widening them or by hand rather than by waiting for a PR.

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

Both forms above call `orchestrator/cli.py`, which is also what the `chipping-orchestrator` console script declared in
[`../../pyproject.toml`](../../pyproject.toml) runs (`uv run chipping-orchestrator --once`). The module form is what
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

Drop this at `~/.config/systemd/user/orchestrator.service`, replacing the working directory and the `PATH` entries:

```ini
[Unit]
Description=chipping-orchestrator
After=network-online.target

[Service]
Type=simple
WorkingDirectory=/path/to/chipping-orchestrator
ExecStart=/path/to/chipping-orchestrator/run.sh
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
systemctl --user enable --now orchestrator.service
loginctl enable-linger <user>
```

`enable-linger` is **required for boot-time start**: without it the per-user systemd manager only runs while the user
has an active login session.

### Operating

```sh
systemctl --user status orchestrator.service        # current state and last log lines
systemctl --user restart orchestrator.service       # bounce the orchestrator
systemctl --user stop orchestrator.service          # SIGTERM the wrapper (exits 143, no restart)
journalctl --user-unit orchestrator.service -f      # tail the wrapper's stdout/stderr
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
  `workflow:decomposing` or `workflow:umbrella` — or `workflow:ready` / `workflow:blocked`, where a decomposition
  outcome that landed after the close can leave an ending nothing else would find (see
  [`../state-machine/delivery-stages.md`](../state-machine/delivery-stages.md#closed-owner-cleanup-sweep-no-label-of-its-own)).

The sweep runs on the existing `CLOSED_ISSUE_SWEEP_EVERY_N_TICKS` cadence and adds no per-tick traffic of its own, so
raising that knob (the multi-repo rate-limit advice in
[`../configuration.md`](../configuration.md#github-rate-limits)) also stretches how long an unreclaimed branch or ref
survives, by the same factor. It is cleanup-only: it never spawns an agent, resumes a workflow, activates a child, or
touches one that already exists. It does end the cycle the close interrupted — the cancellation is marked, any pull
request that cycle was holding is closed over one notice, and the issue moves to `rejected` once nothing is owed. That
last write is the only label it makes, and it is also what stops the sweep: an owner still owing the remote keeps its
label and keeps being visited, so a repository whose closed owners stay on `workflow:decomposing` or
`workflow:umbrella` is a repository with something the orchestrator could not reclaim.

Reopening such an owner does not get the workflow going again. The same cleanup runs from the dispatcher instead,
once per tick, the issue reaches no stage handler, and the same `rejected` is written once the ledger settles —
each held tick logs a warning naming what is still owed. Clearing the refusal is clearing the obligation; starting
a fresh attempt afterwards is removing `rejected`, which is the handshake below.

### Rolling back to an older orchestrator

The late generation an oversized candidate is adjudicated under lives in additive `late_*` fields on the issue's own
pinned comment. An orchestrator that predates them ignores those fields entirely, which is safe for an issue that
never entered the size gate and **not** safe for one currently in it: the older binary would read a
`workflow:decomposing` issue carrying a frozen candidate as one waiting to be decomposed, spawn the initial
decomposer against it, and decide the size question by not asking it. The same holds for an issue whose ledger still
records a snapshot ref or a superseded branch — nothing in the older binary reclaims either.

So a rollback is drained rather than cut over. Set `DECOMPOSE=off` and restart, which stops new candidates entering
the gate while every recorded generation goes on being adjudicated, cancelled, cleaned up, and restarted. Then wait
for **both** halves of the drain, because they end at different times:

- **No open issue carries `late_cycle_id`** in its pinned comment. That is the adjudication half — a cycle still
  deciding, revising, or splitting.
- **No CLOSED issue carries an unsettled `late_resources` ledger**, on any of the four labels the cleanup sweep
  visits. A closed owner is exactly the case the first check cannot see: its cycle was ended by the close, and what
  is left is the sweep reclaiming the superseded branch and the snapshot ref its children were cut from, at the
  `CLOSED_ISSUE_SWEEP_EVERY_N_TICKS` cadence rather than every tick. Deploying the older binary over one abandons
  precisely the resources the paragraph above says nothing else reclaims. A ledger is settled when every entry reads
  `reconciled`; a `retained` ref (its consumers are still live) is **not** settled and is the one state that can take
  arbitrarily long, since it waits on issues that are still being worked.

The section above lists the ref namespace and the `git ls-remote` that shows what is still out there, which is the
direct check when a pinned comment is ambiguous. An issue that has to be parked mid-cycle instead is closed, which
ends its cycle irreversibly and settles what it owes the remote — the work stays committed in its worktree and the
section below says how to start it again.

### Restarting an issue whose cycle was cancelled

**Reopen the issue, then remove `rejected`.** That is the whole gesture, and both halves are required: the
orchestrator restarts an issue that is open and wearing no workflow label at all, over a pinned comment that records
a cancelled cycle with nothing left owed **and** records that this cycle's `rejected` was actually handed out.
Removing the label is what authorizes it — GitHub grants label writes only to a repository's own people — so the
restart runs whoever filed the issue, `ALLOWED_ISSUE_AUTHORS` included.

Three things follow from that last condition. Removing a *workflow* label from an owner whose cleanup has not
finished does not authorize anything: the ending was never in a state it could write `rejected` from, so it writes it
once the cleanup settles, and the handshake starts from there. Neither does a `rejected` the orchestrator tried and
failed to apply — what is recorded is a label a pass could see on the issue, not an attempt, so a refused write is
simply retried. And an issue whose cancellation is still owing the remote is refused until the cleanup finishes —
including the one obligation no pass can clear for you, a recorded held pull request with no preserved description
beside it, which the held-terminal warning names as `held PR #<n> (no preserved description)`. Repair that record
first; nothing restarts over it.

Cancellations the orchestrator ended itself need nothing from you, closed owners included: the pass that writes
`rejected` records it in the same breath, so the first removal is the one that counts. Cancellations that ended
*before* this record existed are sitting on `rejected` with nothing recorded, and the first tick that sees one there
writes it down — so removing the label works the first time on those too, as long as a tick has seen the issue open
and still labelled. If one of those older issues is **closed**, then reopened and unlabelled inside a single poll
interval, the orchestrator asks GitHub's own label history for that issue before deciding: where the most recent
workflow label **it** applied is `rejected`, the removal counts and the fresh cycle starts one tick later. Only its
own applications count — a `rejected` a collaborator applied and removed by hand is somebody else's label, not a
terminal this orchestrator wrote. A history whose newest one is some other state — which is what an issue that has
already been restarted once looks like, since the restart applied a label of its own — and one the API would not
serve both re-apply the terminal, and removing it again starts the cycle.

Removing a terminal from an issue that never had a late cycle does not start anything either. An issue that already
carries a pinned comment is one the orchestrator has met, and greeting it a second time would write a second pinned
comment that every later read shadows, so an unlabeled issue with a pinned comment is left exactly where it is and
logged once a tick. To drive such an issue again, apply the workflow label you want it to run from by hand — the
same way an outsider's issue is driven past `ALLOWED_ISSUE_AUTHORS`.

What you will see, on the next tick after the label comes off: **one comment** naming the new cycle and where the
issue is going, and **one label** — `workflow:decomposing`, or `workflow:implementing` when `DECOMPOSE=off`. The
issue then runs as a fresh attempt. Everything the cancelled cycle recorded is dropped from the pinned comment: its
agent sessions, its pull request and branch, its child issues and dependency graph, the snapshot it was cut from,
any park, the drift baseline, the retry and review counters, and the timestamps. What is kept is the pinned comment
itself, the ids of the comments the orchestrator has posted on the thread, and the issue's cumulative agent-run,
token, and cost counters — so the receipt a later terminal posts still reports what the whole issue has spent, not
just what the newest attempt did. Child issues the cancelled cycle created on GitHub are **not** touched: they are
real issues carrying real work, and what happens to them stays a human's decision.

If you apply that same target label by hand while a restart is mid-transaction, you will see the orchestrator take
it off and put it straight back. That is deliberate, not a fight over the label: its own application of the target
is what separates the fresh cycle from the previous one's `rejected` in the label history, and GitHub records no
event for a label that is already there. Leave it be — the issue ends up on the label you wanted either way.

If the restart cannot finish — GitHub refuses the comment or the label — the issue keeps the pending marker in its
pinned comment, a `late_failure` carrying `restart_failed` reaches both sinks, and the next tick resumes at the step
that is still owed rather than starting over. `backlog` or `paused` on the issue defers the whole restart until the
control label comes off; the authorization is not lost meanwhile.

**What to look at when something is not going away.** Four signals, and they mean different things:

- A `late_failure` carrying `snapshot_delete_failed` or `branch_cleanup_failed` (see
  [`../observability/event-streams.md`](../observability/event-streams.md#late-split-records-both-sinks)), together
  with an umbrella that will not close, or a closed owner that keeps its label. The remote **refused** the delete.
  That is a permission or ruleset problem — a protected-ref rule over `refs/orchestrator/*`, or a token that lost
  push scope — and only an operator can clear it. Nothing is retried into success meanwhile; the retry itself is
  every visit, but the *record* of it is not: the sinks carry the move to `failed` once and say nothing on the
  visits that reach the same answer again, so what tells you a refusal is still standing is the terminal that never
  fires and the warning logged on every visit that holds — not a second event.
- A snapshot ref that is simply still there, with no failure recorded, and an umbrella that will not close. It is
  **retained** on purpose: a ref is kept until every recorded direct consumer has ended — which means the consumer's
  issue is *closed*, since reaching `done`, being `rejected`, and a human closing it all close it, and reopening
  leaves the label where it was. Those readings are taken fresh on every visit rather than latched, and every
  obligation that is not `reconciled` holds the owner's terminal, so the umbrella stays open and logs what it is
  waiting for on each tick. A child that stays open forever keeps its ancestor's ref forever, which is the
  deliberate trade — invalidating a live child's only copy of the work it was told to reuse is worse. Closing (or
  finishing) the child is what lets both go.
- An umbrella that will not close with **nothing owed at all** — every obligation `reconciled`, no failure on
  either sink. The issue was split on the far side of publication, and the pull request that split superseded is
  open again (or was merged, or has been pushed to since). Everything the umbrella still had to do was licensed by
  that change being closed, so the parent holds rather than handing itself `done` over a live change carrying
  superseded work: no child is released, the branch is left wherever it is, and the terminal waits. There is nothing
  on the ledger to look at because nothing is owed the remote — the reason is only in the log line, said on every
  tick that holds and naming the pull request. Settling that pull request is what clears it; the label staying put
  is the retry. Do not expect the orchestrator to re-delete a branch you restored — a branch put back by hand is
  yours, and refusing to remove it is the point.
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
  A cycle a human's close **cancelled** leaves even that unsaid: it is responsible for none of those children, so it
  reclaims the ref and touches nothing. The child is not left uncovered — the mirror goes before the remote ref, so
  the guard below reaches the same park a receipt would have earned it, one `ls-remote` later.
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
journalctl --user -u orchestrator.service -f   # systemd users
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
3. When safe (no live agent child), `systemctl --user restart orchestrator.service`.
4. Tail logs: `journalctl --user -u orchestrator.service -f`.

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
