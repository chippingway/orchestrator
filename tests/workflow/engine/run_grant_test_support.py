# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The thread and the ledger the add-agent-runs command is read against.

The park's own fixtures live beside its owner
(`run_limit_test_support`); what is here is the half this command adds to
them -- an issue that has actually spent what it was allowed, and the comment
somebody wrote on its thread. Both the owner's tests and the dispatcher's read
them, since the command is answered by the hold rather than by a stage.
"""
from __future__ import annotations

from orchestrator.github.pinned_state import PinnedState
from tests.support.fakes import FakeComment, FakeUser
from tests.workflow.engine.run_limit_test_support import (
    ALLOWANCE,
    USED_FIELD,
    WATERMARK,
    parked_state,
)

# The default id a command comment carries: above the watermark a park
# consumed, and below the ids the fake client mints for what it posts itself,
# so a receipt written in answer to one always sorts after it.
COMMAND_ID = WATERMARK + 5

# The id of a comment somebody writes while a tick is answering the command
# below it: above the batch that tick read, and below the ids the fake client
# mints for what the orchestrator posts itself. That order is the race -- the
# comment exists before the receipt does, and no read here has seen it.
RACING_COMMENT_ID = COMMAND_ID + 1

# The author every command here is written by unless it is the outsider's.
# The allowlist is empty by default, so what this login pins is which comment
# was said by whom rather than whether it was trusted.
OPERATOR = "geserdugarov"


def spent_state(**fields) -> PinnedState:
    """A parked issue that has spent every run of a full allowance.

    The count is what this command is read against: what it buys is measured
    from the runs already spent, so a fixture that had spent none would pin an
    allowance the arithmetic cannot tell from the request.
    """
    return parked_state(**{USED_FIELD: ALLOWANCE, **fields})


def command(text: str, *, comment_id: int = COMMAND_ID, author: str = OPERATOR):
    """One thread comment, as an operator or an outsider wrote it."""
    return FakeComment(id=comment_id, body=text, user=FakeUser(author))
