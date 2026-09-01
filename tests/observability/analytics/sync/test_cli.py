# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What one invocation asks for, exits with, and leaves an operator reading."""
from __future__ import annotations

import io
import logging
import re
import unittest
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from orchestrator.observability.analytics.sync import cli
from orchestrator.observability.analytics.sync.models import SyncResult
from tests.observability.analytics.sync.sync_test_support import (
    jsonl_log,
    sample_record,
)

# The two knobs an omitted argument falls back to, on the package they are
# bound on and where a caller patches one.
_LOG_PATH_SETTING = "orchestrator.observability.analytics.settings.ANALYTICS_LOG_PATH"

_DB_URL_SETTING = "orchestrator.observability.analytics.settings.ANALYTICS_DB_URL"

# The service the command drives, named on the command's own module so an
# interception aimed there is what the invocation actually runs.
_ENTRY_POINT = "sync_jsonl_to_postgres"

_STDERR = "sys.stderr"

_STDOUT = "sys.stdout"

_OVERRIDE_DB_URL = "postgresql://override/db"

_LOG_PATH_OPTION = "--log-path"

_DB_URL_OPTION = "--db-url"

# The anchor both surfaces carry: a UTC wall-clock with the zone spelled out.
_TIMESTAMP = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) UTC")

_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

# The summary an operator reads leads with that same anchor.
_SUMMARY = re.compile(f"^{_TIMESTAMP.pattern} analytics_sync:")

# Both surfaces are stamped within one invocation, so anything past a few
# seconds is a timezone apart rather than a slow run.
_CLOCK_TOLERANCE_SECONDS = 5


@contextmanager
def _disabled_sink() -> Iterator[None]:
    """Turn both knobs off so an argument-free run is a configured no-op."""
    with patch(_LOG_PATH_SETTING, None), patch(_DB_URL_SETTING, None):
        yield


def _drop_root_handlers() -> None:
    """Remove the handler `main` installed on the root logger."""
    root_logger = logging.getLogger()
    for stale_handler in list(root_logger.handlers):
        root_logger.removeHandler(stale_handler)


def _capture_main(test_case: unittest.TestCase, argv: list[str]) -> tuple[str, str]:
    """Run the command over `argv` and return what each stream received."""
    output_buffer = io.StringIO()
    error_buffer = io.StringIO()
    with patch(_STDOUT, output_buffer), patch(_STDERR, error_buffer):
        test_case.assertEqual(cli.main(argv), 0)
    return output_buffer.getvalue(), error_buffer.getvalue()


def _utc_timestamp(test_case: unittest.TestCase, text: str) -> datetime:
    """Read the first UTC stamp out of one surface's output."""
    matched = _TIMESTAMP.search(text)
    test_case.assertIsNotNone(matched, f"no UTC timestamp in {text!r}")
    return datetime.strptime(matched.group(1), _TIMESTAMP_FORMAT)


class CommandOutcomeTest(unittest.TestCase):
    """One invocation reports itself twice: as the summary line an operator
    reads off a terminal, and as the exit code a cron or systemd unit branches
    on. The two overrides are what a one-off replay of an archived file is
    driven by, so they have to reach the service rather than the environment.
    """

    def setUp(self) -> None:
        self.addCleanup(_drop_root_handlers)

    def test_a_no_op_run_prints_a_zeroed_summary(self) -> None:
        with _disabled_sink():
            printed, _ = _capture_main(self, [])
        self.assertRegex(printed, _SUMMARY)
        self.assertIn("inserted=0", printed)
        self.assertIn("duplicate=0", printed)
        # The elapsed wall-clock is what makes a multi-thousand-record replay
        # cost visible without grepping the log lines.
        self.assertIn("duration_s=", printed)

    def test_the_overrides_reach_the_service(self) -> None:
        service = MagicMock(return_value=SyncResult(inserted=1, total_lines=1))
        with jsonl_log([sample_record()]) as path:
            with patch.object(cli, _ENTRY_POINT, service):
                printed, _ = _capture_main(
                    self, [_LOG_PATH_OPTION, str(path), _DB_URL_OPTION, _OVERRIDE_DB_URL],
                )
            self.assertIn("inserted=1", printed)
            service.assert_called_once()
            self.assertEqual(service.call_args.kwargs["log_path"], path)
            self.assertEqual(service.call_args.kwargs["db_url"], _OVERRIDE_DB_URL)

    def test_a_failed_replay_exits_nonzero(self) -> None:
        # A driver error has to reach the scheduler as a code rather than a
        # traceback, since that is what an unattended run branches on.
        with (
            patch.object(cli, _ENTRY_POINT, side_effect=RuntimeError("boom")),
            patch(_STDOUT, io.StringIO()),
            patch(_STDERR, io.StringIO()),
        ):
            self.assertEqual(cli.main([]), 1)


class CommandClockTest(unittest.TestCase):
    """Both surfaces are pinned to UTC and say so, so a piped `2>&1` on a host
    whose local clock is offset stays one time-ordered stream instead of two
    that disagree by hours.
    """

    def setUp(self) -> None:
        self.addCleanup(_drop_root_handlers)

    def test_logs_and_stdout_share_a_utc_clock(self) -> None:
        with _disabled_sink():
            printed, logged = _capture_main(self, [])
        # The explicit marker is what tells a mixed-stream consumer the two
        # timestamps share a zone at all.
        self.assertIn(" UTC ", printed)
        self.assertIn(" UTC ", logged)
        printed_at = _utc_timestamp(self, printed)
        logged_at = _utc_timestamp(self, logged)
        self.assertLess(
            abs((printed_at - logged_at).total_seconds()),
            _CLOCK_TOLERANCE_SECONDS,
            f"stdout says {printed_at} and the log says {logged_at}",
        )
        # Cross-check the shared clock against UTC itself: a local-time
        # formatter would agree with a local-time summary and still be wrong.
        now_utc = datetime.now(UTC).replace(tzinfo=None)
        self.assertLess(
            abs((printed_at - now_utc).total_seconds()),
            _CLOCK_TOLERANCE_SECONDS,
            f"stdout says {printed_at}, not UTC",
        )


if __name__ == "__main__":
    unittest.main()
