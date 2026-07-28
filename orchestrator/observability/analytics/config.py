# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Analytics sink and database configuration.

One owner for the six environment knobs the analytics and trajectory sinks are
configured by: where each JSONL file is written and whether it is written at
all, how long the records in it are kept, whether a tracked run's skill
evidence is parsed, and the libpq URL the Postgres surfaces dial. The disable
vocabulary is shared -- an empty value and the sentinels `off` / `disabled` /
`none` (case-insensitive) turn a knob off wherever it appears -- so what "off"
spells and what it costs are settled together rather than agreeing by
coincidence across separate leaves.

Every knob is read out of the environment inside the call, never bound at
import, so a package re-imported against a patched environment resolves to
what that environment implies. `parsed_settings` is the whole set under the
names the analytics package publishes them as, which is what its bootstrap
binds, and `Settings` is how an adapter reads them back: `settings_on` for the
package instance a recorder captured at its own import, `live_settings` for
whichever instance the package name resolves to now. Both indirections point
at that package for as long as patching a setting on it is the interception a
caller makes; what they answer for is which instance is the caller's.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

_DISABLED_SENTINELS = ("off", "disabled", "none")

_TRUTHY_SPELLINGS = ("1", "true", "on", "yes")


@dataclass(frozen=True)
class Settings:
    """The six knobs as they stand on one settings holder.

    A view rather than a snapshot: each property reads its own attribute when
    asked, so a value patched between two reads reaches the second one, a
    short-circuited condition costs only the knob it actually evaluated, and a
    holder carrying just the knobs its caller touches stays usable.
    """

    holder: Any

    @property
    def log_path(self) -> Optional[Path]:
        return self.holder.ANALYTICS_LOG_PATH

    @property
    def retention_days(self) -> int:
        return self.holder.ANALYTICS_RETENTION_DAYS

    @property
    def db_url(self) -> Optional[str]:
        return self.holder.ANALYTICS_DB_URL

    @property
    def track_skill_triggers(self) -> bool:
        return self.holder.TRACK_SKILL_TRIGGERS

    @property
    def trajectory_log_path(self) -> Optional[Path]:
        return self.holder.TRAJECTORY_LOG_PATH

    @property
    def trajectory_retention_days(self) -> int:
        return self.holder.TRAJECTORY_RETENTION_DAYS


def _explicit_path(raw: Optional[str]) -> Optional[Path]:
    """Read one path knob whose value is an operator's explicit opt-in.

    Disabled for an unset variable, an empty value, or a disable sentinel. The
    two path knobs differ only in what an *unset* variable means, so the rest
    of the vocabulary is settled here once.
    """
    if raw is None:
        return None
    stripped = raw.strip()
    if not stripped or stripped.lower() in _DISABLED_SENTINELS:
        return None
    return Path(stripped)


def parse_log_path() -> Optional[Path]:
    """Resolve `ANALYTICS_LOG_PATH` from the environment.

    Unset -> default under `config.LOG_DIR` (already covered by the `logs/`
    .gitignore rule). Empty value and the sentinels `off` / `disabled` /
    `none` (case-insensitive) disable the sink entirely; `append_record` and
    `prune_old_records` become silent no-ops in that mode and no file is ever
    opened.

    `config` is imported inside the call rather than bound at module import so
    the default follows whichever `orchestrator.config` is current: a test that
    pops and re-imports the pair in lockstep to land a patched `LOG_DIR` sees
    the patched one.
    """
    from orchestrator import config

    raw = os.environ.get("ANALYTICS_LOG_PATH")
    if raw is None:
        return config.LOG_DIR / "analytics.jsonl"
    return _explicit_path(raw)


def parse_retention_days() -> int:
    """Resolve `ANALYTICS_RETENTION_DAYS` from the environment.

    Default 90 days. 0 (or any non-positive value) keeps raw data
    indefinitely -- `prune_old_records` becomes a no-op so operators can opt
    out of cleanup without disabling the sink itself.
    """
    return int(os.environ.get("ANALYTICS_RETENTION_DAYS", "90"))


def parse_db_url() -> Optional[str]:
    """Resolve `ANALYTICS_DB_URL` from the environment.

    Unset / empty value and the sentinels `off` / `disabled` / `none`
    (case-insensitive) disable the Postgres surfaces (sync + read model)
    entirely; a real URL passes through verbatim so a libpq connection string
    is the single-knob endpoint contract. The orchestrator's polling tick does
    not read this var, so an unset value has no effect on workflow
    correctness. Matches `ANALYTICS_LOG_PATH`'s disable knob so the two can be
    turned off together with parallel spellings.
    """
    raw = os.environ.get("ANALYTICS_DB_URL", "").strip()
    if not raw or raw.lower() in _DISABLED_SENTINELS:
        return None
    return raw


