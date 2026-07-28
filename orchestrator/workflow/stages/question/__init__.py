# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Read-only Q&A on an operator-applied `question` label.

Nothing routes an issue in or out of this stage automatically. An operator
applies the label to ask the agent something about the repository, and the
answer comes back as a comment: no branch is pushed, no PR is opened, and the
issue leaves only when a human relabels it or closes it. That read-only
contract is the whole reason the stage is shaped the way it is -- the agent is
told not to write, and every owner here is arranged so a run that wrote anyway
is caught before anything can be published.

The owners divide by what one tick has to decide. `handler` holds the order --
the closed-issue finalize outranks everything, then the run, then its
disposition -- and owns both worktree teardowns, because the scratch checkout
this stage never pushes has to disappear on the terminal arc and on every safe
exit alike. `run` picks between the two shapes a tick can take (resume a parked
conversation on a human reply, or start the first agent run), owns the spawn
they share, and owns the park funnel every exit lands on. `session` is the
locked identity that keeps a multi-turn Q&A on one backend: the `question_agent`
spec is pinned before the first spawn can fail, and both prompt builders sit
there together because the resume degrades to the first-round prompt when no
session id survived -- a followup handed to a fresh agent carries no issue body
to answer against.

`outcomes` is where the read-only contract is enforced. New commits and a dirty
tree are checked before interruption and before the answer itself, and both
park with the worktree kept: a misbehaving run's changes have to survive for an
operator to inspect, and the implementing stage's relabel guard reads the same
`question_*` park reason to refuse shipping them as dev work. `state` holds
those reasons and the two pinned-state keys, because the writer is never the
only reader -- `_UNSAFE_QUESTION_PARKS` decides the cleanup policy on entry and
the park reasons themselves are read from outside this package.

Callers import the owner they need, so this initializer binds nothing: the
dispatcher resolves one handler per issue, and an eager binding here would
charge every importer of one stage for the agent, worktree, and GitHub
machinery only a question run reaches.
"""
