# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a query test sets up around a call, and how it reads the failure back.

Two things every module here needs and neither owner provides: the configured
URL an omitted `db_url=` falls back to, which is read off the analytics
settings holder rather than the environment, and a way to hold the raised
`AnalyticsReadError`
so its `__cause__` can be asserted -- the chaining is the contract, so a test
that only checked the type would pass on a wrapper that dropped the driver
exception.
"""

from __future__ import annotations

import contextlib
from importlib import import_module
from typing import Any, Callable, Iterator, Optional
from unittest.mock import patch

from orchestrator.observability.analytics.query.connections import AnalyticsReadError

# The stand-in DSNs these tests thread through `db_url=` and the configured
# knob; only their identities matter, nothing ever dials them.
DB_URL = "postgresql://h/db"

OTHER_DB_URL = "postgresql://other/db"

_DB_URL_SETTING = "ANALYTICS_DB_URL"


@contextlib.contextmanager
def configured_db_url(url: Optional[str] = DB_URL) -> Iterator[None]:
    """Pin what an omitted `db_url=` resolves to for the body."""
    holder = import_module("orchestrator.observability.analytics.settings")
    with patch.object(holder, _DB_URL_SETTING, url):
        yield


def read_error_from(call: Callable[[], Any]) -> AnalyticsReadError:
    """Run `call` and hand back the read error it raised."""
    try:
        call()
    except AnalyticsReadError as error:
        return error
    raise AssertionError("expected an AnalyticsReadError")
