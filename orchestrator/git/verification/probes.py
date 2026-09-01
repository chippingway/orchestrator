# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""HEAD, worktree-state, and committed-path probes over what a run left behind.

Every probe here reads a worktree the agent can write to, so they go through
the command owner rather than assembling their own `git` invocation: the ones
that inspect working state need the hardened envelope's detached config, and
the HEAD probe must share the same no-prompt envelope so a credential-prompting
config cannot hang a worker.

They divide by what an agent could have left where. HEAD says whether it
committed at all -- and, beside it, whether HEAD is the branch a caller is
about to publish to, since a commit made detached leaves that ref where it was
while every other reading comes back identical -- the status read says what it
left loose, the two-commit path
read says what a commit actually changed, and the tree read says whether a
named path survived it as a regular file -- the last two are separate questions
on purpose, since a commit that DELETES a permitted path changes exactly that
path and leaves nothing behind it, and one that leaves a symlink or a gitlink
there changes it while leaving no document to read.

Those last two take their commits by object id rather than by ref. A caller
that inspects a branch and then publishes what it inspected has to be asking
about one commit throughout -- `HEAD` between two `git` invocations is whatever
the branch is on by then -- and it has to measure against a base nothing here
can move, since a linked worktree shares the object store its own agent writes
into. Both ends of the diff are therefore the caller's to establish, not this
module's to look up. `_commit_present` is what makes establishing one
answerable: an id can be read off a remote this repository has not fetched
from since, and a diff that names a commit git cannot resolve fails -- which
the path read reports as no paths, exactly what a branch that changes nothing
reports. `_commit_contains` is the same pair of ids asked a different question,
and the one a caller about to overwrite a ref needs: whether what is on that
ref survives being replaced by this commit.

`_ignored_paths` is the same tree read, bounded and collapsed, for the one
thing `status` leaves out of every answer above. Untracked and modified are what git itself calls dirty, and
they are what `worktree remove` refuses over; an ignored path is neither, so a
tree carrying nothing but those reports clean and a removal that does not force
takes them with it. A caller about to publish has no use for that -- ignored
output is exactly what it should not be pushing -- but one about to DELETE a
tree does: what the rules hide is still somebody's, and an `.env` beside a
build directory is not something to throw away on a repository's say-so.

`_worktree_status` and `_worktree_dirty_files` are the same read with different
answers for the same failure. The list form says "the paths git named", which
is what a caller refusing on a positive result wants; the status form says
whether git could be asked at all, which is what a caller that has to PROVE a
clean tree before pushing needs -- a corrupt index can fail `git status` while
a commit-to-commit diff still succeeds, and an empty list read as "clean" would
publish on the strength of a probe that never ran.

Proving it takes two things beyond running the command, because a clean answer
is one an agent can arrange without touching a single file it was asked about.
The working tree is NAMED on the command line rather than discovered, since
`core.worktree` in the per-worktree config redirects the whole read at another
directory -- and `-c` does not override that one, so only `--work-tree` says
which tree the answer is about. And the index is asked whether it has been told
to stop comparing: `assume-unchanged` and `skip-worktree` are index bits, not
config, so no envelope reaches them, and either one has `git status` report a
modified tracked file as clean. Both forms fail closed on them -- the paths come
back in the list so a caller refusing on what git named still refuses, and the
status form withholds `readable` so a caller that has to prove the tree empty
cannot.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import islice
from pathlib import Path

from orchestrator.git import commands as _commands

# What the two working-tree reads have to say for themselves, because the
# worktree's own `.git/config` is agent-writable and answers otherwise:
# `status.showUntrackedFiles=no` hides untracked paths from a status that asks
# for defaults, and `diff.ignoreSubmodules=all` hides a moved gitlink from a
# diff that does.
_UNTRACKED_ALL = "--untracked-files=all"

_IGNORE_SUBMODULES_NONE = "--ignore-submodules=none"

# What has `status` report the paths its ignore rules hide, how each of those
# is spelled in the report, and the untracked mode they are asked for beside.
#
# The mode is stated for two reasons at once. `status.showUntrackedFiles=no`
# in the repository the checkouts share stops the untracked walk, and this
# half of the report is what that walk turned up and then classified -- so
# asked for defaults it comes back empty over any number of hidden files. And
# `all` is what expands an ignored DIRECTORY into every file beneath it, so a
# tree carrying a dependency root would answer with a hundred thousand paths
# where `normal` answers with the root. Stating `normal` overrides the knob
# and keeps the collapse.
_IGNORED_ENTRIES = "--ignored"

