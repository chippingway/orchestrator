# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the run record, answered by its owner.

The class is the owner's own, views and cached turn index already bound, so a
run parsed through one import site and a run built through the other are the
same type -- which is what an ``isinstance`` check, a repr, and the page's type
hints all read off.
"""

from __future__ import annotations

from orchestrator.observability.trajectory_viewer import runs


TrajectoryRun = runs.TrajectoryRun
