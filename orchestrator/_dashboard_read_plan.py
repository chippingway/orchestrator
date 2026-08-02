# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the staged read plan.

The plan a page load is described by, the task each of its entries is built
as, the two wave registries, and the key pair they are bound to are the
dashboard owner's own objects. A caller that names this module -- the dispatch
leaf beside it, the hub in front of them, and every historical
`dashboard.<name>` import through that hub -- reaches those rather than a copy
of any of them, so a page and the owner cannot stage a load differently. The
reader alias is the fan-out owner's, which is where the type a wave is made of
has always been decided.
"""
from __future__ import annotations

from orchestrator.observability.dashboard import fanout, read_plan


_ReaderTask = fanout.NamedReader
_DashboardReadPlan = read_plan.DashboardReadPlan
_widget_task = read_plan.widget_task
_first_wave_readers = read_plan.first_wave_readers
_second_wave_readers = read_plan.second_wave_readers
_widget_readers = read_plan.widget_readers
_build_read_keys = read_plan.build_read_keys
