# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The event families a run appends to the analytics sink.

One owner for the analytics JSONL's own append and the three producer-facing
recorders that reach it directly -- a stage entered, a stage evaluated, and a
repo's skill catalog scanned. They sit together because they are one
vocabulary: an event name, the envelope it satisfies, and the extras it adds
are decided in the same place a reader looks for the shape a record has. The
fourth family, a tracked agent run's exit, composes four steps before it
writes and owns them on ``agent_exit`` beside this module, which reaches back
here for the append. The envelope and the log channel are the shared ``sink``
owner's, because the trajectory sink satisfies the same envelope and reports
on the same channel; they are republished here as the import site a producer
already names.

Where the file is and whether it exists at all is answered by the ``config``
owner above this package, read off the ``settings`` holder beside it inside
the call. Each recorder dispatches its own ``append_record`` on this module,
which is what makes ``patch.object(events, "append_record", ...)`` intercept
an internal append.

This is the bottom of the recording graph: it names ``config``, ``sink``, and
``models``, and none of its siblings, which is what lets the ``agent_exit``
composition above it reach the append here. Nothing under ``trajectories``
names it -- an ``agent_exit`` composes that write, so those owners take the
envelope and the channel off ``sink`` instead, and the layering check under
``tests/observability/analytics/trajectories/`` rejects the back edge.
"""

from __future__ import annotations

import typing

from orchestrator.observability.analytics import config as analytics_config
from orchestrator.observability.analytics import sink
from orchestrator.observability.analytics.recording.models import (
    STAGE_EVALUATION_SIGNATURE,
    bind_stage_evaluation,
)

# The envelope and the log channel are the shared sink owner's, republished
# here because this is the import site a producer reaches them at.
build_record = sink.build_record
log = sink.log
_SkillPaths = dict[str, list[str]]


def append_record(record: dict) -> None:
    """Append one JSONL line to the configured analytics sink."""
    sink.append_jsonl_record(
        analytics_config.live_settings().log_path,
        sink.ANALYTICS_FILE_LOCK,
        record,
    )


def record_stage_enter(*, repo: str, issue: int, stage: str) -> None:
    """Append the `stage_enter` analytics record emitted alongside the audit
    event of the same name.

    Centralized so `GitHubClient._emit_stage_enter` and the in-memory fake
    in `tests/support/github/` agree on the record shape without re-inlining the
    `build_record`/`append_record` pair. Disabled-sink behavior is
    inherited from `append_record` (no-op when the sink is off).
    """
    append_record(
        build_record(
            repo=repo,
            issue=int(issue),
            event="stage_enter",
            stage=stage,
        )
    )


def record_stage_evaluation(*args: typing.Any, **kwargs: typing.Any) -> None:
    """Append one stage-evaluation event through the typed request model."""
    request = bind_stage_evaluation(args, kwargs)
    append_record(
        build_record(
            repo=request.repo,
            issue=request.issue,
            event="stage_evaluation",
            stage=request.stage,
            duration_s=request.duration_s,
            result=request.evaluation_result,
        ),
    )


record_stage_evaluation.__signature__ = STAGE_EVALUATION_SIGNATURE


def record_repo_skill_catalog(
    *,
    repo: str,
    base_branch: str,
    remote_name: str,
    skills_available: list[str],
    skill_paths: typing.Optional[_SkillPaths] = None,
) -> None:
    """Append one `repo_skill_catalog` analytics record for a spec.

    Repo-level, not issue-scoped: `issue` is the sentinel `0` so the
    record still satisfies the `ts` / `repo` / `issue` / `event` envelope
    that both the JSONL sink and the Postgres `analytics_events` schema
    require, with no DDL change -- `base_branch`, `remote_name`,
    `skills_available`, and `skill_paths` all land in the `extras` JSONB
    column. `skill_paths` is dropped when None (`build_record` drops None
    extras), so an empty catalog records `skills_available: []` -- the
    "scanned, found none" signal -- without an empty `skill_paths`.
    Disabled-sink behavior is inherited from `append_record` (no-op when
    the sink is off). Centralized here so the producer in
    `orchestrator.skills.catalog` does not re-inline the record shape.
    """
    append_record(
        build_record(
            repo=repo,
            issue=0,
            event="repo_skill_catalog",
            base_branch=base_branch,
            remote_name=remote_name,
            skills_available=skills_available,
            skill_paths=skill_paths,
        )
    )
