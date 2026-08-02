# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the per-repository spend ranking.

The adapter that draws a window's repositories as bars and the short name each
bar is labelled by are the charts owner's own objects. The cost hub that names
this module reaches those rather than a copy, so a repository cannot be
labelled one way here and another under the owner.
"""
from __future__ import annotations

from orchestrator.observability.dashboard.charts import cost_repo


cost_by_repo = cost_repo.cost_by_repo
_repo_short_name = cost_repo.repo_short_name
