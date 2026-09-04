# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Prospective-diff domain owners.

One diff and two readings of it. What a reading IS -- the typed failure
vocabularies, the one end of a diff a freeze produces, the record a completed
count hands back, the fingerprint of what lies between two ends, and the
readback saying whether an end this host was supposed to hold is really here
-- lives in ``models``; the two commits every reading is taken between, each
established before it counts for anything, in ``commits``; the added-line
count over the diff between them, plus the measurement that composes all
three, in ``additions``; and the digest naming which contribution that diff is
in ``fingerprint``.

The division is by what a caller is asking. A caller that has to PIN the
commits (before it spawns anything, or after a crash, so the retry reads the
same pair) asks ``commits``; one that has a pinned pair already and needs the
number asks ``additions``, or the identity asks ``fingerprint``. Nothing here
decides what either answer means: the configured ceiling and the
strictly-past-it comparison belong to the record that is adjudicated against
them, and so does what two equal digests license, so this domain answers "how
many lines, which contribution, or why neither" and stops.

Every name is defined on one of these owners and callers import the owner they
need directly, so this initializer binds nothing and importing the count never
charges the importer for the authenticated transport the freeze needs.
"""
