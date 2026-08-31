# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a polling run is built from: options, clients, and the scheduler."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import patch

from orchestrator import config
from orchestrator.runtime import startup
from tests.runtime import polling_test_support as _support

_GITHUB_CLIENT_ATTR = "GitHubClient"
_DEFAULT_SPECS_ATTR = "default_repo_specs"
_GLOBAL_CAP_ATTR = "MAX_PARALLEL_ISSUES_GLOBAL"
_PER_REPO_CAP_ATTR = "MAX_PARALLEL_ISSUES_PER_REPO"
_GLOBAL_CAP = 4
_PER_REPO_CAP = 3
_LEVEL_FLAG = "--log-level"
_DEBUG_LEVEL = "DEBUG"
_DEFAULT_LEVEL = "INFO"
_PROCESS_ARGV = ("chipping-orchestrator",)


class OptionParsingTest(unittest.TestCase):
    """`--once` and `--log-level` are the whole command line, and an absent
    `argv` is the process's own.
    """

    def test_flags_and_defaults(self) -> None:
        for argv, expected in (
            ([], (False, _DEFAULT_LEVEL)),
            ([_support.ONCE_ARGS[0]], (True, _DEFAULT_LEVEL)),
            ([_LEVEL_FLAG, _DEBUG_LEVEL], (False, _DEBUG_LEVEL)),
            (
                [_support.ONCE_ARGS[0], _LEVEL_FLAG, _DEBUG_LEVEL],
                (True, _DEBUG_LEVEL),
            ),
        ):
            with self.subTest(argv=argv):
                options = startup.parse_options(argv)
                self.assertEqual(
                    (options.once, options.log_level),
                    expected,
                )

    def test_absent_argv_reads_the_process_argv(self) -> None:
        with patch.object(sys, "argv", [*_PROCESS_ARGV, *_support.ONCE_ARGS]):
            options = startup.parse_options(None)

        self.assertTrue(options.once)


class ClientConnectionTest(unittest.TestCase):
    """One client per configured spec, each paired with the spec it was built
    for and each bootstrapped once. Re-running the label bootstrap per tick
    would burn API calls on a no-op, so it belongs to the connect.
    """

    def test_one_bootstrapped_client_per_spec(self) -> None:
        specs = _support.repo_specs([_support.ALPHA_REPO, _support.BETA_REPO])
        clients = _support.ClientFactory()

        with (
            patch.object(config, _DEFAULT_SPECS_ATTR, return_value=specs),
            patch.object(startup, _GITHUB_CLIENT_ATTR, side_effect=clients),
        ):
            connected = startup.connect_clients()

        self.assertEqual(
            [(spec.slug, client.slug) for spec, client in connected],
            [
                (_support.ALPHA_REPO, _support.ALPHA_REPO),
                (_support.BETA_REPO, _support.BETA_REPO),
            ],
        )
        for client in clients.by_slug.values():
            client.ensure_workflow_labels.assert_called_once_with()


class SchedulerConstructionTest(unittest.TestCase):
    """The host-wide and per-repo ceilings come off the configuration at
    build time, so a run is bounded by the environment it was started in.
    """

    def test_caps_come_from_the_configuration(self) -> None:
        with (
            patch.object(config, _GLOBAL_CAP_ATTR, _GLOBAL_CAP),
            patch.object(config, _PER_REPO_CAP_ATTR, _PER_REPO_CAP),
        ):
            scheduler = startup.create_scheduler()

        self.addCleanup(scheduler.shutdown)
        self.assertEqual(
            (scheduler.global_cap, scheduler.per_repo_cap),
            (_GLOBAL_CAP, _PER_REPO_CAP),
        )


if __name__ == "__main__":
    unittest.main()
