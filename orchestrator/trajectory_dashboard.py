# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical trajectory-viewer launch path and lazy compatibility facade.

The page is `orchestrator/apps/trajectory_dashboard.py`. This module keeps the
`streamlit run` target an operator's shell history and bookmarks already carry,
and the lazy inventory a historical caller reaches the viewer's page surface
through -- every name on it resolving to the owner that defines it.
"""
from __future__ import annotations

if __package__:
    from orchestrator._trajectory_dashboard_bootstrap import (
        bootstrap_trajectory_dashboard,
    )
else:
    from _trajectory_dashboard_bootstrap import bootstrap_trajectory_dashboard


_FACADE = bootstrap_trajectory_dashboard(__file__, __name__, __package__)
__getattr__ = _FACADE.resolve_export
__dir__ = _FACADE.exported_dir
main = _FACADE.main
trajectory_reader = _FACADE.trajectory_reader


if __name__ == "__main__":
    main()