def parse_track_skill_triggers() -> bool:
    """Resolve `TRACK_SKILL_TRIGGERS` from the environment.

    Default off. When on, `record_agent_exit` runs the skill-trigger extractor
    (`observability/usage/skills.py`) and folds `skills_triggered` /
    `skills_triggered_count` / `skills_available` / `skills_evidence` /
    `skills_incidental` / `skills_incidental_count` into the `agent_exit`
    record. The switch defaults off *because* the sink itself is default-on
    (`ANALYTICS_LOG_PATH` -> `LOG_DIR/analytics.jsonl`): an on-by-default
    switch would silently add skill fields to every default install's records,
    breaking the "absent opt-in -> today's record shape" guarantee. Truthy
    spellings match `orchestrator.config`'s other boolean knobs: `1` / `true` /
    `on` / `yes` (case-insensitive).
    """
    raw = os.environ.get("TRACK_SKILL_TRIGGERS", "off")
    return raw.strip().lower() in _TRUTHY_SPELLINGS


def parse_trajectory_log_path() -> Optional[Path]:
    """Resolve `TRAJECTORY_LOG_PATH` from the environment.

    Opt-in / default off: unlike `ANALYTICS_LOG_PATH` (which defaults to a
    path under `config.LOG_DIR`), an *unset* `TRAJECTORY_LOG_PATH` disables
    the trajectory sink. Empty value and the sentinels `off` / `disabled` /
    `none` (case-insensitive) also disable it; any other value is the explicit
    opt-in path. When disabled, `append_trajectory_record` and
    `prune_trajectory_records` are silent no-ops and no file is ever opened.
    """
    return _explicit_path(os.environ.get("TRAJECTORY_LOG_PATH"))


def parse_trajectory_retention_days() -> int:
    """Resolve `TRAJECTORY_RETENTION_DAYS` from the environment.

    Default 90 days, matching `ANALYTICS_RETENTION_DAYS`. 0 (or any
    non-positive value) keeps trajectories indefinitely --
    `prune_trajectory_records` becomes a no-op so operators can opt out of
    cleanup without disabling the sink itself.
    """
    return int(os.environ.get("TRAJECTORY_RETENTION_DAYS", "90"))


def parsed_settings() -> dict[str, Any]:
    """Parse every knob under the name the analytics package publishes it as.

    One mapping rather than six calls spread across the package bootstrap, so
    a knob cannot be parsed here and left unbound there.
    """
    return {
        "ANALYTICS_LOG_PATH": parse_log_path(),
        "ANALYTICS_RETENTION_DAYS": parse_retention_days(),
        "ANALYTICS_DB_URL": parse_db_url(),
        "TRACK_SKILL_TRIGGERS": parse_track_skill_triggers(),
        "TRAJECTORY_LOG_PATH": parse_trajectory_log_path(),
        "TRAJECTORY_RETENTION_DAYS": parse_trajectory_retention_days(),
    }


def settings_on(holder: Any) -> Settings:
    """Read the knobs off the settings holder a caller is bound to.

    The analytics package is where the parsed values are bound and where a
    caller patches one, so an adapter reads them back off it rather than
    re-parsing or caching. *Which* instance is a caller's own question: a
    recorder answers with the one it captured at its own import, because a
    package re-imported against a different environment is what its own
    callers drive, and reaching for the current instance instead would hand
    them the process-wide one's values.
    """
    return Settings(holder)


def live_settings() -> Settings:
    """Read the knobs off whichever analytics package the name resolves to.

    What a caller with nothing captured reads through -- the read path and the
    sync, each of which is entered on the same instance the environment was
    patched around.
    """
    from orchestrator import analytics

    return settings_on(analytics)


def resolve_db_url(db_url: Optional[str]) -> Optional[str]:
    """Resolve one read's database URL: the explicit argument, else the knob.

    Every read helper accepts a caller-supplied `db_url=` and falls back to
    `ANALYTICS_DB_URL` when it is `None`, so the URL-source policy is decided
    here once instead of at each call site.
    """
    if db_url is None:
        return live_settings().db_url
    return db_url
