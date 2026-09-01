# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The Plotly configuration every figure on the page is handed.

One mapping rather than a keyword spelled at each `st.plotly_chart` call: the
page draws a figure in most of its panels, and a modebar switched off in all but
one of them is chrome that appears over exactly the card nobody remembered.
What it turns off is the hover toolbar -- camera, zoom, pan, autoscale. This
page is read rather than driven: every figure is already scoped to the window
the filter bar picked, and a stray drag inside one leaves a card zoomed into a
range no filter names and no control undoes short of a rerun.

It is a read-only proxy rather than a plain dict because it is shared by every
call site. A caller hands Plotly a copy -- the proxy is not JSON-serializable
-- and copying is what keeps one panel's config from becoming the next panel's.

Configuration is data, so this owner names neither Plotly nor Streamlit, and a
caller that needs only the switch pays for nothing else in the package.
"""
from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any


PLOTLY_CONFIG: Mapping[str, Any] = MappingProxyType({"displayModeBar": False})