_IGNORED_STATUS = "!! "

_UNTRACKED_NORMAL = "--untracked-files=normal"

# How many hidden paths are carried back. The caller's question is whether the
# tree is holding anything at all, and its answer is a refusal naming what an
# operator has to go and look at -- so what is past a handful is weight in a
# log line rather than information, however the collapse above went.
_IGNORED_LIMIT = 10

# What keeps a READ from writing. `git status` refreshes the index as it goes
# and writes the refreshed stat data back, which is a change to the repository
# made by a probe that was only asked a question -- and one that takes
# `index.lock` while it does it, so a status taken beside a running agent can
# fail on a lock neither of them needed. Every caller here is deciding whether
# to publish or to reclaim, and none of them is entitled to leave a mark on
# the tree it is deciding about.
_NO_OPTIONAL_LOCKS = "--no-optional-locks"

# What every read of a path here asks for. Git's default output quotes a name
# with anything unusual in it and separates records by newline, so a path can
# arrive escaped, or split across what reads as two entries. NUL-delimited it
# arrives as the bytes it is.
_NUL_DELIMITED = "-z"

# What `-z` separates those records with, spelled once: every read here splits
# on it, and a typo would read one record as a whole report.
_NUL_SEPARATOR = "\0"

# What porcelain's two status columns say when an entry came from somewhere
# else. Under `-z` the path it came FROM is its own record, following the one
# naming where it is now -- so a reader that did not expect the pair would take
# a bare path for a status line and cut three bytes off the front of it.
_RENAMED_STATUS = frozenset(("R", "C"))

# What `git ls-files -v` tags an index entry with when git has been told to
# stop comparing it against the working tree: `S` for skip-worktree, and a
# LOWERCASE tag of any letter for assume-unchanged.
_SKIP_WORKTREE_TAG = "S"

# What a tree entry has to be for a caller asking whether a document is at a
# path: the two modes git gives a regular file, and the object type that goes
# with them. A symlink (`120000`) and a gitlink (`160000`) are entries at the
# same path that are not the file anybody would read there.
_BLOB_TYPE = "blob"

_REGULAR_FILE_MODES = frozenset(("100644", "100755"))


def _head_sha(worktree: Path) -> str:
    """HEAD commit SHA of the worktree, or '' if it cannot be read.

    Used by the validating handler to detect whether a dev-fix codex run
    produced a new commit. _has_new_commits compares against origin/<base>,
    which is already true throughout validating, so we need an absolute SHA
    snapshot instead.
    """
    head_result = _commands._git("rev-parse", "HEAD", cwd=worktree)
    if head_result.returncode != 0:
        return ""
    return (head_result.stdout or "").strip()


@dataclass(frozen=True)
class _WorktreeStatus:
    """What `git status` said about a worktree, or that it could not say.

    `readable` is False when the read established nothing about the tree, and
    it is a separate field rather than an empty path list because the two mean
    opposite things to a caller that must not push over unproven state. The
    command failing is one way; an index entry git was told to stop comparing
    is the other, and that one also comes back in `paths` -- it is a thing to
    refuse on as well as a reason the rest cannot be called clean.
    """

    readable: bool
    paths: tuple[str, ...] = ()

    @property
    def is_clean(self) -> bool:
        """Whether this reading PROVED the tree is carrying nothing loose.

        What a caller whose next step is a push has to ask, and it is asked
        rather than truth-tested on `paths` for the reason the field beside
        them exists: a read that established nothing names no paths, which is
        what a tree with nothing in it names too. Only a reading that happened
        AND named nothing is a clean tree; everything else is a refusal,
        whichever half of it failed.
        """
        return self.readable and not self.paths


def _head_on_branch(worktree: Path, branch: str) -> bool:
    """True when this checkout's HEAD IS `branch` rather than a bare commit.

    The question a caller has to answer before it publishes a commit by SHA to
    `refs/heads/<branch>`. A commit made on a detached HEAD -- or on some other
    ref -- is a real commit in a real tree, and every reading of what it
    changed comes back the same, so nothing else here can tell the two apart.
    What differs is the branch: it stays where it was, and everything after the
    push reads it. The records name a commit the local ref does not carry, the
    relabel guard downstream convicts that stale tip of being unreviewed work,
    and a checkout rebuilt from it comes back without the plan.

    Answered from `symbolic-ref` rather than by comparing SHAs, because the two
    are different facts: a branch that happens to point at the same commit is
    not a HEAD that will move with it, and the next commit an agent makes
    detached would separate them again with nothing here having changed.

    Hardened for the reason every probe here is, and false on any failure --
    including a detached HEAD, which is exactly what a non-zero exit means for
    this command. A caller that cannot prove HEAD is the branch must proceed as
    though it is not.
    """
    ref_result = _commands._git_hardened(
        "symbolic-ref", "--quiet", "HEAD", cwd=worktree,
    )
    if ref_result.returncode != 0:
        return False
    return (ref_result.stdout or "").strip() == f"refs/heads/{branch}"


