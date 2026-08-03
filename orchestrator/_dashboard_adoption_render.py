# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the per-session skill-adoption table.

The notice a window with no session evidence renders instead, the rules the
panel scopes to its own class, and the sorted table itself are the dashboard
owner's own objects. A caller that names this module gets those rather than a
copy, so the table a page draws and the one the owner builds cannot start
answering differently about which skills a repository's sessions loaded.
"""
from __future__ import annotations

from orchestrator.observability.dashboard import skill_adoption


SKILL_ADOPTION_EMPTY_MESSAGE = skill_adoption.SKILL_ADOPTION_EMPTY_MESSAGE
SKILL_ADOPTION_EXTRA_CSS = skill_adoption.SKILL_ADOPTION_EXTRA_CSS
_skill_adoption_html = skill_adoption.skill_adoption_html
