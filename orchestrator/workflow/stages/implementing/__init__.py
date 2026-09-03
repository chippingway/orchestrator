# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""One dev session per issue, from the first spawn to the PR it hands off.

The owners here divide by the decisions one `implementing` tick makes rather
than by the code those decisions run. `handler` owns the order they are asked
in. `spawn` decides whether anything runs at all -- an awaiting-human tick
belongs to the human's reply, and a worktree that already carries commits is a
publication an earlier tick was interrupted mid-way through.

The locked dev session is four owners because a resume is not one act:
`session_read` says what the pinned state claims the session is and what a
failed run's own text says about its health, `session` decides when it is
retired and gates a fresh spawn against the per-issue daily cap, `resume` keeps
the call shape every other stage wrote against, and `execution` runs one attempt
plus the single poisoned-session retry behind it, in `worktree`'s checkout.

What a finished run leaves behind is four more: `disposition` compares HEAD
against the pre-agent SHA to tell this run's commit from carried-over work,
`late_gate` measures whatever it is about to publish and holds a candidate
past the size ceiling unpublished under `workflow:decomposing`, `publication`
turns a clean tree into a pushed branch, a PR, and the validating handoff, and
`parks` owns the five ways a commit-less or unpublishable run stops. The gate
sits inside the disposition rather than beside it because being the ONE seam
all three committed outcomes publish through -- a finished run, a timeout that
committed first, and a branch a crash stranded -- is what makes the
measurement a contract rather than a check.

`late_gate` is the order its own questions are asked in and nothing else, so
five owners sit under it: what one gate call is ABOUT and the identity every
refusal is reported under is `late_records`, the pair a count is taken over is
`late_freeze`, what a recovery proves before it acts on a recorded commit is
`late_evidence`, what a measured candidate earns -- the push, the
`workflow:decomposing` hold, and the retirement each is durable behind -- is
`late_verdict`, and the one park shape every unreadable reading takes, with
the typed failure both sinks carry, is `late_parks`.

A candidate the remote already carries is the same gate one seam further on,
and eight more owners divide it the way the seam itself divides: what a call
taken past publication has to freeze before it may measure at all -- the
stage, the pull request, the head it stands on, and the five refusals that
make freezing them fail closed -- is `late_overflow`; the switch, the record,
and the count asked in one place so the seam that reached the gate makes no
difference to the answer is `late_publication`; the one call every push onto a
pull request the remote already carries goes through -- measure, push named
and leased, spend the debt, prove the checkout again -- is `late_push`, so a
pull request cannot be grown past the ceiling a commit at a time; the push a
human's adjudication already accepted, taken with no measurement but over a
checkout re-proved, is `late_accepted`; the push a squash-on-approval makes
over the branch it just rewrote -- entered on that publication before anything
destructive runs, then measuring the commit the squash MADE, since that is
what would go onto the pull request -- is `late_rewrite`; the reading the dispatcher
takes ahead of every handler for a pair this issue froze and never counted is
`late_reconcile`; the approval that same dispatcher pays ahead of it,
where a crash past the write that granted one left no record to reconcile
from, is `late_debt`; and what a pinned record CLAIMS about either -- and the
claims nothing may act on, since every field here is read fail-closed and a
group missing a member parses as no group -- is `late_claims`. The last five
own the signals that arrive between runs -- a body edit (`drift`), a body edit
before any session existed plus the quiet timeout recovery
(`drift_preflight`), an operator's `/orchestrator continue` (`continue_command`),
the park a spent spawn budget leaves and the one command that lifts it
(`retry_cap`), and a `question` / `discussion` -> `implementing` relabel
(`read_only_relabel`)
-- over the records they hand each other (`models`) and the pinned-state keys
and CLI markers they share (`state`).

The relabel divides again, because screening one is not the same act as
honouring the plan it hands over. `read_only_relabel` owns the screen itself --
which park it answers for, and the acceptance write that retires the
conversation's records -- while what the branch and the checkout are carrying is
`relabel_hazard`, what anything here has grounds to vouch for a tip sitting on
is `relabel_evidence`, and the idempotent park a finding earns, with the
remediation that clears it without destroying work worth keeping, is
`relabel_refusal`. The plan PR under the handoff is two more: `plan_reading`
says what its reviewers left on it and where that puts the checkout, and
`plan_handoff` takes that same reading again every tick until a developer
publishes, since the humans can move the head all through the window the
acceptance opens.

Callers import the owner they need, so this initializer binds nothing: the
dispatcher resolves one handler per issue, and an eager binding here would
charge a park or a session read for the publication path it never reaches.
"""