def _worktree_status(worktree: Path) -> _WorktreeStatus:
    """Read the worktree's modified and untracked paths, failure included.

    Hardened unconditionally: `git status --porcelain` refreshes the index,
    which spawns a configured `core.fsmonitor` helper -- and the agent can
    plant one in the worktree's `.git/config` or in `~/.gitconfig` (same OS
    user), so a plain probe would execute it with the orchestrator's process
    environment (ambient secrets) attached. Every call site is an
    agent-writable worktree, so there is no trusted caller that would want
    the unhardened form. Detaching global/system config also drops a global
    `core.excludesFile` from the untracked filter; the repo's own tracked
    `.gitignore` still applies, which is the intended trust boundary.

    Detaching does NOT reach the worktree's own `.git/config`, which the agent
    can write and which carries knobs that decide what `status` reports at all.
    `status.showUntrackedFiles=no` is the sharp one: set there, a probe reading
    defaults sees a clean tree over any number of untracked files. So what the
    report includes is stated on the command line, where local config cannot
    answer for it -- and so is HOW, since the default output quotes an unusual
    path and joins a rename onto one line, which is enough for a file named
    ` -> ` to read as rename syntax and leave the tree looking clean.

    WHICH tree it reports on is stated there too, and for a knob no override
    reaches. `core.worktree` in the per-worktree config (`config.worktree`,
    which an agent enables by writing `extensions.worktreeConfig` into the repo
    it shares) points discovery at another directory entirely, and a `-c
    core.worktree=` on the command line does not win against it -- so a probe
    that let git discover its own tree would report on a clean shadow checkout
    while the real one carried the agent's edits. `--work-tree` is what says
    otherwise, and it is the reason this answer is about the directory the
    caller named rather than the one the repository was talked into.

    Optional locks are off, which is what makes this a read. A `status` left
    to itself refreshes the index and writes the new stat data back, so a
    probe asking what a tree holds would modify the repository it is asking
    about -- and would contend for `index.lock` with whatever else is running
    in a tree an agent owns. Nothing about the answer changes; only whether
    taking it leaves a trace.

    Neither the envelope nor the flags above say anything about the index
    CONTENTS, which is where the last way out lives: `assume-unchanged` and
    `skip-worktree` are bits on an index entry rather than config, so nothing
    above reaches them, and either one has `status` skip the comparison and
    report a modified tracked file as clean.
    Those entries come back as paths AND withhold `readable`, because they are
    both things at once -- something the caller must refuse on, and a tree
    nothing here can call empty.
    """
    status_result = _commands._git_hardened(
        _commands._work_tree_arg(worktree),
        _NO_OPTIONAL_LOCKS,
        "status", "--porcelain", _NUL_DELIMITED,
        _UNTRACKED_ALL, _IGNORE_SUBMODULES_NONE,
        cwd=worktree,
    )
    if status_result.returncode != 0:
        return _WorktreeStatus(readable=False)
    suppressed = _suppressed_index_paths(worktree)
    if suppressed is None:
        return _WorktreeStatus(readable=False)
    reported = _reported_paths(status_result.stdout or "")
    if suppressed:
        return _WorktreeStatus(
            readable=False,
            paths=tuple(dict.fromkeys(reported + list(suppressed))),
        )
    return _WorktreeStatus(readable=True, paths=tuple(reported))


