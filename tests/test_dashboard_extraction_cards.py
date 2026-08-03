# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Dashboard card extraction tests."""

import sys


import unittest


from types import MappingProxyType


from tests.dashboard_reload_helpers import (
    reload_dashboard as _reload,
)


DASHBOARD_CARDS_MODULE = "orchestrator.dashboard_cards"


ANALYTICS_DB_URL_ENV = "ANALYTICS_DB_URL"


CONFIGURED_DB_URL = "postgresql://h/db"


CONFIGURED_DB_ENV = MappingProxyType({ANALYTICS_DB_URL_ENV: CONFIGURED_DB_URL})


DASHBOARD_OWNERS = "orchestrator.observability.dashboard"


CARD_MARKUP_OWNER = f"{DASHBOARD_OWNERS}.card_html"


BACKEND_CARD_OWNER = f"{DASHBOARD_OWNERS}.backend_card"


COVERAGE_CARD_OWNER = f"{DASHBOARD_OWNERS}.coverage_card"


# Each builder the hub publishes and the owner under `observability/` that
# defines it. The hub itself is an import site, so a builder reporting the hub
# would be an implementation that came back to it.
_CARD_MEMBER_HOMES = MappingProxyType({
    "_card_header_html": CARD_MARKUP_OWNER,
    "_insights_html": CARD_MARKUP_OWNER,
    "_reliability_tiles_html": CARD_MARKUP_OWNER,
    "_backend_efficiency_card_html": BACKEND_CARD_OWNER,
    "_cost_coverage_bar_html": COVERAGE_CARD_OWNER,
})


class CardHtmlExtractionTest(unittest.TestCase):
    """The insight / backend-efficiency / cost-coverage / reliability-tile
    inline-HTML card family is reached through `orchestrator.dashboard_cards`,
    and `orchestrator.dashboard` re-exports each builder under the same
    name so the page pipeline and the `dashboard.<name>`
    surface keep resolving to the same object.
    """

    def test_card_members_report_their_home(self) -> None:
        _reload(CONFIGURED_DB_ENV)
        cards = sys.modules[DASHBOARD_CARDS_MODULE]
        for name, home in _CARD_MEMBER_HOMES.items():
            with self.subTest(name=name):
                self.assertEqual(getattr(cards, name).__module__, home)

    def test_facade_reexports_cards_objects(self) -> None:
        _, dashboard = _reload(CONFIGURED_DB_ENV)
        cards = sys.modules[DASHBOARD_CARDS_MODULE]
        for name in _CARD_MEMBER_HOMES:
            with self.subTest(name=name):
                self.assertTrue(
                    hasattr(dashboard, name),
                    f"dashboard dropped the historical {name!r} alias",
                )
                self.assertIs(getattr(dashboard, name), getattr(cards, name))
