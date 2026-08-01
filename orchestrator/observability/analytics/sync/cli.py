# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The command one replay is started by, and what it reports back.

`python -m orchestrator.observability.analytics.sync.cli` is the entry point:
three arguments, the logging an operator watches the run through, the service
beneath it, and one run reported twice -- as an exit code a cron or systemd
unit branches on, and as a summary line stdout keeps even when the log stream
is filtered away. The two overrides exist so a rotated or archived JSONL file
can be replayed against another database without touching the environment the
sink itself is configured by.

Both surfaces are pinned to UTC and say so. The formatter converts with
`time.gmtime` and stamps an explicit `UTC` suffix, and the summary is built
from `datetime.now(timezone.utc)`, so a piped `2>&1` on a host whose local
clock is offset stays one time-ordered stream rather than two that disagree by
hours. The converter is set on the formatter instance rather than on
`logging.Formatter`, whose attribute is process-wide and would drag every other
formatter -- a test's own included -- into UTC with it. The handler replaces
whatever the root already carried, because `basicConfig` silently keeps the
first one and a second `main` in the same process would then log through the
formatter it thought it had just installed.

A failure is answered with its elapsed time and exit 1 rather than a traceback,
since the exit code is what the scheduler reads. The service is named on this
module rather than bound into the call that drives it, so what an interception
aimed here replaces is what the command actually runs.
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from orchestrator.observability.analytics.sync.models import SyncResult
from orchestrator.observability.analytics.sync.run import sync_jsonl_to_postgres

log = logging.getLogger("orchestrator.analytics.sync")


def configure_cli_logging(level: str) -> None:
    """Install a UTC-stamped log formatter on the root logger."""
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S UTC",
    )
    formatter.converter = time.gmtime

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    for prior_handler in list(root.handlers):
        root.removeHandler(prior_handler)
    root.addHandler(stream_handler)


def cli_parser() -> argparse.ArgumentParser:
    """Build the parser one replay is asked for through."""
    parser = argparse.ArgumentParser(
        prog="python -m orchestrator.observability.analytics.sync.cli",
        description=(
            "Replay records from ANALYTICS_LOG_PATH into the Postgres "
            "analytics service at ANALYTICS_DB_URL. Deduplicates by "
            "content hash so repeated runs are idempotent. No-op when "
            "either env var is unset or the JSONL file is absent."
        ),
    )
    parser.add_argument(
        "--log-path",
        type=Path,
        default=None,
        help=("Override ANALYTICS_LOG_PATH for this run. Useful for replaying a rotated / archived JSONL file."),
    )
    parser.add_argument(
        "--db-url",
        default=None,
        help=(
            "Override ANALYTICS_DB_URL for this run. Accepts any libpq "
            "URL so a one-off replay against a different database does "
            "not require touching the environment."
        ),
    )
    parser.add_argument("--log-level", default="INFO")
    return parser


def print_cli_result(sync_result: SyncResult, cli_start: float) -> None:
    """Print the UTC summary retained even when structured logs are hidden."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    duration_s = sync_result.duration_s or round(time.monotonic() - cli_start, 3)
    sys.stdout.write(
        f"{timestamp} analytics_sync: inserted={sync_result.inserted} "
        f"duplicate={sync_result.skipped_duplicate} "
        f"malformed={sync_result.skipped_malformed} "
        f"total_lines={sync_result.total_lines} "
        f"duration_s={duration_s:.3f}\n"
    )


def run_cli(args: argparse.Namespace) -> int:
    """Drive one replay and report it as an exit code and a summary line."""
    cli_start = time.monotonic()
    try:
        sync_result = sync_jsonl_to_postgres(
            log_path=args.log_path,
            db_url=args.db_url,
        )
    except Exception:
        log.exception(
            "analytics_sync: failed after %.3fs",
            time.monotonic() - cli_start,
        )
        return 1
    print_cli_result(sync_result, cli_start)
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    """Parse `argv`, install the operator's logging, and run the replay."""
    args = cli_parser().parse_args(argv)
    configure_cli_logging(args.log_level)
    return run_cli(args)


if __name__ == "__main__":
    sys.exit(main())
