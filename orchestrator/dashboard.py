# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical analytics-page launch path and lazy compatibility facade.

The page is `orchestrator/apps/analytics_dashboard.py`. This module keeps the
`streamlit run` target an operator's shell history and bookmarks already carry,
and the lazy inventory a historical caller reaches the whole dashboard surface
through -- every name on it resolving to the object its owner defines, `main`
included, which is the canonical app's own entrypoint.
"""
from __future__ import annotations

if __package__:
    from orchestrator._dashboard_facade_bootstrap import bootstrap_dashboard
else:
    from _dashboard_facade_bootstrap import bootstrap_dashboard


_FACADE = bootstrap_dashboard(
    __file__,
    __name__,
    __package__,
)
__getattr__ = _FACADE.resolve_export
__dir__ = _FACADE.exported_dir
main = _FACADE.main


if __name__ == "__main__":
    main()
