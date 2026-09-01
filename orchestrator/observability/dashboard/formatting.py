# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""How a figure reads once it is small enough to fit on the page.

A KPI tile, an axis tick, and a per-bar label are all narrower than the numbers
the read model hands back, so each formatter here trades digits for a suffix at
a fixed threshold. They live together because the page is read across those
surfaces at once: a card reporting `$3.4M` beside an axis reporting `3400000`
is one dataset shown two ways, and the thresholds are what keep the two
agreeing.

Every formatter takes exactly one number and each carries that signature
explicitly, which is what lets a caller pass it by the `value` keyword -- how
the chart builders hand a column to one -- and still bind the argument the
positional call binds.
"""
from __future__ import annotations

from inspect import Parameter, Signature
from typing import Any

# Decimal scales the compact money/token formatters divide by.
_MILLION = 1_000_000
_BILLION = 1_000_000_000


def _numeric_value(args: tuple[Any, ...], kwargs: dict[str, Any]) -> float:
    return _VALUE_SIGNATURE.bind(*args, **kwargs).arguments["value"]


def fmt_money(*args: Any, **kwargs: Any) -> str:
    """Compact dollar formatter matching the standalone mock (`$1.2K`,
    `$3.4M`). Used by KPIs, axis tick labels, and per-bar value labels.
    """
    dollars = float(_numeric_value(args, kwargs) or 0)
    if dollars >= _MILLION:
        millions = dollars / _MILLION
        return f"${millions:.2f}M"
    if dollars >= 1_000:
        thousands = dollars / 1_000
        return f"${thousands:.1f}K"
    if dollars < 10:
        return f"${dollars:.2f}"
    return f"${dollars:.0f}"


def fmt_money_exact(*args: Any, **kwargs: Any) -> str:
    """Whole-dollar formatter with thousands separators (`$12,345`)."""
    amount = round(float(_numeric_value(args, kwargs) or 0))
    return "${}".format(format(amount, ","))


def fmt_tokens(*args: Any, **kwargs: Any) -> str:
    """Compact token-count formatter (`1.2K`, `3.4M`, `1.2B`)."""
    tokens = float(_numeric_value(args, kwargs) or 0)
    if tokens >= _BILLION:
        decimals = 0 if tokens >= 10 * _BILLION else 2
        billions = tokens / _BILLION
        return "{}B".format(format(billions, f".{decimals}f"))
    if tokens >= _MILLION:
        decimals = 0 if tokens >= 10 * _MILLION else 1
        millions = tokens / _MILLION
        return "{}M".format(format(millions, f".{decimals}f"))
    if tokens >= 1_000:
        thousands = tokens / 1_000
        return f"{thousands:.0f}K"
    return str(round(tokens))


def fmt_num(*args: Any, **kwargs: Any) -> str:
    """Integer with thousands separators."""
    number = round(float(_numeric_value(args, kwargs) or 0))
    return format(number, ",")


_VALUE_SIGNATURE = Signature(
    (Parameter("value", Parameter.POSITIONAL_OR_KEYWORD),),
)
fmt_money.__signature__ = _VALUE_SIGNATURE
fmt_money_exact.__signature__ = _VALUE_SIGNATURE
fmt_tokens.__signature__ = _VALUE_SIGNATURE
fmt_num.__signature__ = _VALUE_SIGNATURE