def _ignored_paths(worktree: Path) -> tuple[str, ...] | None:
    """What this tree carries that its own ignore rules hide, or None.

    Bounded and collapsed rather than exhaustive: a whole directory the rules
    cover comes back as the directory, and no more than a handful of entries
    come back at all. A caller deciding whether to delete a tree asks whether
    there is anything there and wants to be able to say what -- neither of
    which a hundred thousand paths answers better than ten.

    The one thing `_worktree_status` cannot report, and it is left out of that
    answer rather than folded into it because the two are spent differently: a
    caller deciding whether to publish is right to pass over ignored output,
    and a caller deciding whether to DELETE a tree is not. Git draws the same
    line -- `worktree remove` refuses a tree with untracked or modified files
    and takes an ignored one without a word -- so this is the read that stands
    between a reclamation and somebody's `.env`.

    `None` is the read that established nothing, kept apart from the empty
    answer for the reason every probe here keeps them apart: only an empty
    list proves the tree is hiding nothing, and a caller that read a failure
    as one would delete on the strength of a question nobody put.

    The same envelope as the status read above, and for the same reasons: the
    tree is named on the command line so per-worktree `core.worktree` cannot
    point the read at another one, optional locks are off so asking leaves no
    trace, and the report is NUL-delimited so a path cannot arrive quoted or
    joined. What the detached global config drops here is a global
    `core.excludesFile`, which costs nothing: a path hidden only by that file
    is not hidden from the untracked read beside this one, so between the two
    of them nothing on disk goes unreported.

    The untracked mode is stated here even though nothing untracked is read
    off the answer, and it is the load-bearing flag: `--ignored` reports what
    that walk turned up and then classified, so the local
    `status.showUntrackedFiles=no` an agent can write into the repository the
    checkouts share empties this report along with the other half. Asked for
    defaults, a tree holding an ignored secret answers that it holds nothing,
    which is the one answer that gets it deleted.

    `normal` rather than `all`, because `all` is what stops the collapse: a
    dependency root or a build tree would come back as every file beneath it,
    which is a report nobody reads and a walk this probe should never make.
    What comes back is bounded on top of that, since the answer is spent on a
    yes-or-no and a line naming what to look at.
    """
    listed = _commands._git_hardened(
        _commands._work_tree_arg(worktree),
        _NO_OPTIONAL_LOCKS,
        "status", "--porcelain", _NUL_DELIMITED,
        _IGNORED_ENTRIES, _UNTRACKED_NORMAL, _IGNORE_SUBMODULES_NONE,
        cwd=worktree,
    )
    if listed.returncode != 0:
        return None
    return tuple(islice(
        (
            record[len(_IGNORED_STATUS):]
            for record in (listed.stdout or "").split(_NUL_SEPARATOR)
            if record.startswith(_IGNORED_STATUS)
        ),
        _IGNORED_LIMIT,
    ))


def _reported_paths(status_stdout: str) -> list[str]:
    """Every path a NUL-delimited porcelain-v1 report names, in its own order.

    `-z` rather than the default line format, because the default is lossy in
    exactly the direction that costs something here. It quotes a path with
    anything unusual in it and spells a rename `<to> -> <from>` on one line, so
    an untracked file named ` -> ` comes back as `?? " -> "`: read as a rename,
    what follows the arrow is a lone quote, which is nothing once the quoting
    is undone -- and a tree holding that file reports clean, with a plan sitting
    beside it published as though the round had left nothing loose. Under `-z`
    nothing is quoted and nothing is joined, so there is nothing to guess at.

    The rename's source record is the one thing the loop carries state for: it
    is a bare path with no status columns in front of it, and taken for a
    status line it would lose its first three bytes. Both halves are reported,
    since a caller permitting exactly one path is entitled to know that a file
    left another one behind.
    """
    paths: list[str] = []
    renamed_from = False
    for record in status_stdout.split(_NUL_SEPARATOR):
        if renamed_from:
            renamed_from = False
            paths.append(record)
        elif len(record) > 3 and record[2] == " ":
            renamed_from = bool(_RENAMED_STATUS & set(record[:2]))
            paths.append(record[3:])
    return [path for path in paths if path]


def _suppressed_index_paths(worktree: Path) -> tuple[str, ...] | None:
    """Index entries git has been told not to compare, or None if unreadable.

    The one way a clean status can be arranged without config and without
    touching the file it is about. `git update-index --assume-unchanged` and
    `--skip-worktree` set bits on the index entry, which every `status` honors
    and no envelope can drop: the entry is reported as matching whatever is on
    disk, so a tracked file the agent rewrote comes back clean and the branch
    reads as publishable.

    An empty answer is the only one that proves nothing is suppressed, so the
    read failing is not it -- None says so, and the caller withholds `readable`
    rather than reading a list it could not take as "none set". The paths it
    does return are named so a refusal can quote them: what an operator has to
    clear is a bit on a specific entry, and "something in the index" would send
    them looking through the whole of it.

    Bound to the same tree and hardened for the same reasons as the status read
    beside it, since it answers half of the same question.
    """
    listed = _commands._git_hardened(
        _commands._work_tree_arg(worktree),
        "ls-files", "-v", _NUL_DELIMITED, "--full-name",
        cwd=worktree,
    )
    if listed.returncode != 0:
        return None
    # `-v -z` writes one `<tag> <path>` record per entry, NUL-terminated, and
    # `--full-name` with `-z` leaves the path unquoted -- so the first space is
    # the separator whatever the path itself contains.
    suppressed = []
    for record in (listed.stdout or "").split(_NUL_SEPARATOR):
        tag, _, path = record.partition(" ")
        if len(tag) == 1 and path and (
            tag == _SKIP_WORKTREE_TAG or tag.islower()
        ):
            suppressed.append(path)
    return tuple(suppressed)


