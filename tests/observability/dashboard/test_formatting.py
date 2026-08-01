# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""How a figure reads once it has been shortened to fit the page."""
from __future__ import annotations

import unittest

from orchestrator.observability.dashboard import formatting

# The compact count / token formatters render an integer zero as this bare
# string.
_ZERO_TEXT = "0"


class FormattersTest(unittest.TestCase):
    """The KPI strip, the axis ticks, and the per-bar labels all run through
    these, so the thresholds are what keep one dataset reading the same across
    the three surfaces it is shown on.
    """

    def test_fmt_money_handles_zero_and_small_values(self) -> None:
        cases = ((0, "$0.00"), (4.5, "$4.50"), (42, "$42"))
        for money_input, formatted in cases:
            with self.subTest(money_input=money_input):
                self.assertEqual(formatting.fmt_money(money_input), formatted)

    def test_fmt_money_uses_k_and_m_suffixes(self) -> None:
        cases = ((1_234, "$1.2K"), (2_500_000, "$2.50M"))
        for money_input, formatted in cases:
            with self.subTest(money_input=money_input):
                self.assertEqual(formatting.fmt_money(money_input), formatted)

    def test_fmt_money_exact_uses_thousands(self) -> None:
        cases = ((12_345.67, "$12,346"), (0, "$0"))
        for money_input, formatted in cases:
            with self.subTest(money_input=money_input):
                self.assertEqual(
                    formatting.fmt_money_exact(money_input), formatted,
                )

    def test_fmt_tokens_compact(self) -> None:
        cases = (
            (0, _ZERO_TEXT),
            (999, "999"),
            (1_500, "2K"),
            (2_500_000, "2.5M"),
            (12_000_000_000, "12B"),
        )
        for token_count, formatted in cases:
            with self.subTest(token_count=token_count):
                self.assertEqual(
                    formatting.fmt_tokens(token_count), formatted,
                )

    def test_fmt_num_thousands(self) -> None:
        cases = ((1234567, "1,234,567"), (0, _ZERO_TEXT))
        for count, formatted in cases:
            with self.subTest(count=count):
                self.assertEqual(formatting.fmt_num(count), formatted)

    def test_formatters_accept_value_keyword(self) -> None:
        # `value` is the public keyword every formatter exposes, and how the
        # chart builders hand a column to one.
        cases = (
            (formatting.fmt_money, 42, "$42"),
            (formatting.fmt_money_exact, 0, "$0"),
            (formatting.fmt_tokens, 999, "999"),
            (formatting.fmt_num, 0, _ZERO_TEXT),
        )
        for formatter, formatter_input, formatted in cases:
            with self.subTest(formatter=formatter.__name__):
                self.assertEqual(formatter(value=formatter_input), formatted)


if __name__ == "__main__":
    unittest.main()
