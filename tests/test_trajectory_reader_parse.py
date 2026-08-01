# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The historical parse call shape the trajectory reader answers on."""

import unittest


from orchestrator import trajectory_reader as tr


_TS = "2026-06-20T10:00:00+00:00"


_ISSUE = 7


_SEQUENCE = 3


def _record():
    return {
        "ts": _TS,
        "repo": "acme/widgets",
        "issue": _ISSUE,
        "event": "agent_trajectory",
        "steps": [],
    }


class ParseCallShapeTest(unittest.TestCase):
    """`parse_record` binds the record as `obj` and the line count as `seq`.

    The owner under `observability/trajectory_viewer/` narrows a record
    through its own `sequence` keyword; this is the site the historical
    spelling is bound at, and every caller parsing a line of its own drives it
    by name, so both halves have to stay bindable rather than positional-only.
    """

    def test_the_record_may_be_passed_by_name(self) -> None:
        run = tr.parse_record(obj=_record(), seq=_SEQUENCE)
        assert run is not None
        self.assertEqual((run.issue, run.seq), (_ISSUE, _SEQUENCE))
