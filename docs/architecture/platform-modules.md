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
- **No second site.** No domain here sits behind a facade. Where a package replaced flat modules — `git/` and four
  of its six subpackages, `runtime/`, `skills/` — its own `test_imports.py` asserts that nothing resolves at the
  retired spelling, that no inventory or resolver hook names one as a target, and that no aggregate over the git
  domains sits above them — `tests/git/publication/test_imports.py` carries that last one. `git/measurement/` and
  `git/snapshots/` replaced nothing and hold the surface assertion anyway. The rule also holds one name at a time
  where a second binding would be invisible: the transport reaches the token lookup, the askpass session, and the
  session record through `credentials` rather than importing the three by name, and `tests/git/test_imports.py`
  asserts each is bound on that owner and nowhere in `authentication` — a copy there would read as the patch target
  a test aims at while the session a call actually opens stayed the owner's.
- **Operator log channels.** Four names are spelled literally rather than derived from `__name__`, because an
  operator's level and handler selection is keyed on them: `orchestrator.git_plumbing` (`git/authentication.py`,
  `git/credentials.py`, `git/snapshots/refs.py`, and the two `git/measurement/` owners that log, which all report on
  the same token, `ls-remote`, fetch, push, and diff plumbing),
  `orchestrator.base_sync` (`git/base_sync/state.py`), `orchestrator.worktree_lifecycle` (the nine `git/worktrees/`
  owners that log), and `orchestrator.branch_publication` (`git/publication/rewrite.py`). A module moved between
  packages does not take its channel with it, and each of the four names is asserted where its owner is tested —
  `tests/git/test_authentication.py` and `tests/git/test_credentials.py`, `tests/git/base_sync/test_state.py`,
  `tests/git/worktrees/test_imports.py`, and `tests/git/publication/test_imports.py`.
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
                        through, whether a marker on a thread is one of ours, and the reserved prefix every receipt
                        this orchestrator hides shares -- so content somebody else wrote can be refused before it is
                        embedded; the low-level comment and review readers stay raw
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
    authentication.py   the authenticated fetches, the remote-ref reads that answer what a branch or a whole refname
                        is at without a local one, the lease-pinned branch push, and the lease-pinned ref write and
                        delete an immutable namespace is owned through -- each spending one credential session
    commands.py         plain / hardened git execution, the argv hardening and no-prompt environment, the per-call
                        environment pin a caller adds over it, the absolute `--work-tree` argument a working-tree
                        operation names its tree with, and the unsafe local-transport probe
    credentials.py      the per-repo token lookup, the owner-only askpass script that outlives no operation, and
                        the session record a token-bearing call is spawned from -- the detached environment, the
                        URL naming only the `x-access-token` username, and the token the transport redacts with
    locks.py            the per-target-root re-entrant lock registry and its accessor
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
      models.py         the typed failure vocabulary, one frozen end of a diff, and the measurement record
      commits.py        the remote-authoritative base freeze (fetched once when the object is missing) and the
                        candidate proof that an id resolves, is held here, and peels to the commit it names --
                        each handing back whatever id it did establish beside the failure, so a retry has one
                        exact object to ask for
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
                        and rewrite its index -- and the two a named commit is judged by
      process.py        one command's group spawn / kill / drain and its verdict
      runner.py         the stripped child environment and the fail-fast command sequencing
    worktrees/          the per-issue checkouts an agent runs in, the read-only inventory of which issues they
                        and the branches beside them name, the classification of which of those may be
                        reclaimed, and the teardown that takes the cleared ones down -- with the ledger that
                        carries an unfinished one of those across a restart
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
                        the commits an eligible one hands over as cleared. Then what the teardown answers with:
                        the three surfaces an artifact lives on, the cleaned / absent / failed one step leaves,
                        and the whole per-surface record a caller reads a partly-finished reclamation off
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
      evidence.py       the six hardened reads a candidate is judged by -- a checkout that is a worktree of this
                        clone and on one of this issue's own branch names, a tree that PROVED it carries nothing
                        loose, a local branch tip, the commit the checkout's own HEAD stands on and which branch
                        that HEAD is, what the REMOTE
                        says a branch is at, and whether the base the remote named already contains a given tip
                        -- each answering "could not read" apart from git's own no, and a base nobody named
                        counted as the first. The two remote questions go over the authenticated `ls-remote`
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
                        tip can still sit under a branch the remote has been pushed past. Reported as one verdict
                        per candidate carrying every reason it is kept for
      reclamation.py    the destructive step, and the only writer in the artifact domain: an eligible verdict is
                        spent, never re-derived, and everything it established is established again at the
                        boundary it is about to be spent at -- the checkout still this issue's own, still clean,
                        and still on the commit that was cleared before a `worktree remove` that does not force,
                        the local branch deleted through an `update-ref -d` naming the old value and refused
                        while any live worktree of the clone is still standing on it, since that one protection
                        `branch -D` has and the ref update does not, and the remote branch through the same
                        lease-pinned delete the snapshot namespace is reclaimed under. Ownership is re-derived
                        for every ref, so only the two names this issue publishes under and the one path its
                        creators derive can be touched. Already-absent is success; the checkout comes down
                        before the branch it is on, and the remote branch before the local one, since the local
                        artifacts are what the scan finds a half-finished teardown back by. What that ordering
                        cannot cover -- a local artifact somebody took before the teardown reached it, leaving
                        nothing to hold back -- is covered by the record beneath: every remote deletion is
                        written down before it is attempted and let go once it has happened or stopped being
                        owed, one that could not be written down is not attempted, and the second entry point
                        here finishes the records rather than the candidates, which is the pass a restart
                        reaches for
      obligations.py    the ledger those records live in: one ref per branch under
                        `refs/orchestrator/remote-reclaim/`, valued at the commit the classification cleared, so
                        what a later pass may spend it on is a deletion of exactly that commit. A ref rather
                        than a file, because that is where this domain's durable state already lives and it is
                        written under the same lock; outside `refs/heads/`, so the artifact scan does not read
                        one as a candidate of its own, and outside the snapshot namespace, which is published.
                        The read-back answers "could not read" apart from "nothing owed" -- a listing that
                        warned, a line that did not parse, and a ref outside the namespace all refuse the whole
                        answer, since a ledger short by one entry is indistinguishable from a complete one.
                        Nothing here reads a remote or deletes anything on one
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
  and the verification probes; `rewrite` calls `commands`, `authentication`, and those probes; `squash` calls
  `planning` and `rewrite`.
