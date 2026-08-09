# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the analytics sink, prunes, and settings.

Every name here is forwarded to the owner under
``orchestrator.observability.analytics`` that defines it, resolved per access
so a knob patched on the ``settings`` holder is what a read through this
package answers with. Nothing is bound at import, so naming this package costs
an importer neither the recorders nor the process configuration behind those
knobs.
"""

from __future__ import annotations as __getattr__
from __future__ import generator_stop as __dir__

from orchestrator.analytics._package_exports import __dir__ as __dir__
from orchestrator.analytics._package_exports import __getattr__ as __getattr__
