# Platform modules

This page maps the packages the workflow layer runs on: the package root and its two launch forms, the polling
`runtime/`, and the `config/`, `github/`, `agents/`, `scheduler/`, `git/`, and `skills/` domains. It is split out of
[`../architecture.md#top-level-layout`](../architecture.md#top-level-layout), which keeps the top-level map and the
naming rules that hold for the tree as a whole. The `workflow/` package is in
[`workflow-modules.md`](workflow-modules.md).

Each entry below is the responsibility its module owns, and it answers there and on no second site. What a stage does
with these owners is in [`../state-machine.md`](../state-machine.md).

## Enforced boundaries

Each rule below names what holds it, so a module that breaks one fails the suite rather than the next reader. The
last is held by the loader itself rather than by a check.

- **Layer position.** `config/` is the bottom layer and names nothing above itself; `github/`, `git/`, `agents/`,
  `scheduler/`, and `skills/` sit above it and below `workflow/`; `runtime/` and the two launch forms compose the
  lot. `tests/repository/test_layering.py` reads that direction twice, because deferring an import weakens where it
  lands but not whether it belongs.
- **At module scope, one exception.** The only name a lower layer may bind above itself is `workflow/state.py`, for
  the label vocabulary it is typed by, and only `github/` and `git/` may bind it — matched on the module boundary in
  the same check, so a sibling of the state owner cannot inherit the exemption by wearing the same prefix.
- **Over every scope, six more, each declared per module.** A base sync runs in the git layer but reports to the
  issue it was started for: `base_sync/conflicts.py`, `base_sync/persistence.py`, and `base_sync/publication.py`
  reach `workflow/engine/comments.py`; `persistence` also `workflow/engine/guards.py` and
  `workflow/stages/implementing/late_parks.py`, to drop the debt the size gate recorded when a refused push sends
  the branch back to where it started; and `publication` also
  `workflow/stages/implementing/late_push.py` and `late_records.py` — the gated push the rebase it is about to
  force-push goes through, since a base that moved changes what the branch adds to it and a pull request may not be
  grown past the ceiling by a refresh either. `publication/rewrite.py` reaches `late_rewrite.py` for the same reason
  one seam over: a squash-on-approval force-pushes onto a pull request the remote already carries, so it is entered
  on that publication before it rewrites anything and pushes through the gate's own call. Each waits for the call
  that needs it. The same check declares them per module: an undeclared hop fails wherever it is written, and one of
  these fails if it is bound at module scope after all — where it would be a cycle, since the workflow imports base
  sync back.
- **Package surfaces.** `github/`, `agents/`, and `scheduler/` publish a narrow `__all__` of their owners' own
  objects and nothing else; `runtime/`, `skills/`, `git/`, and every `git/` subpackage publish nothing at all, so
  naming one costs no owner behind it. `config/` is the deliberate exception: its initializer binds each resolved
  setting as a module attribute, which is the reload and patch target every caller reads one through. Each package's
  own tests hold its surface — a `test_imports.py` in the domains, `tests/config/test_surface.py` for the settings
  module — and `tests/repository/test_package_exports.py` holds the publish-or-front-nothing rule over the tree.
- **No second site.** No domain here sits behind a facade. Where a package replaced flat modules — `git/` and four of
  its six subpackages, `runtime/`, `skills/` — its own `test_imports.py` asserts that nothing resolves at the retired
  spelling, that no inventory or resolver hook names one as a target, and that no aggregate over the git domains sits
  above them — `tests/git/publication/test_imports.py` carries that last one. `git/measurement/` and `git/snapshots/`
  replaced nothing and hold the surface assertion anyway, and the same list carries `git/authentication.py`, the
  module the two transports were split out of, so no facade settles back at that spelling. The rule also holds one
  name at a time where a second binding would be invisible: each transport reaches the token lookup, the askpass
  session, and the session record through `credentials`, and the branch transport reaches the `ls-remote` read a lease
  is taken from through `ref_transport`, rather than importing any of the four by name. `tests/git/test_imports.py`
  asserts each is bound on the owner that defines it and nowhere in the module that spends it — a copy beside the
  caller would read as the patch target a test aims at while the session or the read a call actually takes stayed the
  owner's.
- **One road to a process.** The `agents/` chain is reached at one point from above and one per hop below it: only
  `workflow/engine/usage.py` calls `run_agent`, and the initializer republishing it as the package API is the one
  other module that names it at all; only `runner.py` names `codex.run_codex` / `claude.run_claude`; and only the two
  backends name `processes.run_subprocess`. That is what makes the lifetime agent-run charge taken around that single
  call a charge every role pays, since a second caller anywhere would be runs nothing counts.
  `tests/repository/test_agent_spawn_boundary.py` reads the whole chain off the source, counting a reference rather
  than a call so a spawn bound into a variable is caught where its name is written, and holds the call itself to
  `_run_agent_tracked`'s own body with the circuit asked on a line above it.
- **Operator log channels.** Four names are spelled literally rather than derived from `__name__`, because an
  operator's level and handler selection is keyed on them: `orchestrator.git_plumbing` (`git/branch_transport.py`,
  `git/credentials.py`, `git/ref_transport.py`, `git/snapshots/refs.py`, and the two `git/measurement/` owners that
  log, which all report on the same token, `ls-remote`, fetch, push, and diff plumbing),
  `orchestrator.base_sync` (`git/base_sync/state.py`), `orchestrator.worktree_lifecycle` (the eleven `git/worktrees/`
  owners that log), and `orchestrator.branch_publication` (`git/publication/rewrite.py`). A module moved between
  packages does not take its channel with it, and each of the four names is asserted where its owner is tested —
  `tests/git/test_branch_transport.py`, `tests/git/test_credentials.py`, and `tests/git/test_ref_transport.py`,
  `tests/git/base_sync/test_state.py`, `tests/git/worktrees/test_imports.py`, and
  `tests/git/publication/test_imports.py`.