- `verification/` — `output` calls `models`, `process` calls `output` and `probes`, and `runner` calls `process`.
- `measurement/` — `models` carries only data. `commits` calls `commands`, `authentication`, and the verification
  probes for the two object reads; `additions` calls `commands` and `commits`. Nothing here reaches the workflow
  layer, so the ceiling a count is compared against, and the verdict that comparison earns, stay with the caller.
- `snapshots/` — `namespace` is string policy and reaches nothing, which is what lets the late domain's lineage
  record consult it on every pinned read without paying for the transport; `refs` calls `authentication` for the
  remote read, the lease-pinned write and delete, and the fetch, and `commands` for the hardened local resolution
  that proves what the fetch brought. The workflow decides WHEN a snapshot is taken and what its absence costs; this
  package decides only what a snapshot ref IS and refuses everything outside it.
- `worktrees/` — the creators call `commands`, `locks`, `authentication`, and their `paths` / `recovery` siblings;
  `decomposition` resolves its own path helper; `terminal` composes its local teardown from `cleanup`. The read-only
  scan sits on the same owners: `inventory` calls `probes` and `attribution`, and `paths` itself for the checkout
  path it hands back; `probes` and `attribution` reach `paths` too, for the names they compare against, and only
  `probes` reaches `commands` and `locks`. `models` carries only data. Nothing in the scan writes, fetches, or names
  GitHub, which is what lets a caller take it at any point in a tick. The classification over it keeps that split
  visible: `evidence` calls `commands`, `locks`, `paths`, the `git/verification/` status probe, and
  `authentication` for the one question a local ref may not answer — what the remote says a branch is at;
  `claims` names GitHub and reaches `paths` for the branch names it asks GitHub about rather than for anything on
  disk; `eligibility` calls both and nothing else. None of the three writes anything, on the host or on GitHub.
  `reclamation` is where that changes: it calls `evidence` for the readings it takes again at the boundary, `paths`
  for the two branch names and the one checkout path a teardown for an issue may touch — and for the issue a record
  names — `commands` and `locks` for the removal and the ref delete, `obligations` for the record either side of the
  remote deletion, and `authentication` for the lease-pinned delete itself. `obligations` calls `commands` and
  `locks` and nothing else, and reaches no remote. Neither reaches `eligibility` or GitHub — the verdict a teardown
  is handed is the whole of the permission, and a record is the same permission written down.
- `base_sync/` — `models` and `state` carry only data. On the sync side `refresh` calls `pre_pr` and `pr`, `pr` asks
  `eligibility`, `startup`, and `publication` in that order, and `guards` ends in `persistence`. On the recovery
  side `recovery` calls `snapshot`, `outcomes`, and `persistence`. The three keyword-call adapters — the PR sync,
  the conflict route, and the crash recovery — still take the argument lists their callers spell and normalize each
  into the typed context entry point beside it.
