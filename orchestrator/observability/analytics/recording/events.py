# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The event families a run appends, and the sink line they land on.

One owner for every record the orchestrator writes to the analytics JSONL:
the envelope each of them shares, the append that puts one on disk, and the
four producer-facing recorders -- a stage entered, a stage evaluated, a repo's
skill catalog scanned, and a tracked agent run finished. They sit together
because they are one vocabulary: an event name, the envelope it satisfies, and
the extras it adds are decided in the same place a reader looks for the shape
a record has.

Where the file is and whether it exists at all is answered by the ``config``
owner above this package, read off a *settings holder* -- the flat
``orchestrator.analytics`` package, which is where the parsed knobs are bound
and where a caller patches one. The recorders also dispatch their own
``append_record`` through that holder, which is what makes
``patch.object(analytics, "append_record", ...)`` intercept an internal
append. ``settings_holder`` documents which instance answers.
"""

from __future__ import annotations

import datetime
import logging
import sys
import typing

from orchestrator.observability.analytics import config as analytics_config
from orchestrator.observability.analytics.recording.agent_exit import (
    record_agent_exit as _record_agent_exit,
)
from orchestrator.observability.analytics.recording.io import (
    ANALYTICS_FILE_LOCK,
    append_jsonl_record,
)
from orchestrator.observability.analytics.recording.models import (
    AGENT_EXIT_SIGNATURE,
    STAGE_EVALUATION_SIGNATURE,
    bind_agent_exit,
    bind_stage_evaluation,
)

# The flat analytics package: the settings holder, the patch surface, and the
# logger every sink failure is reported under. Spelled out rather than derived
# from `__package__` so relocating this owner leaves an operator's log filter
# and a caller's patch target where they were.
#
# The sink lock is deliberately not minted here: this module is rebuilt for
# each package instance, and an append and the prune it races have to hold one
# object, so it lives on the `io` owner that is loaded once per process.
_SETTINGS_HOLDER = "orchestrator.analytics"

# The holder instance this module was imported alongside, looked up rather
# than imported: that package imports this one, so binding the import here
# would cycle and make the compatibility package load-bearing rather than
# retirable. A lookup answers with the instance whose bootstrap pulled this
# module in, and with nothing at all when a producer imported the owner
# directly -- which is the case `settings_holder` resolves live.
_HOLDER = sys.modules.get(_SETTINGS_HOLDER)

log = logging.getLogger(_SETTINGS_HOLDER)
_SkillPaths = dict[str, list[str]]


def settings_holder() -> typing.Any:
    """Return the analytics package instance these recorders answer for.

    Two things resolve through it: the patchable entry points the recorders
    dispatch to (`append_record`, `prune_old_records`,
    `append_trajectory_record`), and the settings holder they hand
    `config.settings_on` to read a knob off. It is deliberately the instance
    captured at this module's own import rather than whatever the package name
    resolves to now -- a caller that re-imports the package against a patched
    environment drives the instance it got back, which is not the one
    installed under the package name afterwards, so the current one would
    answer with the process-wide values instead. The package's bootstrap
    reloads this module for each instance it initializes, which is what gives
    every instance its own capture.

    Nothing is captured when a producer imported this owner without the
    package behind it; the settings still live there, so that case resolves
    the name at call time.
    """
    if _HOLDER is None:
        from orchestrator import analytics

        return analytics
    return _HOLDER


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
    append_jsonl_record(
        analytics_config.settings_on(settings_holder()).log_path,
        ANALYTICS_FILE_LOCK,
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
    settings_holder().append_record(
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
    settings_holder().append_record(
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
    settings_holder().append_record(
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
    return _record_agent_exit(bind_agent_exit(args, kwargs, settings_holder()))


record_agent_exit.__signature__ = AGENT_EXIT_SIGNATURE
