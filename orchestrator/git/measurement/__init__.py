# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Size-measurement domain owners.

What a measurement IS -- the typed failure vocabulary, the one end of a diff a
freeze produces, and the record a completed count hands back -- lives in
``models``; the two commits it is taken between, each established before it
counts for anything, in ``commits``; and the added-line count over the diff
between them, plus the measurement that composes all three, in ``additions``.

The division is by what a caller is asking. A caller that has to PIN the
commits (before it spawns anything, or after a crash, so the retry measures the
same pair) asks ``commits``; one that has a pinned pair already and only needs
the number asks ``additions``. Nothing here decides what a number means: the
configured ceiling and the strictly-past-it comparison belong to the record
that is adjudicated against them, so this domain answers "how many lines, or
why not" and stops.

Every name is defined on one of these owners and callers import the owner they
need directly, so this initializer binds nothing and importing the count never
charges the importer for the authenticated transport the freeze needs.
"""
