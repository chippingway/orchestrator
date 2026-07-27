# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""How one issue becomes a manifest, and what that manifest becomes.

Four workflow labels share this package because they share one artifact. The
decomposer runs on `decomposing` and answers with a single fenced manifest;
`single` sends the issue straight to `ready`, and `split` turns the manifest's
children into real GitHub issues and leaves the parent on `blocked` or
`umbrella` until every one of them resolves. The parent-side labels are the
back half of the same decision, so the manifest that produced the children and
the walk that waits on them belong in one package rather than one per label.

The owners divide by what each is responsible for rather than by label:
`manifest` and `validation` decide what the agent's reply is allowed to be,
`session` owns the decomposer session an issue is locked to and every spawn
or resume under it, `run` owns the order one tick asks the others in and
`outcomes` the three dispositions its reply earns, `recovery` owns what a tick
that died mid-split left behind, `split` owns the crash-safe order children are
created in, and `parents`, `activation`, `blocked`, and `umbrella` own the
parent-side polling that drives the tree to completion.

Callers import the owner they need, so this initializer binds nothing: the
dispatcher resolves one handler per label, and an eager binding here would
charge the `blocked` walk for the manifest parser and the split writer it
never reaches.
"""
