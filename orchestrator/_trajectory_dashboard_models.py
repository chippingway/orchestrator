# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the page state, answered by its owner.

Both shapes are the owner's own objects, and both report this module, because
this is the site the page state is published from. That is also why the typing
vocabulary and the two record shapes they are annotated in are imported here
and used for nothing else: ``get_type_hints`` resolves a class's annotations in
the globals of the module it names, and under postponed evaluation those
annotations are text.
"""

from __future__ import annotations

from pathlib import Path as Path
from typing import Optional as Optional, Sequence as Sequence

from orchestrator.observability.trajectory_viewer import page_models
from orchestrator.observability.trajectory_viewer.filter_models import (
    FilterOptions as FilterOptions,
)
from orchestrator.observability.trajectory_viewer.runs import (
    TrajectoryRun as TrajectoryRun,
)


_TrajectoryFilters = page_models._TrajectoryFilters
_TrajectoryPage = page_models._TrajectoryPage
