# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""How an adapter reads an analytics knob back, and off which holder.

`Settings` is the view every one of the six sink and database knobs is read
through, and the two ways it is entered are what settle whose values answer:
`settings_on` for the holder a caller captured at its own import,
`live_settings` for whichever the settings module name resolves to now. Both
indirections point at the `settings` owner beside this one for as long as
patching a knob on it is the interception a caller makes; what they answer for
is which holder is the caller's. `resolve_db_url` is the one policy above
them, so a read helper's `db_url=` argument beats the knob in one place rather
than at each call site.

Nothing here reads the environment: the vocabulary and the six parses are the
`environment` owner's, and `settings` is where their results are bound. The
holder is imported inside the call rather than at this module's import, so
nothing pays for the process configuration behind it until a knob is actually
read.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


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
    def log_path(self) -> Path | None:
        return self.holder.ANALYTICS_LOG_PATH

    @property
    def retention_days(self) -> int:
        return self.holder.ANALYTICS_RETENTION_DAYS

    @property
    def db_url(self) -> str | None:
        return self.holder.ANALYTICS_DB_URL

    @property
    def track_skill_triggers(self) -> bool:
        return self.holder.TRACK_SKILL_TRIGGERS

    @property
    def trajectory_log_path(self) -> Path | None:
        return self.holder.TRAJECTORY_LOG_PATH

    @property
    def trajectory_retention_days(self) -> int:
        return self.holder.TRAJECTORY_RETENTION_DAYS


def settings_on(holder: Any) -> Settings:
    """Read the knobs off the settings holder a caller is bound to.

    The `settings` owner is where the parsed values are bound and where a
    caller patches one, so an adapter reads them back off it rather than
    re-parsing or caching. *Which* holder is a caller's own question: a reader
    built against a re-imported one answers with the instance it captured at
    its own import, because that is the environment its own callers set up,
    and reaching for the current holder instead would hand them the
    process-wide values.
    """
    return Settings(holder)


def live_settings() -> Settings:
    """Read the knobs off whichever settings holder the name resolves to.

    What a caller with nothing captured reads through -- both sinks' appends,
    the two prunes, the read path, and the sync. The holder is imported inside
    the call rather than bound here, so nothing pays for the process
    configuration behind it until a knob is actually read.
    """
    from orchestrator.observability.analytics import settings

    return settings_on(settings)


def resolve_db_url(db_url: str | None) -> str | None:
    """Resolve one read's database URL: the explicit argument, else the knob.

    Every read helper accepts a caller-supplied `db_url=` and falls back to
    `ANALYTICS_DB_URL` when it is `None`, so the URL-source policy is decided
    here once instead of at each call site.
    """
    if db_url is None:
        return live_settings().db_url
    return db_url
