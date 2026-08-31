# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What one polling run is built from before its first tick.

The options an operator started it with, one authenticated client per
configured repository, and the single scheduler every tick hands work to. Each
of the three reads the configuration inside its own call, so a run reflects the
environment it was started in rather than the one this module was imported in.

`RepoClients` is what `connect_clients` hands back and what every pass over the
repositories is typed by: the spec stays paired with the client built for it,
because the pairing is what a tick would otherwise have to reconstruct.
"""
from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from typing import Optional

from orchestrator import config
from orchestrator.github.client import GitHubClient
from orchestrator.scheduler import IssueScheduler

log = logging.getLogger("orchestrator")

RepoClients = list[tuple[config.RepoSpec, GitHubClient]]

_ISSUE_THREAD_PREFIX = "orch-issue"


@dataclass(frozen=True)
class PollingOptions:
    """Parsed polling-loop command-line options."""

    once: bool
    log_level: str


def parse_options(argv: Optional[list[str]]) -> PollingOptions:
    """Parse single-tick and log-level command-line options."""
    parser = argparse.ArgumentParser(
        description="chipping-orchestrator polling loop.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single tick and exit.",
    )
    parser.add_argument("--log-level", default="INFO")
    parsed_options = parser.parse_args(argv)
    return PollingOptions(
        once=parsed_options.once,
        log_level=parsed_options.log_level,
    )


def connect_clients() -> RepoClients:
    """Connect once per configured repository and ensure its labels."""
    clients: RepoClients = []
    for repo_spec in config.default_repo_specs():
        github_client = GitHubClient(repo_spec=repo_spec)
        log.info("connected: repo=%s", repo_spec.slug)
        github_client.ensure_workflow_labels()
        clients.append((repo_spec, github_client))
    return clients


def create_scheduler() -> IssueScheduler:
    """Build the process-wide scheduler shared by every polling tick."""
    return IssueScheduler(
        global_cap=config.MAX_PARALLEL_ISSUES_GLOBAL,
        per_repo_cap=config.MAX_PARALLEL_ISSUES_PER_REPO,
        thread_name_prefix=_ISSUE_THREAD_PREFIX,
    )
