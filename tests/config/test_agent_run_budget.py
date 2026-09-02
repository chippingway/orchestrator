# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The per-issue agent-run budget resolved from the environment."""

import unittest

from tests.config import config_reload_helpers as _reload, config_test_values as _config_cases


class MaxAgentRunsPerIssueConfigTest(unittest.TestCase):
    """The lifetime ceiling on the agent runs one issue may spend.

    A budget rather than a control, so `0` is the operator's own word for
    unlimited and resolves to it untouched. What aborts is what no budget can
    mean: a negative ceiling, which no run could ever come in under, and a
    value that is not a whole number of runs at all.
    """

    def test_default_is_fifty(self) -> None:
        config = _reload.load_config()
        self.assertEqual(
            config.MAX_AGENT_RUNS_PER_ISSUE,
            _config_cases._DEFAULT_MAX_AGENT_RUNS,
        )

    def test_a_finite_override_wins(self) -> None:
        config = _reload.load_config(
            {
                _config_cases._MAX_AGENT_RUNS_ENV: str(
                    _config_cases._OVERRIDE_MAX_AGENT_RUNS,
                ),
            }
        )
        self.assertEqual(
            config.MAX_AGENT_RUNS_PER_ISSUE,
            _config_cases._OVERRIDE_MAX_AGENT_RUNS,
        )

    def test_zero_is_unlimited_rather_than_an_abort(self) -> None:
        # The one value the positive-integer controls refuse is this budget's
        # way of turning itself off, so it has to survive resolution as 0.
        config = _reload.load_config(
            {_config_cases._MAX_AGENT_RUNS_ENV: _config_cases._DISABLED_ENV},
        )
        self.assertEqual(
            config.MAX_AGENT_RUNS_PER_ISSUE,
            _config_cases._UNLIMITED_MAX_AGENT_RUNS,
        )

    def test_blank_value_keeps_the_default(self) -> None:
        # An operator who commented the value out but left the key behind gets
        # the shipped ceiling rather than an abort or an accidental unlimited.
        config = _reload.load_config({_config_cases._MAX_AGENT_RUNS_ENV: "  "})
        self.assertEqual(
            config.MAX_AGENT_RUNS_PER_ISSUE,
            _config_cases._DEFAULT_MAX_AGENT_RUNS,
        )

    def test_an_invalid_budget_aborts_at_import(self) -> None:
        for spelling in ("plenty", "-1", "-50", "12.5", "1e3"):
            with self.subTest(value=spelling):
                error_message = _reload.config_error_message(
                    {_config_cases._MAX_AGENT_RUNS_ENV: spelling},
                )
                self.assertIn(_config_cases._MAX_AGENT_RUNS_ENV, error_message)
                self.assertIn(spelling, error_message)
