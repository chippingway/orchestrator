# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for two of the skill panel reads.

Both are the dashboard owner's own objects. A caller that names this module --
the hub in front of it, and every historical `dashboard.<name>` import through
that hub -- reaches those rather than a copy of either, so a page and the owner
cannot answer differently. The third of the trio is reached through
`_dashboard_read_breakdowns`, which is where a caller has always spelled it.
"""
from __future__ import annotations

from orchestrator.observability.dashboard import skills


_read_skill_trigger_matrix = skills.read_skill_trigger_matrix
_read_skill_adoption = skills.read_skill_adoption
