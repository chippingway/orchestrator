# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What the run card writes out for a run's tool and skill chips."""

from unittest import TestCase, mock


from orchestrator import trajectory_reader as tr


_ISSUE = 42


def _td():
    from orchestrator import trajectory_dashboard as td

    return td


def _run(**overrides):
    record = {
        "ts": "2026-06-20T10:00:00+00:00",
        "repo": "acme/widgets",
        "issue": _ISSUE,
        "event": "agent_trajectory",
        "stage": "implementing",
        "agent_role": "developer",
        "backend": "claude",
        "steps": [],
    }
    record.update(overrides)
    return tr.parse_record(record, seq=0)


class RunChipRowsTest(TestCase):
    """Which of a run's three chip rows the card asks for.

    All three go through one chip builder, so what is pinned here is the
    card's own choice: which rows it draws at all, and which it draws with an
    empty-state marker.
    """

    def test_render_shows_empty_skills_triggered(self) -> None:
        # A session that fired no skill still shows the row, marked `none`, so
        # it is distinguishable from an omitted row; the equally-empty Tools
        # and Skills-available rows stay omitted.
        blob = self._render_chips()
        self.assertIn(">Skills triggered</span>", blob)
        self.assertIn('class="orch-traj-chip none"', blob)
        self.assertIn(">none</span>", blob)
        self.assertNotIn("Tools offered", blob)
        self.assertNotIn("Skills available", blob)

    def test_render_triggered_skills_are_plain_chips(self) -> None:
        blob = self._render_chips(skills_triggered=["develop", "review"])
        self.assertIn(">develop</span>", blob)
        self.assertIn(">review</span>", blob)
        self.assertNotIn('class="orch-traj-chip none"', blob)

    def _render_chips(self, **overrides) -> str:
        st = mock.Mock()
        _td()._render_run_usage_and_chips(st, _run(**overrides))
        return "".join(call.args[0] for call in st.markdown.call_args_list)
