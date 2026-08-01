# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical date-window import site, answered by the window owner.

The six names are read off the owner, so a window a caller builds here is the
one the reads are bounded by and the one an `isinstance` against the dataclass
holds for.
"""

from __future__ import annotations

from orchestrator.observability.dashboard import windows


DateWindow = windows.DateWindow
default_date_range = windows.default_date_range
to_window = windows.to_window
extent_dates = windows.extent_dates
preset_window = windows.preset_window
previous_window = windows.previous_window
