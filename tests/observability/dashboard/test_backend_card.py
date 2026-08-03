# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What one backend's row is worth by the time it is a card.

The three readings the card exists for are read off the rendered string, since
that is where an operator reads them: what a million tokens cost, how much of
the billable input the cache answered, and what one run cost. Each is checked
against a row whose numbers make the arithmetic visible -- a token band split
evenly between input and cache read is a fifty-percent hit rate no matter what
the denominator is spelled as -- and against a row a backend barely ran in,
because every one of those ratios divides by something a thin window can leave
at zero.

The tint, the type, and the two number formatters are read back as the ones the
caller handed in rather than any this package holds, and both a backend name and
a formatted spend are read back escaped: the first arrives off the sink, and the
second is whatever the caller's own formatter returned.
"""

from __future__ import annotations

import unittest

from orchestrator.observability.analytics.query.cost_models import (
    BackendEfficiencyRow,
)
from orchestrator.observability.dashboard import backend_card
from tests.observability.dashboard.card_test_support import (
    BACKEND_CLAUDE,
    BACKEND_CODEX,
    BODY_FONT,
    BORDER,
    CLAUDE_COLOR,
    MONO_FONT,
    card_theme,
)

_SPEND = 8.0

_ONE_MILLION = 1_000_000

_BILLED_TOKENS = 2 * _ONE_MILLION

_EVEN_CACHE_HIT_PCT = 50

_RUNS = 4

# Half the billed band is cache read and half is input, so the cache-hit
# reading is 50% while the per-million one divides by the whole 2M band.
_EVEN_CACHE_ROW = BackendEfficiencyRow(
    backend=BACKEND_CLAUDE,
    runs=_RUNS,
    total_cost_usd=_SPEND,
    total_input_tokens=_ONE_MILLION,
    total_output_tokens=0,
    total_cache_read_tokens=_ONE_MILLION,
    total_cache_write_tokens=0,
)

# A backend the window carries no work for, so every ratio behind the card
# divides by zero unless the guard answers first.
_EMPTY_ROW = BackendEfficiencyRow(
    backend=BACKEND_CODEX, runs=0, total_cost_usd=float(),
)

_UNSAFE_BACKEND = "ba<ck>"

_ESCAPED_BACKEND = "ba&lt;ck&gt;"


def _rendered(row: BackendEfficiencyRow) -> str:
    """The card `row` is drawn as, under the injected theme."""
    return backend_card.backend_efficiency_card_html(row, theme=card_theme())


class BackendEfficiencyMetricsTest(unittest.TestCase):
    """The three readings a card reports, and the guard under each: a run
    count, a token band, or a cache-plus-input total of zero reports nothing
    rather than raising on a window a backend barely ran in.
    """

    def test_each_reading_has_its_own_denominator(self) -> None:
        metrics = backend_card.backend_efficiency_metrics(_EVEN_CACHE_ROW)
        self.assertEqual(metrics.tokens, _BILLED_TOKENS)
        self.assertEqual(metrics.cost_per_million, _SPEND / 2)
        self.assertEqual(metrics.cost_per_run, _SPEND / _RUNS)
        self.assertEqual(metrics.cache_hit_pct, _EVEN_CACHE_HIT_PCT)

    def test_an_empty_window_reports_zero_everywhere(self) -> None:
        metrics = backend_card.backend_efficiency_metrics(_EMPTY_ROW)
        self.assertEqual(metrics.tokens, 0)
        self.assertEqual(metrics.cost_per_million, float())
        self.assertEqual(metrics.cost_per_run, float())
        self.assertEqual(metrics.cache_hit_pct, float())


class BackendEfficiencyCardHtmlTest(unittest.TestCase):
    """The card is hand-rolled markup so the caller can render one
    `st.markdown` per backend, and every figure on it is the reading beside
    its own unit.
    """

    def test_the_readings_reach_the_card(self) -> None:
        rendered = _rendered(_EVEN_CACHE_ROW)
        self.assertIn(f"{_RUNS} runs", rendered)
        self.assertIn("$4.00 / 1M tok", rendered)
        self.assertIn("50% cache hit", rendered)
        self.assertIn("$2.00 / run", rendered)

    def test_an_empty_window_still_draws_a_card(self) -> None:
        rendered = _rendered(_EMPTY_ROW)
        self.assertIn("$0.00 / 1M tok", rendered)
        self.assertIn("0% cache hit", rendered)
        self.assertIn("$0.00 / run", rendered)

    def test_the_injected_theme_paints_it(self) -> None:
        # The page hands one theme object to every builder, so a card that
        # resolved a hue or a font of its own would be a panel painted off a
        # palette the chrome around it was not.
        rendered = _rendered(_EVEN_CACHE_ROW)
        self.assertIn(f"border:1px solid {BORDER}", rendered)
        self.assertIn(f"background:{CLAUDE_COLOR}", rendered)
        self.assertIn(f"font-family:{MONO_FONT}", rendered)
        self.assertIn(f"font-family:{BODY_FONT}", rendered)

    def test_both_figures_go_through_the_formatters(self) -> None:
        rendered = _rendered(_EVEN_CACHE_ROW)
        self.assertIn(f"~{_BILLED_TOKENS} tok", rendered)
        # The spend is whatever the caller's formatter returned, so it is
        # escaped on the way in like any other value the card is handed.
        self.assertIn("&lt;8.00", rendered)

    def test_the_backend_name_is_escaped(self) -> None:
        rendered = _rendered(
            BackendEfficiencyRow(backend=_UNSAFE_BACKEND, runs=1),
        )
        self.assertIn(_ESCAPED_BACKEND, rendered)
        self.assertNotIn(_UNSAFE_BACKEND, rendered)


if __name__ == "__main__":
    unittest.main()
