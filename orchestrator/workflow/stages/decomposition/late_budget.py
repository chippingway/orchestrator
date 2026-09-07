# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The addition budget one proposed child declares, wherever it is met.

Four owners meet that number and each meets it in a different world: the
prompt asks for it, the reply contract judges what an agent just said, the
pinned record keeps what a crashed tick reads back, and the child issue tells
the developer implementing the slice what it was sized at. So the field and
the rule for reading one are here, in the module all four already name --
because a key spelled twice would let a prompt ask for one name while the
parser reads another, and a rule spelled twice would let a record hold a
budget the body that renders it refuses.

What counts as a declared budget is a whole number of at least one line, and
nothing that merely converts to one: a bool, a float, and a numeric string are
each a value nothing estimated, and zero and below say a slice of an oversized
candidate adds nothing. Every one of them reads back as no budget at all, so a
hand edit cannot put prose where a child issue states a size.

What an absent budget earns is the CALLER's, deliberately, because the answer
differs by who is asking. A fresh reply is refused over one, since a missing
number is a protocol failure and a reply is the last place a proposal can be
sent back before it becomes issues. A record writes none, so nothing this
binary invented reaches the comment humans read. And a child body says nothing
about a size nobody declared -- which is what a manifest recorded before this
domain kept budgets reads back as, and those still create children.
"""
from __future__ import annotations

from typing import Any

from orchestrator.workflow.late_split import formats as _formats

# The manifest key a proposed child declares its budget under. The prompt
# spells it from here and so does the parser, so the number an agent is asked
# for is the number the reply is read for.
ESTIMATE = "estimated_added_lines"

# The smallest budget a slice may claim. A child of an oversized candidate
# that adds nothing is not a slice of it.
MIN_ESTIMATE = 1


def declared_budget(child: Any) -> int | None:
    """Return the lines this child claims it will add, or None for no claim.

    None for everything that is not a count as well as for a child that
    declared nothing, since a caller that told the two apart would be acting
    on a number nobody wrote.
    """
    if not isinstance(child, dict):
        return None
    estimated = child.get(ESTIMATE)
    if not _formats.whole_number(estimated) or estimated < MIN_ESTIMATE:
        return None
    return estimated
