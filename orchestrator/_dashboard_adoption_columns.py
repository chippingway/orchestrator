# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the adoption table's column vocabulary.

The nine columns per-session skill adoption is read across, the key each is
ordered by, the subset a first click sorts descending, and the pair of query
parameters its headers write are the dashboard owner's own objects. A caller
that names this module gets those rather than a copy, so the header a page
links from and the parse that reads it back cannot start spelling one sort two
ways.
"""
from __future__ import annotations

from orchestrator.observability.dashboard import skill_adoption_columns


SkillAdoptionColumn = skill_adoption_columns.SkillAdoptionColumn
SKILL_ADOPTION_COLUMNS = skill_adoption_columns.SKILL_ADOPTION_COLUMNS
SKILL_ADOPTION_NUMERIC_KEYS = skill_adoption_columns.SKILL_ADOPTION_NUMERIC_KEYS
SKILL_ADOPTION_SORT_KEYS = skill_adoption_columns.SKILL_ADOPTION_SORT_KEYS
SKILL_ADOPTION_SORT_PARAM = skill_adoption_columns.SKILL_ADOPTION_SORT_PARAM
SKILL_ADOPTION_DIR_PARAM = skill_adoption_columns.SKILL_ADOPTION_DIR_PARAM
