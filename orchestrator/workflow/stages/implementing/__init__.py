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

What a finished run leaves behind is three more: `disposition` compares HEAD
against the pre-agent SHA to tell this run's commit from carried-over work,
`publication` turns a clean tree into a pushed branch, a PR, and the validating
handoff, and `parks` owns the four ways a commit-less run stops. The last four
own the signals that arrive between runs -- a body edit (`drift`), a body edit
before any session existed plus the quiet timeout recovery
(`drift_preflight`), an operator's `/orchestrator continue` (`continue_command`),
and a `question` -> `implementing` relabel (`question_relabel`) -- over the
records they hand each other (`models`) and the pinned-state keys and CLI
markers they share (`state`).

Callers import the owner they need, so this initializer binds nothing: the
dispatcher resolves one handler per issue, and an eager binding here would
charge a park or a session read for the publication path it never reaches.
"""
