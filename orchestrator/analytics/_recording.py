# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Public analytics event recorders backed by event-family leaves."""

from __future__ import annotations

import datetime
import importlib
import logging
import os as os
import sys
import threading
import typing

from orchestrator.observability.analytics import config as analytics_config

_deps = importlib.import_module("orchestrator.analytics._recording_dependencies")


AgentResult = _deps.agents.AgentResult
_append_jsonl_record = _deps._recording_io._append_jsonl_record
_AgentExitContext = _deps._recording_models._AgentExitContext
_AgentExitSkillFields = _deps._recording_models._AgentExitSkillFields
_CodexCatalog = _deps._recording_models._CodexCatalog
AGENT_EXIT_SIGNATURE = _deps._recording_models.AGENT_EXIT_SIGNATURE
STAGE_EVALUATION_SIGNATURE = _deps._recording_models.STAGE_EVALUATION_SIGNATURE
bind_agent_exit = _deps._recording_models.bind_agent_exit
bind_stage_evaluation = _deps._recording_models.bind_stage_evaluation
_discover_codex_catalog = _deps._recording_catalog._discover_codex_catalog
_discover_codex_skills = _deps._recording_catalog._discover_codex_skills
_discover_codex_tools = _deps._recording_catalog._discover_codex_tools
_populate_codex_catalog = _deps._recording_catalog._populate_codex_catalog
_normalize_agent_exit_skills = _deps._recording_skills._normalize_agent_exit_skills
_parse_agent_exit_skills = _deps._recording_skills._parse_agent_exit_skills
_read_agent_exit_skills = _deps._recording_skills._read_agent_exit_skills
_parse_agent_exit_usage = _deps._recording_usage._parse_agent_exit_usage
_build_agent_exit_record = _deps._recording_agent_exit._build_agent_exit_record
_persist_agent_exit = _deps._recording_agent_exit._persist_agent_exit
_record_agent_exit = _deps._recording_agent_exit._record_agent_exit


_facade = sys.modules[__package__]
_FILE_LOCK = threading.Lock()
log = logging.getLogger(__package__)
_SkillPaths = dict[str, list[str]]
_COMPATIBILITY_MODULES = (os,)


def _live_settings():
    """Return the package instance this recorder module was imported alongside.

    Two things resolve through it: the patchable entry points the recorders
    dispatch to (`append_record`, `prune_old_records`,
    `append_trajectory_record`), and the settings holder they hand
    `config.settings_on` to read a knob off. It is deliberately the captured
    instance rather than whatever the package name resolves to now -- a caller
    that re-imports the package against a patched environment drives the
    instance it got back, so the current one would answer with the
    process-wide values instead.
    """
    return _facade


def build_record(
    *,
    repo: str,
    issue: int,
    event: str,
    stage: typing.Optional[str] = None,
    **extras: typing.Any,
) -> dict:
    """Build a single analytics record.

    `ts` is the current UTC time at second precision in ISO-8601 form.
    `stage` and any extra whose value is None are dropped so callers can
    pass optional context unconditionally without polluting records that
    don't carry them.
    """
    rec: dict[str, typing.Any] = {
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(
            timespec="seconds",
        ),
        "repo": repo,
        "issue": int(issue),
        "event": event,
    }
    if stage is not None:
        rec["stage"] = stage
    for key, field_value in extras.items():
        if field_value is not None:
            rec[key] = field_value
    return rec


def append_record(record: dict) -> None:
    """Append one JSONL line to the configured analytics sink."""
    _append_jsonl_record(
        analytics_config.settings_on(_live_settings()).log_path,
        _FILE_LOCK,
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
    _live_settings().append_record(
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
    _live_settings().append_record(
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
    _live_settings().append_record(
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


def record_agent_exit(
    *args: typing.Any,
    **kwargs: typing.Any,
) -> typing.Optional[list[str]]:
    """Parse, persist, and return triggered skills for one completed run."""
    return _record_agent_exit(bind_agent_exit(args, kwargs, _live_settings()))


record_agent_exit.__signature__ = AGENT_EXIT_SIGNATURE
