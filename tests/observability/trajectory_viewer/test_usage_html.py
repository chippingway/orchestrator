# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a run's spend reads as, for the whole run and for one assistant turn."""
from __future__ import annotations

import unittest
from typing import Any

from orchestrator.observability.trajectory_viewer import models, usage_html
from tests.observability.trajectory_viewer.trajectory_viewer_test_support import run


_MODEL_CLAUDE = "claude-opus-4-8"

_MODEL_CODEX = "gpt-5-codex"

_ESTIMATED = "estimated"

_REPORTED = "reported"

_NO_USAGE = "no-usage"

_RUN_COST = 0.83

_RUN_INPUT = 41230

_RUN_OUTPUT = 5120

_RUN_CACHE_READ = 812440

_RUN_CACHE_WRITE = 20110

_CODEX_OUTPUT = 200

_CODEX_CACHED = 500

_CODEX_COST = 0.05

_TURN_COST = 0.0123

_TURN_INPUT = 12

_TURN_OUTPUT = 340

_TURN_CACHE_READ = 18240

_TURN_CACHE_WRITE = 512


def _claude_run_usage() -> models.RunUsageView:
    """The run summary a claude record carries, cache buckets and all."""
    return models.RunUsageView(
        models=(_MODEL_CLAUDE,),
        turns=9,
        input_tokens=_RUN_INPUT,
        output_tokens=_RUN_OUTPUT,
        cached_tokens=0,
        cache_read_tokens=_RUN_CACHE_READ,
        cache_write_tokens=_RUN_CACHE_WRITE,
        cost_usd=_RUN_COST,
        cost_source=_REPORTED,
    )


def _turn(**overrides: Any) -> models.TurnUsageView:
    """One priced assistant turn, overridable per test."""
    fields = {
        "turn": 0,
        "model": _MODEL_CLAUDE,
        "input_tokens": _TURN_INPUT,
        "output_tokens": _TURN_OUTPUT,
        "cache_read_tokens": _TURN_CACHE_READ,
        "cache_write_tokens": _TURN_CACHE_WRITE,
        "cost_usd": _TURN_COST,
        "cost_source": _ESTIMATED,
    }
    fields.update(overrides)
    return models.TurnUsageView(**fields)


class RunUsageHtmlTest(unittest.TestCase):
    """The run row draws the buckets the backend reported, and says so."""

    def test_claude_summary_chips_and_estimate_note(self) -> None:
        rendered = usage_html.run_usage_html(run(
            run_usage=_claude_run_usage(),
            turns=(_turn(),),
        ))
        for fragment in (
            ">Run usage</span>",
            _MODEL_CLAUDE,
            "9 turns",
            "cache-read 812,440",
            "cache-write 20,110",
            # The authoritative figure, named with its source and exact to
            # the cent, in the one chip drawn louder than the token pills.
            "reported $0.83",
            "orch-traj-chip cost",
            "authoritative when reported",
            "claude-only estimates",
            "need not sum to it",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, rendered)
        # `cached_tokens` is 0 on claude -> no always-zero cached chip.
        self.assertNotIn("cached ", rendered)

    def test_codex_summary_shows_not_available_note(self) -> None:
        rendered = usage_html.run_usage_html(run(run_usage=models.RunUsageView(
            models=(_MODEL_CODEX,),
            turns=3,
            input_tokens=1000,
            output_tokens=_CODEX_OUTPUT,
            cached_tokens=_CODEX_CACHED,
            cost_usd=_CODEX_COST,
            cost_source=_ESTIMATED,
        )))
        self.assertIn(_MODEL_CODEX, rendered)
        # Codex has no read/write split, so `cached_tokens` is its only cache
        # signal and must reach the row.
        self.assertIn("cached 500", rendered)
        self.assertIn("estimated $0.05", rendered)
        # No per-turn detail on this backend: the run summary plus a note that
        # says so, and never the estimates caveat.
        self.assertIn("not available for this backend", rendered)
        self.assertNotIn("need not sum to it", rendered)

    def test_pre_usage_record_renders_nothing(self) -> None:
        self.assertEqual(usage_html.run_usage_html(run()), "")

    def test_unpriced_run_names_source_without_cost(self) -> None:
        rendered = usage_html.run_usage_html(
            run(run_usage=models.RunUsageView(cost_source=_NO_USAGE)),
        )
        # Unpriced -> the cost chip names the source, no dollar figure.
        self.assertIn(f">{_NO_USAGE}</span>", rendered)
        self.assertNotIn("$", rendered)


class TurnUsageHtmlTest(unittest.TestCase):
    """The strip drawn above one assistant turn, and what it admits to."""

    def test_strip_carries_model_tokens_and_est_cost(self) -> None:
        rendered = usage_html.turn_usage_html(_turn())
        self.assertIn("orch-traj-turn", rendered)
        self.assertIn(_MODEL_CLAUDE, rendered)
        self.assertIn("in 12 tok", rendered)
        self.assertIn("out 340 tok", rendered)
        self.assertIn("cache-read 18,240", rendered)
        self.assertIn("cache-write 512", rendered)
        # Sub-cent precision so a small estimate is not floored to `$0.00`.
        self.assertIn("est. $0.0123", rendered)

    def test_cache_hit_chip_only_when_cache_read(self) -> None:
        self.assertIn("cache hit", usage_html.turn_usage_html(_turn()))
        self.assertNotIn(
            "cache hit", usage_html.turn_usage_html(_turn(cache_read_tokens=0)),
        )

    def test_unpriced_turn_reads_est_na(self) -> None:
        rendered = usage_html.turn_usage_html(
            _turn(cost_usd=None, cost_source="unknown-price"),
        )
        self.assertIn("est. n/a", rendered)

    def test_model_escaped(self) -> None:
        rendered = usage_html.turn_usage_html(_turn(model="<m>"))
        self.assertIn("&lt;m&gt;", rendered)
        self.assertNotIn("<m></span>", rendered)


if __name__ == "__main__":
    unittest.main()
