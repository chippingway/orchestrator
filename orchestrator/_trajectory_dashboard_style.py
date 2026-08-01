# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the viewer's stylesheet, answered by its owner.

The string is the owner's own, so the page injects the same rules whichever
module it reached them through.
"""

from __future__ import annotations

from orchestrator.observability.trajectory_viewer import css


EXTRA_CSS = css.EXTRA_CSS