def _worktree_dirty_files(worktree: Path) -> list[str]:
    """Paths git considers modified or untracked in the worktree.

    Used to refuse opening a PR when codex committed only part of its work and
    left other modifications behind -- the push would publish an incomplete
    branch. The orchestrator's own scratch (codex's `-o` file) lives outside
    the worktree (a per-spawn tempfile in `codex.run_codex`), so it never
    surfaces here regardless of the target repo's .gitignore.

    An unreadable worktree answers with no paths, which every caller here
    reads as "nothing to refuse on". That is the right shape for a refusal
    that fires on what git DID name; a caller whose next step is a push has to
    prove the opposite and asks `_worktree_status` instead.

    An index entry git has been told to stop comparing is the exception, and it
    comes back as a path: the status read cannot see the change under it, so a
    caller refusing on what git named would be told there is nothing to refuse
    on -- which is the whole point of setting the bit.
    """
    return list(_worktree_status(worktree).paths)


def _revision_contains_path(
    worktree: Path, revision: str, path: str,
) -> bool:
    """True when `revision`'s tree carries `path` as a regular file.

    Asked beside the base-relative diff because that diff cannot tell writing
    a path from deleting one: a commit that removes a file the base branch
    already carried changes exactly that path and nothing else, which a caller
    checking only the changed-path set would read as the artifact it asked
    for. Reading the object out of the commit is what separates the two.

    The MODE is part of the question, not decoration, because the caller is
    asking whether a document is there. Git stores three other things at a
    path: a symlink (`120000`, whose blob is a target string, so the artifact a
    reviewer opens is whatever it points at -- possibly outside the
    repository), a gitlink (`160000`, a commit id for a submodule nobody here
    fetches), and a directory. All three exist at the path and none is the
    plan, so "the object resolves" is the wrong test; both regular modes are
    accepted, since an executable bit on a Markdown file is odd rather than a
    different kind of artifact.

    The commit is named rather than left as `HEAD` for the same reason the
    diff below names it: a caller that decides by inspecting a commit and then
    publishes THAT commit must have inspected the one it publishes, and `HEAD`
    is a moving name -- an agent, another tick, or an operator can move it
    between two `git` invocations.

    Hardened for the reason every probe here is, and false on any failure --
    a caller that publishes on this must be told "no" when the tree cannot be
    read at all. `-z` for the reason the diff uses it: an unusual byte in the
    path would otherwise come back quoted and match nothing.
    """
    entry_result = _commands._git_hardened(
        "ls-tree", _NUL_DELIMITED, "--full-tree", revision, "--", path,
        cwd=worktree,
    )
    if entry_result.returncode != 0:
        return False
    # Each record is `<mode> SP <type> SP <object> TAB <path>`, and one path was
    # asked about: anything but a single record answers about something else,
    # and no record at all is the path being absent.
    records = [
        record for record in (entry_result.stdout or "").split(_NUL_SEPARATOR) if record
    ]
    if len(records) != 1:
        return False
    fields = records[0].split("\t", 1)[0].split()
    if len(fields) < 2:
        return False
    return fields[1] == _BLOB_TYPE and fields[0] in _REGULAR_FILE_MODES


