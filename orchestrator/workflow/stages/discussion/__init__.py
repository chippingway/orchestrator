# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Decomposer-led architecture discussion on an operator-applied `discussion` label.

Nothing routes an issue INTO this stage: an operator applies the label to have
the design argued out before anyone commits to it, and what comes back is an
analysis on the issue thread -- the repository facts the agent found for
itself, the branches the design could take, and a numbered frontier of the
questions a human can answer right now, each with a recommended answer.
Answering by number resumes the same conversation, which redraws the tree
around what those answers settled and posts the frontier they opened up, for
as many rounds as the humans keep replying. No developer or reviewer is ever
spawned. What takes an issue OUT is a human deciding: a relabel, a close, or a
verdict on the plan PR below. The last two the stage records for itself, since
both are said off the thread where no round would ever read them; a relabel is
the operator moving the issue on by hand.

The conversation has exactly one artifact, and a human unlocks it. Once one of
them states on the thread that both sides understand the design the same way,
the same session writes that understanding into `plans/issue-N.md` and commits
it, and the stage publishes that commit as a pull request to review -- keeping
the label while the humans read it, opening no further round, and entering no
other stage. What they do with that pull request is what ends the conversation:
merging it is the design agreed and the issue finishes `done`, closing it
unmerged is the design declined and it finishes `rejected`, and either way the
checkout and the branches go with it. Everything
around that is the shape of the contract: nothing may be written before the
confirmation, and after it the branch is checked against the base and published
only when it is that one file and nothing else.

The owners divide by what one tick has to decide. `handler` holds the order --
a published plan is with the humans and `terminal` asks what they did with it,
a park this stage wrote is the humans' turn and earns a round only once one of
them replies, a checkout already holding work is preserved rather than run
over, otherwise the round and then its disposition -- and it is where the stage
stops: nothing below it reaches another stage. `terminal` is also the only
thing here that ends the issue: a plan PR the humans merged or closed finalizes
it and takes the checkout and the branches with it, an open one changes and
reaps nothing however long they take, and an issue closed before any plan
reached a pull request is recorded as rejected with the tree left where it is.
`session` is what keeps a conversation on one agent across all of them: the
pinned spec and session id a round is locked to, the trust filter
both the prompt and the consumed watermark are drawn through, and the choice
between resuming a live session and rebuilding the whole conversation for a
round that has none to resume. `run` is the round itself, opened in the issue's
own `issue-N` worktree, and it owns the probes that bracket the spawn as well
as the records it stages around it, because both are about telling this round's
work apart from what the checkout was already carrying. `outcomes` is where the
write contract is enforced: commits and a dirty tree are checked before
interruption and before the analysis, so an agent that started implementing is
judged on what it wrote rather than read as a design.

Publishing what that judgement passes divides by the question each owner
answers. `artifact` takes the one reading of the branch every other owner
decides and refuses from, and makes a remote tip askable in the checkout it was
taken from. `settled_prs` asks GitHub whether the commit is already on a pull
request the humans merged, closed, or pushed their own work past, which is what
has to be ruled out before anything is sent. `publication` is the re-runnable
order itself -- the durable marker, the lease, the push -- and `recovery` is
what comes back for a marker a tick died holding, since everything past that
write can leave the world changed. `plan_pr` opens or reuses the pull request
and makes its body name the session the plan came out of, refusing a plan no
session can be named for. `records` is what a finished publication writes down,
and which of the two durable writes those records ride.

The endings divide the same way the tick does. `parks` is the funnel all of
them go through, and the only thing that writes: it stamps the reason the next
tick's turn-taking gate reads back, so no ending can reach the issue without
one. Which ending is reached belongs to the owner whose question it answers --
`checkout_parks` for a tree holding work nothing may run over or refusing to be
read, `publication_parks` for what a reading of the committed plan earned, and
`outcome_parks` for what the run itself came back with -- and `park_messages`
holds the wording all three quote, so one checkout is described one way however
it is reported. `state` and `models` hold the wire keys, the park reasons, the
plan path both the prompt and the check are drawn from, and the carriers
between them, so what a park is called and what a round is identified by are
decidable without a client.

Callers import the owner they need, so this initializer binds nothing: the
dispatcher resolves one handler per issue, and an eager binding here would
charge every importer of one stage for the agent, worktree, and GitHub
machinery only a discussion round reaches.
"""
