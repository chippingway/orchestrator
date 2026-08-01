# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the field coercion, answered by its owner.

The five helpers are the owner's own functions, so what an absent, restyled, or
hand-edited field narrows to is decided once rather than per import site.
"""

from __future__ import annotations

from orchestrator.observability.trajectory_viewer import coercion


coerce_int = coercion.coerce_int
coerce_float = coercion.coerce_float
coerce_str = coercion.coerce_str
coerce_str_tuple = coercion.coerce_str_tuple
as_list = coercion.as_list
