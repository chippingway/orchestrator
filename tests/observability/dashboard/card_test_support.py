# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The theme the card builders are handed, spelled as a caller's own.

Both card owners take their border, type, hues, and number formatting off a
theme parameter rather than reaching for a palette, so the cases read them back
through one built here: every value is a marker no owner in the package holds,
which is what makes an assertion on the rendered markup evidence the injected
theme was used rather than a sibling module resolved behind the caller's back.

The color resolution itself is the palette owner's, because a card only names
the explicit map a hue is looked up in and the domain it is positioned against
-- picking one out of the two is a decision already made elsewhere.
"""

from __future__ import annotations

from types import MappingProxyType, SimpleNamespace

from orchestrator.observability.dashboard.palette import color_for

BORDER = "#111811"

TEXT = "#222822"

MUTED_TEXT = "#333833"

MONO_FONT = "TestMono"

BODY_FONT = "TestBody"

# The two backends and the one cost source a case names, each mapped to a hue
# only this module spells, so a card drawn in it can only have read it here.
BACKEND_CLAUDE = "claude"

BACKEND_CODEX = "codex"

CLAUDE_COLOR = "#440044"

CODEX_COLOR = "#004400"

COST_SOURCE_REPORTED = "reported"

REPORTED_COLOR = "#004444"


def _fmt_tokens(tokens: int) -> str:
    """Mark a token count as having gone through the injected formatter."""
    return f"~{tokens}"


def _fmt_money_exact(amount: float) -> str:
    """Mark a spend figure the same way, with the markup-unsafe `<` on it."""
    return f"<{amount:.2f}"


def card_theme() -> SimpleNamespace:
    """A theme carrying only values a case can attribute to this module."""
    return SimpleNamespace(
        BACKEND_COLORS=MappingProxyType({
            BACKEND_CLAUDE: CLAUDE_COLOR,
            BACKEND_CODEX: CODEX_COLOR,
        }),
        COST_SOURCE_COLORS=MappingProxyType({
            COST_SOURCE_REPORTED: REPORTED_COLOR,
        }),
        BORDER=BORDER,
        TEXT=TEXT,
        MUTED_TEXT=MUTED_TEXT,
        MONO_FONT_FAMILY=MONO_FONT,
        FONT_FAMILY=BODY_FONT,
        color_for=color_for,
        fmt_tokens=_fmt_tokens,
        fmt_money_exact=_fmt_money_exact,
    )
