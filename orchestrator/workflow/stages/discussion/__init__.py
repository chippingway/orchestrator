# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The stage behind the operator-applied `discussion` label.

The stage exists so that applying the label is safe rather than so that
anything happens: an issue humans are still arguing over is one the
orchestrator has to leave alone, and a label the dispatcher does not recognize
is one it logs a "not implemented yet" warning for on every tick. `handler` is
the whole stage -- one function that does nothing, so the label routes somewhere
and that somewhere touches no worktree, no agent, and no issue state.

Callers import the owner they need, so this initializer binds nothing, the same
contract every sibling stage keeps.
"""
