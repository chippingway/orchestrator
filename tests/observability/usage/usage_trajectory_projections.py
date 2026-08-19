# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Small observable projections for trajectory parser tests."""


def claude_summary(trajectory) -> tuple:
    return (
        trajectory.backend,
        trajectory.system_prompt,
        trajectory.tools,
        trajectory.final_output,
        (trajectory.skills.available, trajectory.skills.triggered),
    )


def source_item_classes(trajectory) -> dict:
    """Each accounted source item's type and disposition, keyed by its id."""
    return {
        source_item.item_id: (source_item.item_type, source_item.disposition)
        for source_item in trajectory.source_items
    }