- **Import cost.** `import orchestrator` costs the root module and no owner behind it, and importing a `runtime/`
  owner plants neither the CLI nor an app — `tests/runtime/test_imports.py` and `tests/apps/test_imports.py`.
- **Direction inside `skills/`.** Neither owner may reach the workflow engine, a stage, or an application entry
  point: a catalog is observation the tick drives, not state a handler consults — `tests/skills/test_imports.py`.
- **Secrets.** `GITHUB_TOKEN` is read from the process environment or a token file outside `REPO_ROOT`, never from
  the `.env` an agent with sandbox bypass could read out of a sibling worktree: `config/_dotenv.py` skips every
  secret key it finds there and warns instead of loading it — see
  [`../configuration.md#github-personal-access-token`](../configuration.md#github-personal-access-token).

## The map

A package line names what its initializer publishes; where it names nothing, the initializer is a marker and callers
import an owner directly.

```
orchestrator/
  __init__.py           the distribution version and the `__all__` naming it, and nothing else
  cli.py                the `chipping-orchestrator` console script: the polling process's composition point
  __main__.py           the `python -m orchestrator` launch form over `cli.main`, and what `run.sh` starts
  runtime/              the polling process's own owners
    state.py            the mutable state one run carries and the shell-style code a signal stop exits with
    logs.py             the stderr and rotating-file destinations a run settles before its first client
    startup.py          the run options, one client per configured repo, and the scheduler every tick shares
    ticks.py            one pass over the configured repos: the per-repo tick, the fan-out, and the reap / prune
                        drains
    loop.py             one-shot vs recurring polling, the interruptible wait, and the guaranteed scheduler drain
    self_update.py      the git probes behind the self-restart guard
    shutdown.py         the signal handler, the bounded-drain watchdog, and the forced exit it ends at
  config/               the resolved settings surface, bound as module attributes
    environment.py      the env-value parsers and the `_SettingsResolver` that reads and validates every knob
    _dotenv.py          the non-secret `.env` loader
    credentials.py      process / token-file credential resolution and the secret redactor the verify output, the
                        agent stderr diagnostics, and the trajectory writer mask with
    models.py           the `RepoSpec` / `RepoEnvEntry` repository-config types
    repositories.py     `REPOS` entry parsing, validation, and default-spec construction
  github/               publishes `GitHubClient` and `PinnedState`
    client.py           the authenticated client over the mixin chain: PyGithub setup, the worker-thread clone, and
                        the cached label reads with their confirmed-absent retry window and the one line a sweep's
                        absent legacy spellings are reported in
    aliases.py          the descriptor a stateless helper is bound onto the client with, so class, instance, and
                        module access all answer alike
    checks.py           status / check-run normalization, failure-before-pending folding, and the fail-closed check
                        reads
    comments.py         the `ALLOWED_ISSUE_AUTHORS` trust policy a caller filters a thread or gates one author
                        through, whether a comment on a thread was written by US -- the author check the marker
                        lookup here and both park-notice reconciliations gate on, since a receipt recognized by a
                        hidden marker and one recognized by its whole sentence are alike text anybody may post and
                        so alike text anybody may use to suppress what it stands for -- and the reserved prefix
                        every receipt this orchestrator hides shares, so content somebody else wrote can be refused
                        before it is embedded; the low-level comment and review readers stay raw
    events.py           audit event record construction and the optional JSONL sink
    issues.py           issue polling and writes, the query options, the wire issue-state vocabulary,
                        the closed predicate every reader of it asks through, the every-state, no-label walk
                        that finds the one issue carrying a marker -- the reading a receipt lookup needs and the
                        only one that sees an issue a human has since closed or relabelled -- and the labels whose
                        CLOSED issues a sweep still owes a pass: the recovery set whose terminal arc has not
                        drained, and the cleanup set, which is where a late adjudication runs plus where an
                        interrupted cancellation can be left; plus the one question about an issue's PAST
                        this client answers -- which workflow label THIS orchestrator applied to it LAST --
                        which is what a removed label leaves no other trace of, and what tells one attempt
                        at a state from an earlier one, since every state this workflow moves an issue to
                        is itself an application; the actor is filtered on the same account the pinned
                        comment is authenticated under, so a name a collaborator applied by hand is not a
                        write of this orchestrator's; control labels are excluded, and no account, no
                        evidence, and an unreadable walk all answer alike
    labels.py           the label vocabulary and bootstrap specs, and the in-place rename of a pre-namespace label
    pinned_state.py     the pinned durable-state model, the comment body it is written as and the length GitHub
                        takes, its parser -- which identifies a state-only comment whatever payload it carries
                        and keeps the one carrying no readable state, whether it would not parse or parsed
                        into anything but an object, apart from an issue that recorded nothing, since both read
                        back as `{}` -- and the comment watermarks beside it
    pull_requests.py    PR lookup by open state, by commit, and when GitHub could not be asked at all -- either
                        search narrowed to one base for a caller choosing the thread it would push onto, or asked of
                        every base by one asking only whether anybody is still standing on this branch -- plus
                        creation, comments, body, labels, SHA-pinned merge, remote-branch delete, and the
                        supersession that says once on a thread of ours that this change is not to be merged and then
                        closes it -- taking that "already said" answer from the caller where it has one, since the
                        search is a request and a caller that proved the pull request a moment earlier may not put one
                        between its proof and the write
    reviews.py          current-head review aggregation: approval verdicts and unread-feedback watermarks
  agents/               publishes the run models, `run_agent`, and `terminate_all_running`
    models.py           the agent result, run-option, and subprocess-result models
    environment.py      credential filtering and the injected git identity
    sessions.py         session-id and Claude final-message JSONL parsing, plus the transient-provider
                        classifier every stage that reads a final message as the agent's own asks first
    processes.py        the shared process registry and the subprocess-group lifecycle
    runner.py           `run_agent`: backend dispatch, result assembly, and spawn logging
    backends/
      codex.py          Codex command construction, scratch output, and execution
      claude.py         Claude command construction and execution
  scheduler/            publishes `IssueScheduler` and `SubmissionRequest`
    models.py           the typed submission, the historical `submit` binding, and field normalization
    service.py          the concrete scheduler: the caps, the tracked claims, the family mutex, dispatch, and
                        shutdown. What a refused submission MEANT is the caller's -- a cleanup refused because a
                        worker holds the issue costs an observation rather than a turn, and the workflow keeps that
                        reading where its own stage handlers can reach it
  git/
    branch_transport.py the authenticated fetches, the remote read that answers what a branch is at without trusting
                        a local ref -- in the plain form a caller acts on and the form that also carries why a read
                        established nothing -- and the lease-pinned branch push, each spending one credential
                        session
    commands.py         plain / hardened git execution, the argv hardening and no-prompt environment, the per-call
                        environment pin a caller adds over it, the absolute `--work-tree` argument a working-tree
                        operation names its tree with, the unsafe local-transport probe, and the one line of a
                        failed call's output a caller carries away from it
    credentials.py      the per-repo token lookup, the owner-only askpass script that outlives no operation, the
                        session record a token-bearing call is spawned from -- the detached environment, the URL
                        naming only the `x-access-token` username, and the token itself -- and the redaction every
                        transport puts that token's own output through before logging or handing it back
    locks.py            the per-target-root re-entrant lock registry and its accessor
    ref_transport.py    the remote read named by a whole refname -- the reading and, where nothing was
                        established, the scrubbed line saying why -- and the lease-pinned write and delete an
                        immutable ref namespace is owned through; the read the branch transport spends for its own
                        lease too
    base_sync/          the per-tick base fetch and the auto-rebase of every worktree behind it
      refresh.py        the authenticated base fetch, worktree discovery, the order the sync gates are asked
                        in -- including the label scope on the two freezes no write ever ends -- and the
                        per-worktree route
      frozen.py         which records hold a checkout still and what ends each freeze: the ones that freeze a
                        branch by their presence -- the late reading and the approval among them, each read as
                        the whole GROUP its write puts down rather than as its commit alone, since a record
                        carrying part of one is what the dispatcher parks on a tick LATER and a hold keyed to
                        the commit would rebase and push it first -- the two parks that freeze one with no
                        record behind them at all
                        (a size reading nobody could take, and an implementer timeout whose watermark names a
                        commit not yet made), and the two no write ever ends (the accepted commit and the
                        published one), which freeze only while the checkout still stands on the commit they
                        name and only while the stage that has to act on it still holds the issue
      eligibility.py    the label, park, open-PR, recovery, and clean-tree gates one PR sync clears
      pre_pr.py         the hardened rebase / merge probes and the aborting pre-PR local rebase
      pr.py             the order a PR-having worktree's gates, rebase, and publication are asked in
      startup.py        the pre-rebase HEAD guard and the anchor persisted before git runs
      publication.py    the post-rebase checks, the size gate the rebase passes before it publishes -- reached
                        through a call-time import, since it sits in the workflow layer above this one, and named
                        against the head this owner read, so a checkout something moved between that read and the
                        gate's own refuses rather than publishing one commit while the notice, the event, and the
                        `validating` route name another -- the lease-pinned force-push, and what an accepted push
                        writes
      conflicts.py      the counter, notice, event, and relabel a genuinely conflicted rebase is handed to its stage
                        with
      guards.py         the no-op completion and the unreadable-HEAD, dirty-tree, and failed-push refusals
      snapshot.py       the branch fetch, the local / remote head reads and divergence counts, and the abort an
                        unreadable one takes
      recovery.py       the order a crash recovery asks its questions in, and the dirty-guarded reissued push,
                        measured by the same gate and named against the head this recovery verified against the
                        remote: one an earlier tick rebased and never pushed is a head nothing has read against
                        the base it now sits on, and one something moved since is not the head the finalize
                        behind the push records
      outcomes.py       the already-published, unknown-comparison, diverged, dirty, and failed-push answers
      persistence.py    the parks, the reset-and-park tail -- which drops the debt it abandons only once the reset
                        has actually landed, since a refused one may leave the branch still standing on the
                        approved commit -- and the state / notice / event writes a recovery ends in
      models.py         the frozen contexts, requests, snapshots, and decisions
      state.py          the pinned-state keys, park reasons, refresh detour labels, and the shared logger
    publication/        what a branch becomes before review reads it
      models.py         the record a squash hands back, in the three shapes it can end in -- published, refused, or
                        held by the size gate for the adjudication
      planning.py       the merge-base, HEAD, dirty, and subject preconditions plus the squash message they select
      probes.py         the subject vocabulary and predicates, one divergence reading -- the fetched ref resolved
                        ONCE and HEAD counted against that immutable commit, since the counts are a claim about the
                        tip and a ref something moves between two readings would leave a branch proved against one
                        head and its push pinned to another -- and the first-commit and recent-base subject reads.
                        A reading that did not happen says so (`readable`) rather than answering `(0, 0)`, which is
                        what an in-sync branch answers and what every caller acting on it would rebase, spawn over,
                        and force-push on
      rewrite.py        the soft reset, the orchestrator-identity commit, the gated publication of the commit it
                        just made -- measured, then named against it and pinned to the head the entry froze -- and
                        the rollback a post-reset failure takes -- the ref and the index, never the working tree,
                        since a squash has the same tree as the head it replaces and the only thing taking the
                        worktree too would restore is an edit somebody made while the rewrite ran -- which drops the
                        approval it abandons only once the reset has actually landed -- a reset that failed may
                        leave the branch still standing on the approved commit, and the approval is the only record
                        naming the one commit this issue may publish. A HELD candidate is spared that rollback only
                        where the squash is somebody's: a
                        live record naming it -- oversized, or a pair still owed its count -- already on the remote,
                        or under a commit something else made. A hold the gate REFUSED is none of those, and froze
                        nothing to say otherwise -- a pull request closed or moved in the window the reset and the
                        commit sit in -- and the branch goes back there, since a squash nobody measured, published,
                        or recorded is the one commit a retry finds, and one commit is the nothing-to-squash road
                        reporting success
      squash.py         the plan-then-enter-then-rewrite entry point a stage handler calls, over the gate subject
                        that handler builds
      titles.py         subject-prefix inference and PR-title selection
    measurement/        how large a committed candidate is, and why a size is sometimes unknown
      models.py         the typed failure vocabulary, and the three records a reading hands around: one frozen
                        end of a diff, the measurement over both ends -- each of those two carrying the failing
                        step's own scrubbed line beside the typed reason it stands next to -- and the readback
                        saying whether an end this host was supposed to hold is really here
      commits.py        the remote-authoritative base freeze (fetched once when the object is missing) and the
                        candidate proof that an id resolves, is held here, and peels to the commit it names --
                        each handing back whatever id it did establish beside the failure, so a retry has one
                        exact object to ask for, and the freeze naming what the read or the fetch reported for
                        itself
      additions.py      the `--numstat` added-line count over the frozen pair — read under the candidate's own
                        attributes and a named algorithm, pinned where git consults the environment last, and
                        refusing outright on the attribute file and diff-driver config no pin reaches — and the
                        measurement composing the three steps
    snapshots/          the immutable remote copy a superseded candidate is preserved as
      namespace.py      the one `refs/orchestrator/late-split/...` namespace a snapshot may occupy, built from a
                        generation's own identity and refused for anything else, plus the
                        `refs/orchestrator/late-split-local/<repository>/...` name this host's copy of one lands
                        under -- qualified because several configured repositories may share a clone, and bounded
                        because configuration bounds a slug at nothing
      refs.py           create-or-verify against the exact commit with no overwrite, the fetch-and-resolve that
                        proves a child could obtain it (one locked step, onto this repository's own local name),
                        the read-only ask a caller spends when it must know whether a ref is still there without
                        being allowed to take it, named against the commit it was promised like every other read
                        here, and the absent-is-success delete -- leased at the preserved
                        commit, so a re-pointed ref is refused rather than reclaimed, and taking this host's copy
                        down BEFORE the remote one, since a mirror is what a child reads as "nothing has been
                        reclaimed": one that will not go -- or that a failed read cannot tell from one already
                        gone -- refuses the whole reclamation rather than outliving the ref it mirrors. The read a
                        child spends on that copy is published here too, and it is an identity rather than an
                        existence: the store is one the agents write, so the copy is resolved and compared against
                        the commit the caller was promised
    verification/       what a verify run is, and the reads a checkout is judged by
      models.py         the `VerifyResult` statuses and fields, and the output budget
      output.py         the redact-then-truncate pass over captured verify output
      probes.py         the HEAD reads, the porcelain status in both its answers (the paths, whether git could be
                        asked, and the `is_clean` a caller whose next step is a push asks instead of truth-testing
                        the list) -- taken without optional locks, so asking what a tree holds does not refresh
                        and rewrite its index -- the ignored-path read beside it, which is what git leaves out of
                        every one of those and out of its own refusal to remove a dirty worktree, so a caller
                        about to DELETE a tree can be told about the `.env` a caller about to publish rightly
                        passes over, and the two a named commit is judged by
      process.py        one command's group spawn / kill / drain and its verdict
      runner.py         the stripped child environment and the fail-fast command sequencing
    worktrees/          the per-issue checkouts an agent runs in, the read-only inventory of which issues they
                        and the branches beside them name, the classification of which of those may be
                        reclaimed, the teardown that takes a cleared checkout down, and the ledger carrying an
                        unfinished teardown of one of them across a restart
      paths.py          slug sanitization, git-ref-safe branch segments, path, branch, and pinned/legacy
                        resolution, the exact set of names one issue's branch can be published under, and the
                        `issue-<n>` read that runs back the other way -- canonical spellings only, so a padded or
                        signed number is no issue at all
      creation.py       issue and PR worktree creation, stale-worktree reuse and the probe it turns on, and the one
                        move that re-anchors a reused checkout onto a PR head or its merged base
      cleanup.py        lock-held worktree removal and local branch deletion, each behind its best-effort boundary,
                        plus the fail-closed read a caller that has to RECORD the teardown asks afterwards
      recovery.py       candidate-branch discovery, the unpushed-commit probe, and the tip read a recorded SHA is
                        compared against
      decomposition.py  the decomposer scratch path, its detached creation, and its best-effort removal
      terminal.py       question-stage teardown and terminal local and remote branch cleanup
      models.py         one issue's local artifacts and the whole answer a scan gives -- the issues it attributed
                        beside the repositories it will not answer for -- plus what a classification over them
                        says: the three answers a fail-closed read has, the ref reading that carries a commit
                        with them, the reasons, subjects, and verdict a retained candidate is reported as, and
                        the commits an eligible one hands over as cleared. Then what a teardown over one of
                        those verdicts answers in: the surfaces an artifact lives on, the cleaned / absent /
                        failed one step leaves, and the whole per-surface record a caller reads a
                        partly-finished reclamation off
      probes.py         the two local reads a scan is built from: the `refs/heads/orchestrator/` listing and the
                        per-issue checkout directories -- a real directory under the exact name, never a symlink
                        into a tree the creators never wrote, read through the `lstat` that reports what the
                        `is_dir` predicates suppress -- each answering "could not read", listing and entry alike
                        and a listing that warned about a ref it skipped included, apart from "nothing here"
      attribution.py    which configured repository a discovered artifact belongs to, by re-deriving each spec's
                        own name for it; a name several entries could own -- every legacy flat branch on a shared
                        clone, every checkout directory two lossily-sanitized slugs are handed -- is attributed to
                        none of them
      inventory.py      the read-only scan over both reads: which entries share a clone, one listing per clone,
                        worktree-only and branch-only candidates deduplicated into one entry per issue, and a
                        repository whose clone would not resolve, whose checkout directory another entry also
                        derives, or whose read failed left out of the answer rather than reported empty -- and
                        still put to the attribution, since a repository this scan will not answer for is one the
                        flat branch on its clone could equally belong to
      evidence.py       the seven hardened reads a candidate is judged by -- a checkout that is a worktree of
                        this clone and on one of this issue's own branch names, a tree that PROVED it carries
                        nothing loose and one that PROVED it hides nothing besides, a local branch tip, the
                        commit the checkout's own HEAD stands on and which branch
                        that HEAD is, what the REMOTE
                        says a branch is at, and whether the base the remote named already contains a given tip
                        -- each answering "could not read" apart from git's own no, and a base nobody named
                        counted as the first. Loose and hidden are two reads because git treats them as two:
                        untracked and modified paths are what it calls dirty and what `worktree remove` refuses
                        over, while a path the repository's own rules cover is neither -- so a tree carrying
                        nothing else answers clean and comes down with all of it inside.
                        The two remote questions go over the authenticated `ls-remote`
                        rather than to `refs/remotes/...`, which is a local ref the per-issue worktrees can write:
                        a base mirror repointed at an agent's own tip would otherwise read as a base that carries
                        its work. That read spawns processes, so it is behind a boundary of its own -- a probe
                        with three answers may not have a fourth -- which is why the status read is behind one
                        too, since naming the tree it reports on resolves a path an agent can turn into a
                        symlink loop. Nothing here writes or fetches on either side
      claims.py         the GitHub side of the same question: the issue fetch, the authenticated pinned read and
                        the two checks that its payload is a state at all, the exactly-one-terminal-label rule an
                        ending has to pass, the open pull requests still standing on a branch or on the recorded
                        number, and whether a terminal pull request carries a tip the base does not. The branch
                        claims are asked of both layouts this orchestrator publishes an issue under whether or
                        not the host still holds them, and neither they nor the commit accounting name a base,
                        since a thread retargeted onto another base stands on the branch and holds the commit
                        just as squarely. Every read is behind its own boundary, the lazy fields included, and
                        every boundary answers with a retention rather than a default
      eligibility.py    the side-effect-free classifier over both: the GitHub gates that settle a candidate on
                        their own, then one tip proof run over every commit an artifact holds, with the base
                        established once for the whole candidate. The checkout owes that proof as a branch does
                        -- a worktree whose branch was deleted under it holds its commit through its own HEAD and
                        reflog alone -- and is excused only when a reported branch is standing on that same
                        commit, so the three shapes one issue can be reported in reach one verdict. Inside the
                        proof the remote is asked before the base ancestry can release anything, since a merged
                        tip can still sit under a branch the remote has been pushed past. A branch this clone no
                        longer holds is proven through the copy the remote carries rather than waved through:
                        the scan named it moments earlier and something deleted it since, and a remote copy
                        nobody proved is one a teardown may neither delete nor write down. Reported as one
                        verdict per candidate carrying every reason it is kept for, and -- when it keeps none --
                        the commit each artifact was cleared at
      reclamation.py    the destructive step, and the only owner in the artifact domain that destroys anything:
                        an eligible verdict is spent, never re-derived, and everything it established is
                        established again at the boundary it is about to be spent at -- the checkout still this
                        issue's own, still clean, and still on the commit that was cleared before a `worktree
                        remove` that does not force, which runs with git's own `index.lock` and `HEAD.lock` for
                        that checkout held -- no `commit`, `checkout`, `reset`, or `update-ref HEAD` can run in a
                        tree while they are this pass's, which is what makes the reading before the removal hold
                        -- and with the lock git takes for the branch that checkout's HEAD is on held too, a HEAD
                        being a symbolic ref and an `update-ref` on the branch under it moving what the tree
                        stands on without going near either of the other two. WHICH branch that is gets read
                        only once the first two locks are held: an issue publishes under a namespaced name and a
                        legacy flat one, both of which read as its own, so a HEAD read in front of `HEAD.lock`
                        could have moved between the two by the time the ref is frozen -- leaving this pass
                        holding the ref the checkout moved off. That name also has to stand for itself: git
                        reaches a loose ref by walking its path, so a room on the way replaced with a link, or
                        the ref replaced with one, files this issue's branch where another name is, and an
                        `update-ref` on the far name moves what the checkout stands on while the lock sits at
                        the near one. A ref this pass cannot hold still by its own name is refused rather than
                        locked. Each lock carries the process that took
                        it, so a lock a killed pass left behind is one a later pass tells from one a running
                        command holds and takes again rather than refusing this issue for good -- and each is
                        written whole under a name nothing can have planted, created for this pass alone rather
                        than derived from the lock's own, and then LINKED to the name it is for. A lock created
                        first and marked afterwards is one a failed write or a stopped process leaves carrying
                        nothing, which no later pass can recognise as this host's and which therefore refuses
                        that issue permanently; a staging name anybody could derive is one anybody could leave a
                        link or a fifo at, which the write would follow into somebody's file or wait on forever
                        while these same locks were held. Every write here is finished rather than offered once,
                        since what a write reports is only how much it took; the
                        registration's mode comes back writable whatever was found, for the same reason. Both
                        the take-again and the give-back are bound to the exact file the line inside it names,
                        never to the name alone -- two passes meeting one leftover would otherwise each delete
                        what the other had just created and both go on -- and every lock is asked once more,
                        immediately before the removal, whether it is still the one this pass took. Then
                        with that checkout's HEAD pinned to an anchor one process before it and read back one
                        process after: a commit made before the locks went on comes down with the checkout, and
                        the anchor is what keeps it nameable and has the surface report the removal as the
                        failure it was. An anchor is created and never overwritten, so one an earlier pass left
                        standing refuses the removal rather than being replaced and then discharged -- unless
                        what it pins is the very commit this verdict clears, which is the note a pass that
                        stopped between writing it and removing anything leaves behind. That one is spent and
                        taken again, since reusing a ref an agent could have planted would make it the pinning
                        the removal is measured against; a note nobody could take away refuses the removal too,
                        the write after it being refused by the same ref, and one that would not go after the
                        removal leaves the surface unsettled rather than reported clear. What the tree hides is
                        read once more between the note and the removal, last of everything: git's own locks stop
                        a commit in that tree and stop nothing from writing in it, and an ignored file is what
                        `worktree remove` takes without a word -- so a reading from before the note would delete
                        a secret that landed after it. The rest of the verdict's reading is retaken there too,
                        and not only the parts git leaves out: the locks go on after the reading that cleared the
                        tree, and a checkout put on somebody else's branch in that window is one every step after
                        would take for ours -- the branch this pass freezes being the one it moved onto -- so
                        whose repository it is and which branch its HEAD is on are established again where
                        nothing can move. Where the path leads is read there too, and for the same kind of
                        reason: the command resolves its own argument, so a checkout renamed away with its
                        registration repaired and a link left in its place would have it take a directory outside
                        the tree this orchestrator owns. The two are compared as filesystem objects rather than
                        as spellings, an operator whose worktrees root sits under a link of their own having
                        every checkout answer a resolved path that is not the derived one. The checkout is held
                        OPEN across all of it besides, since a directory nothing links to any more is the only
                        thing that says THIS checkout came down: the descriptor opened before the readings is
                        what they are checked against and what the result is read off. The reading afterwards is
                        not what keeps the tree safe, though — `worktree remove` deletes the path its
                        registration names and resolves it at the moment it runs, after every reading this pass
                        can take, so a directory left where the checkout was would be deleted and a file the
                        repository's rules hide, arriving at that name in that window, would go with it. The
                        name therefore stops being the checkout's before the command runs: the tree is moved,
                        inside the room it already sits in, to a name this pass makes and tells nobody, and the
                        registration — which nothing else can write — is aimed after it, so what the command
                        deletes is a path nobody else holds a name for and what the tree hides is read once more
                        where it now stands. A removal that did not take it puts it back, the scan reading this
                        host's candidates off the derived path; a pass killed between the two leaves it under a
                        name carrying its issue, and the pass after finds it, puts it back, and repairs the
                        registration behind it before it reads anything — dropping on sight the empty rooms a
                        rename that never happened reserved, since a checkout carries its own `.git` at the very
                        least, stopping rather than choosing when more than one tree is there, and stopping
                        outright on a room it could not read at all: that room is SCANNED rather than matched by
                        pattern, since a pattern answers a room it could not list the same way it answers an
                        empty one, and "nothing there" and "could not look" are two answers a teardown must
                        never spend for each other. What
                        the command actually deletes is not the path it is handed, though -- that path only selects a
                        registration, and the registration names the tree that comes down -- so that file is
                        opened without following, refused unless it is a regular one naming this checkout's own
                        tree -- read to a bound with the byte past that bound asked for as well, since a file
                        padded to exactly it would otherwise read as the shorter thing it is not and the
                        take-over would file that truncation at the name -- and then TAKEN OVER: a copy of this
                        pass's own, carrying exactly what the original
                        said, is written beside it and renamed into place, which leaves every descriptor
                        somebody opened earlier pointing at an inode no name resolves to. The original stays
                        open across both halves and is asked once more -- still the file that was read, still
                        saying what it said -- immediately before that rename, because what the copy carries is
                        what the original SAID: a `git worktree move` landing in between rewrites that file in
                        place, and a take-over that went ahead would write the obsolete path over the one git
                        had just recorded, deregistering a checkout it then refuses to touch. That reading and
                        the rename are separate steps, so the original is read once more AFTER the rename too,
                        through the descriptor the rename displaced: a move that finished in between recorded
                        where it put the checkout, and what it recorded goes back at the name rather than under
                        what this pass remembered. That is the half a
                        mode cannot buy, since write bits coming off say nothing to a handle that already
                        exists; the no-follow open is what keeps a link left there from having every read and
                        every mode change land on somebody else's file; and what the mode does buy is that the
                        `worktree repair` a swap needs to aim the removal elsewhere cannot open the name afresh.
                        Nothing locks any of it, so before the command runs the name is read once more against
                        the object held open -- a rename through the directory above is not something a mode
                        reaches -- and the object is read back against what it said when this pass established
                        it named this checkout, since a rewrite in place changes where the destruction lands
                        without changing what is filed at the name.
                        And a removal that came back clean over a path still standing is
                        reported as the failure it is, since what came down was not what this named -- and a
                        command that refused over a path that is gone is this removal having happened without it,
                        reported as the absence it is rather than as a deletion this pass made. The note is
                        measured the same way whatever the removal answered, since `worktree remove` deletes the
                        tree and then deletes the administrative directory beside it whatever the first half did:
                        a non-zero result is not a checkout still standing, and letting the note go over one
                        would take the last name a raced commit has. The path itself is read before any of that,
                        and anything at it that is not a directory of its own is refused: `worktree remove`
                        resolves what it is handed and deletes the registered tree at the far end, so a symlink
                        left where the checkout belongs would have it take a directory outside the tree this
                        orchestrator owns -- and every reading in front of the removal follows the link and
                        agrees. What the tree carries is read twice for the same reason: git refuses a removal
                        over an untracked or modified path and takes an ignored one without a word, so a checkout
                        holding nothing but what its own rules cover passes every other reading and comes down
                        with all of it inside. That read is asked last of everything, and then once more where
                        the tree has been moved to, which is the first place it can be taken that nothing else
                        is writing in. What a pass leaves PINNED is answered beside the checkout rather than
                        folded into it: an anchor outlives the tree it was taken from, so a pass that found the
                        tree already gone would otherwise report the issue settled while this host went on being
                        the only name a commit has. It is reported only as a failure, since a note standing is a
                        thing somebody has to settle.
                        Every name here that an agent chooses what to put at -- the
                        registration and each of the three locks -- is read the same way besides: without
                        following, without waiting, and asked what the descriptor IS before it is asked what it
                        says, to a bound. A fifo at one of them would otherwise block a pass that is holding the
                        target-root lock and git's own, and a pass that blocks there never comes back to give
                        any of them up. Ownership is re-derived rather than read off the verdict, so only
                        the one path this issue's creators derive can be touched. Already-absent is success, and
                        so is nothing to remove: a candidate the scan reported no checkout for names no surface
                        here at all
      obligations.py    the ledger a teardown writes its notes to itself into, both kinds read back off their own
                        namespace: one ref per branch under
                        `refs/orchestrator/remote-reclaim/<repository>/`, valued at the commit the
                        classification cleared -- or, for a branch it cleared none for, at git's empty tree, an
                        object every repository knows and no branch is ever at, which is how a reminder to ask
                        again is told from a commit somebody adjudicated. Neither value authorizes anything: the
                        pass that reads one back asks the classification for that. What the value IS is checked
                        as well as what it says: a ref file carries an object id and nothing else, and git
                        writes and resolves one for an object the repository does not have, so a note left at a
                        stray id -- or at a blob, or at a tree that is not the mark -- reads back exactly like a
                        commit somebody adjudicated. Only a commit this repository holds is a value every note
                        is written at, and the mark is a record's alone: an anchor exists to name a commit, so a
                        marker-valued one names no work at all. The write is held to the same reading before it
                        reports a note kept, since git files a ref at any object it has and a caller told its
                        record was kept would go on over a ledger the pass after has to refuse whole. Every one
                        of those readings is pinned local with `GIT_NO_LAZY_FETCH`: a clone made with a filter
                        keeps a promisor remote, and git answers an object it is missing by fetching it -- so
                        the write, the listing, and the type read under both would each reach that remote, and a
                        note left at an object nothing on this host has would come back as one somebody
                        adjudicated. A ref rather than a file,
                        because that is where this domain's durable state already lives and it is written under
                        the same lock; outside `refs/heads/`, so the
                        artifact scan does not read one as a candidate of its own, and outside the snapshot
                        namespace, which is published. Written and taken away without dereferencing, since a
                        record pointed at somebody's branch would otherwise have this host's note to itself land
                        on that branch or take it away -- and taken away only under the value the caller read
                        there, since each of these is read before it is acted on and a note repointed in that
                        window is holding a commit nothing else names. A leased delete is refused for a ref
                        that has already gone as squarely as for one that moved, so a refusal is asked about
                        once more and a name nothing resolves is the success it looks like -- the ref genuinely
                        not being there, which is why that read answers in three and not two: one that failed
                        spent as an absence would report a note still standing as one this host took away.
                        Every read of a name goes through an undereferenced one first, and so does every
                        deletion, because neither the resolution nor the lease under them answers for the name
                        itself: both follow a symbolic ref. The resolution reports NOTHING for one aimed at a
                        ref that does not exist -- git's own answer for a name nobody ever wrote -- so such a
                        note would read as one this host had already taken away and the deletion that never ran
                        would be reported as done; and the lease compares the stated value against what the name
                        RESOLVES to, so a note aimed at anything standing at that same value passes it, and what
                        the delete takes is a ref the caller never read. Asked undereferenced, a name holding
                        anything but a direct ref or nothing at all is the unreadable name it is. In front of
                        that sits a look at the name itself, taken without following, because git has a second
                        way of following one that no ref read reports on: it opens a note by path, so a note
                        somebody replaced with a filesystem link is read as whatever the link leads to -- and a
                        link leading nowhere reads, to every one of those commands, as a name nothing is at,
                        which is what let a discharge report a note still standing as taken and let the
                        create-only lease write over one. That look walks the whole name a room at a time rather
                        than only its last step, since git follows every one of them: a namespace replaced with
                        a link to `refs/heads` files each note under that name instead -- the note about an
                        issue's branch becoming that branch, which the artifact scan then reads back as a
                        candidate -- and has each listing report somebody else's branches as notes this host
                        wrote. Writes are held to the rooms alone, a note already standing being a thing a later
                        write is allowed to replace. Each reading and the step spent on it are one hold of the
                        lock besides, since git has no write here that states what a name may BE as well as what
                        it stands at, and two holds would leave open the window the reading is there to close.
                        The
                        repository key is the branch namespace's readable
                        segment plus a digest of the untransformed slug, and the digest is the half that
                        matters: two entries sharing a clone derive one legacy branch name, which is why a
                        ledger keyed on the branch alone would send one entry's deletion to the other's remote
                        -- and the segment alone is no better, since `acme/wid:get` and `acme/wid_get` sanitize
                        to one segment, the very collision the attribution refuses to resolve. Beside the
                        records, one anchor per issue holds what a checkout was standing on while it came down,
                        written from inside that checkout so git resolves and records its HEAD in one command --
                        which is also what makes the tree it runs in decide the store it lands in, so that store
                        is asked for and held to the one this repository reads: a checkout of somebody else's
                        repository would otherwise take the note where nothing on this side ever looks while the
                        caller was told it was kept --
                        and written under the lease that says the ref must not exist -- what an anchor already
                        there is holding is a commit nothing else names -- with the undereferenced read in front
                        of it, since the lease compares against what a name RESOLVES to and a dangling symbolic
                        ref resolves to the nothing it accepts.
                        The read-back answers "could not read" apart from "nothing owed" -- a listing that
                        warned, a line that did not parse, a note standing at a commit it merely points at
                        rather than one it was written at, and a ref
                        outside the repository's own namespace all refuse the whole answer, since a ledger short
                        by one entry is indistinguishable from a complete one. The one note the listing itself
                        cannot refuse is the one it never sees: git drops a ref aimed at a ref that does not
                        exist out of every ref iteration it has, silently and at exit zero -- the paranoia that
                        widens iteration to broken refs turns dangling symbolic ones off in the same breath. So
                        what the store is holding is asked of the store, under the same hold of the lock as the
                        listing: a symbolic ref is never packed, so every note that could be in that shape is a
                        file under the namespace, and a name found there the listing did not report refuses the
                        answer. That walk is taken entry by entry and without following any of them, since a
                        glob answers a namespace it was refused exactly as it answers an empty one -- and a
                        namespace this host may not look into holds notes the listing beside it could not read
                        either, both of them coming back as nothing owed. A room that will not be read and
                        anything under one that is neither a note nor a room for more of them refuse the answer;
                        the lock git holds a note under while it writes one is passed over, being a write in
                        flight rather than a name anything has to have accounted for. Nothing here reads a
                        remote or
                        deletes anything on one
  skills/
    catalog.py          the per-tick `git ls-tree` of a repo's `SKILL.md` definitions, the `project` level it
                        classifies every one of them at, and the one `repo_skill_catalog` record it appends
    discovery.py        the per-run scan of what a codex run was loaded with and the `project` / `user` /
                        `harness` level that defined each name, plus the skill roots, marker, and level
                        vocabulary `catalog.py` reads back
```

## Inside `git/`

The six subpackages bind their collaborators directly, so the dependency direction reads off the owner rather than
off a facade:

- `publication/` — `probes` calls `commands`; `titles` calls `probes`; `planning` calls `commands`, both siblings,
  and the verification probes; `rewrite` calls `commands`, `branch_transport`, and those probes; `squash` calls
  `planning` and `rewrite`.
- `verification/` — `output` calls `models`, `process` calls `output` and `probes`, and `runner` calls `process`.
- `measurement/` — `models` carries only data. `commits` calls `commands`, `branch_transport`, and the verification
  probes for the two object reads, and `commands` once more for the one line it keeps off a fetch that brought
  nothing back; `additions` calls `commands` and `commits`. Nothing here reaches the workflow layer, so the ceiling
  a count is compared against, and the verdict that comparison earns, stay with the caller.
- `snapshots/` — `namespace` is string policy and reaches nothing, which is what lets the late domain's lineage
  record consult it on every pinned read without paying for the transport; `refs` calls `ref_transport` for the
  remote read and the lease-pinned write and delete, `branch_transport` for the fetch, and `commands` for the
  hardened local resolution that proves what the fetch brought. The workflow decides WHEN a snapshot is taken and
  what its absence costs; this package decides only what a snapshot ref IS and refuses everything outside it.
- `worktrees/` — the creators call `commands`, `locks`, `branch_transport`, and their `paths` / `recovery` siblings;
  `decomposition` resolves its own path helper; `terminal` composes its local teardown from `cleanup`. The read-only
  scan sits on the same owners: `inventory` calls `probes` and `attribution`, and `paths` itself for the checkout path
  it hands back; `probes` and `attribution` reach `paths` too, for the names they compare against, and only `probes`
  reaches `commands` and `locks`. `models` carries only data. Nothing in the scan writes, fetches, or names GitHub,
  which is what lets a caller take it at any point in a tick. The classification over it keeps that split visible:
  `evidence` calls `commands`, `locks`, `paths`, both `git/verification/` tree reads (the status one, and the
  ignored-path one git leaves out of it and out of its own refusal to remove a dirty worktree), and
  `branch_transport` for the one question a local ref may not answer — what the remote says a branch is at;
  `claims` names GitHub and reaches `paths` for the branch names it asks GitHub about rather than for anything on
  disk; `eligibility` calls both and nothing else. None of the three writes anything, on the host or on GitHub.
  `obligations` is where that changes, and only just: it calls `commands` and `locks` for the notes it writes into the
  clone's own ref store and `paths` for the repository segment its namespaces are keyed by, and it reaches no remote,
  no GitHub, and neither the scan nor the classification. What is done about a note it hands back is the caller's.
  `reclamation` is the one that destroys, and it sits on top of all of them: `commands` and `locks` for the removal
  and the boundary it runs inside, `paths` for the one checkout path it will act on, `evidence` for the readings it
  retakes, and `obligations` for the anchor it pins what it is about to take under. It takes no verdict of its own —
  `eligibility` is not among its imports, and a candidate arrives already judged.
- `base_sync/` — `models` and `state` carry only data. On the sync side `refresh` calls `pre_pr` and `pr`, `pr` asks
  `eligibility`, `startup`, and `publication` in that order, and `guards` ends in `persistence`. On the recovery
  side `recovery` calls `snapshot`, `outcomes`, and `persistence`. The three keyword-call adapters — the PR sync,
  the conflict route, and the crash recovery — still take the argument lists their callers spell and normalize each
  into the typed context entry point beside it.
