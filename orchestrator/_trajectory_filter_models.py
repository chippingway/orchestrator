# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the filter shapes, answered by their owner.

The two names are the owner's own, so the keyword fields one call may be driven
by and the normalized form every match is read off are spelled once rather than
per import site.
"""

from __future__ import annotations

from orchestrator.observability.trajectory_viewer import filter_models


RunFilterOptionFields = filter_models.RunFilterOptionFields
RunFilters = filter_models.RunFilters
