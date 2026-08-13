# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Decomposer-led architecture discussion on an operator-applied `discussion` label.

Nothing routes an issue in or out of this stage automatically. An operator
applies the label to have the design argued out before anyone commits to it,
and what comes back is an analysis on the issue thread: the repository facts
the agent found for itself, the branches the design could take, and a numbered
frontier of the questions a human can answer right now, each with a recommended
answer. No branch is pushed, no PR is opened, no developer or reviewer is
spawned, and the issue leaves only when a human relabels or closes it. That
"discuss, then wait" contract is the whole reason the stage is shaped the way
it is -- the agent is told to write nothing and decide nothing on its own, and
every owner here is arranged so a round that acted anyway is caught before it
can be published as a design.

The owners divide by what one tick has to decide. `handler` holds the order --
a park this stage wrote is the humans' turn and earns nothing, a checkout
already holding work is preserved rather than run over, otherwise the round and
then its disposition -- and it is where the stage stops: nothing below it
reaches another stage. `run` is the round itself, opened in the issue's own
`issue-N` worktree, and it owns the probes that bracket the spawn as well as
the records it stages around it, because both are about telling this round's
work apart from what the checkout was already carrying. `outcomes` is where the
no-write contract is enforced: commits and a dirty tree are checked before
interruption and before the analysis, so an agent that started implementing
parks on that rather than being read as a design. `parks` is every ending, each
stamped with the reason the next tick's turn-taking gate reads back. `state`
and `models` hold the wire keys, the park reasons, and the carriers between
them, so what a park is called and what a round is identified by are decidable
without a client.

Callers import the owner they need, so this initializer binds nothing: the
dispatcher resolves one handler per issue, and an eager binding here would
charge every importer of one stage for the agent, worktree, and GitHub
machinery only a discussion round reaches.
"""