def _commit_present(worktree: Path, revision: str) -> bool:
    """True when `revision` names a commit this repository can actually read.

    The question a caller has to ask before it RECORDS an object id, and the
    reason it cannot be skipped is the failure mode of the read below: a diff
    naming a commit git cannot resolve fails, and a failed read answers "no
    paths", which is what a branch that changes nothing also answers. An id
    pinned while it was absent therefore turns a branch carrying exactly the
    permitted path into a branch that reads as carrying none -- silently, and
    for as long as the record stands.

    It is a real question because the ends of that diff come from different
    places. A base id read off the remote is the remote's current answer, and
    this clone last fetched at some earlier point; the commit it names may
    simply not be here yet. A caller told so can bring it in and pin an id its
    own diff will resolve.

    `^{commit}` is part of the question rather than decoration: a tag or a tree
    at that id is not something the diff can measure from, so peeling is what
    makes a positive answer mean what the caller needs it to.

    Hardened for the reason every probe here is, and false on any failure --
    including the failure to run git at all, since a caller that cannot prove
    the object is here must proceed as though it is not.
    """
    object_result = _commands._git_hardened(
        "cat-file", "-e", f"{revision}^{{commit}}", cwd=worktree,
    )
    return object_result.returncode == 0


def _commit_contains(worktree: Path, ancestor: str, revision: str) -> bool:
    """True when `revision`'s history contains `ancestor`.

    The question a caller has to ask before it OVERWRITES a ref: publishing a
    commit over a tip that commit does not descend from deletes whatever was on
    that tip, and no lease can help -- a lease only proves the ref has not moved
    since it was read, not that what is there survives the push. Asked of the
    two object ids the caller established (the tip something else is on, and the
    commit being published), this is the fast-forward test, and refusing on it
    is what keeps a publication from taking history away.

    An ancestor this repository does not have answers False, because git cannot
    resolve it and a commit here plainly does not contain a commit this host has
    never seen. That is the right answer for the caller either way: it is a tip
    somebody produced elsewhere, so the push would discard it.

    Hardened for the reason every probe here is, and false on any failure --
    exit status 1 is git's "no", and anything else is a read that established
    nothing, which a caller about to overwrite a ref must treat as "no" too.
    """
    ancestry_result = _commands._git_hardened(
        "merge-base", "--is-ancestor", ancestor, revision, cwd=worktree,
    )
    return ancestry_result.returncode == 0


def _committed_paths_since(
    worktree: Path, base_sha: str, revision: str,
) -> list[str]:
    """Paths `revision` changes against the commit `base_sha` names.

    The counterpart to `_worktree_dirty_files` for work that is already
    committed, and the probe a caller with exactly one permitted path needs:
    the discussion stage publishes a branch only when the whole of it against
    the base is the plan file it asked for, which a commit count cannot answer.

    BOTH ends are object ids the caller established, and neither is a ref this
    host can rewrite. The commit, because the caller that reads this is the
    caller that then pushes: a reading of `HEAD` and a push of the SHA it
    captured a moment earlier are answers about two different commits the
    instant anything moves the branch between them. The base, because
    `refs/remotes/<remote>/<base>` lives in the object store the agent's
    worktree shares -- an agent that commits code, repoints that ref at its own
    commit, and then commits the permitted path would otherwise be measured
    against its own work and read as having changed only that path.

    Three-dot, so a base that moved on since the branch forked is not read as
    work this branch did. `--no-renames`, so a file moved onto the permitted
    path is reported as the deletion and the addition it is rather than as a
    single rename landing exactly where the caller was looking. `-z`, because
    the caller compares paths literally and git's default output quotes and
    escapes unusual bytes -- a quoted path would never match the one the agent
    was promised.

    `--ignore-submodules=none` for the reason the status read spells its own
    flags out: `diff.ignoreSubmodules=all` in the worktree's `.git/config` is
    agent-writable, and a caller that permits exactly one path would otherwise
    be told nothing about a gitlink the commit moved.

    Naming both ends by object id is only worth something because the hardened
    envelope turns object replacement off. `refs/replace/<oid>` and the graft
    file both make git serve one commit under another's name, and both are
    writable from the worktree -- an id that can be re-pointed is a name, not
    an identity, and this probe would be measuring against whatever the agent
    put behind it.

    Hardened for the reason the dirty probe is: every call site is a worktree
    the agent can write to, so a planted `core.fsmonitor` or alias would
    otherwise run with the orchestrator's environment attached. A failed read
    answers "no paths", which reads downstream as nothing publishable -- a
    probe that cannot say what a branch carries must never be the reason it is
    pushed.
    """
    diff_result = _commands._git_hardened(
        "diff", "--name-only", "--no-renames", _NUL_DELIMITED,
        _IGNORE_SUBMODULES_NONE,
        f"{base_sha}...{revision}",
        cwd=worktree,
    )
    if diff_result.returncode != 0:
        return []
    return [path for path in (diff_result.stdout or "").split(_NUL_SEPARATOR) if path]
