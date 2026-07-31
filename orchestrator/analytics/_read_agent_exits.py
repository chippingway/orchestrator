# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical recent-exit projection import site, answered by the query owner.

Both names are bound to the owner's own functions, so the pinned
`event = 'agent_exit'`, the binding order it fixes, and the selections that
leave the table nothing to ask for are decided in one place whichever module a
caller names.
"""

from __future__ import annotations

from orchestrator.observability.analytics.query.agent_exits import (
    agent_exit_from_row as _agent_exit_from_row,
    recent_agent_exit_rows as _recent_agent_exit_rows,
)


_COMPATIBILITY_EXPORTS = (
    _agent_exit_from_row,
    _recent_agent_exit_rows,
)
