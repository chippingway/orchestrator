# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Usage-parsing owners.

Destination for the provider payloads one finished agent run is metered from:
the codex and claude event streams, the model price table an estimate falls
back to, the skills a run triggered, and the per-turn breakdown a claude
trajectory carries.

Callers import the owner they need, so this initializer binds nothing. The
parser is what a tracked run folds its per-issue counters from, so no owner
here may reach the workflow that calls it -- the dependency runs the other
way, and a parser is fed a payload rather than an issue.
"""
