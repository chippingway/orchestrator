# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Analytics disabled-sink prune tests."""

import unittest


from tests.analytics_reload_helpers import reload_analytics as _reload


_ANALYTICS_LOG_PATH = "ANALYTICS_LOG_PATH"


class AnalyticsDisabledModeTest(unittest.TestCase):
    """With the sink disabled, `prune_old_records` is a silent no-op --
    no file is ever opened, pinned GitHub state is untouched, and the
    helper does not raise. The append side of the same switch is covered
    beside its owner under `tests/observability/analytics/recording/`.
    """

    def test_prune_returns_zero_when_disabled(self) -> None:
        _, analytics = _reload({_ANALYTICS_LOG_PATH: "off"})
        self.assertEqual(analytics.prune_old_records(), 0)
