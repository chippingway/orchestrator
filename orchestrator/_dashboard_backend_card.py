# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the backend card, forwarding to its owner."""
from __future__ import annotations

from orchestrator.observability.dashboard import backend_card


BackendEfficiencyMetrics = backend_card.BackendEfficiencyMetrics
safe_ratio = backend_card.safe_ratio
backend_efficiency_metrics = backend_card.backend_efficiency_metrics
backend_efficiency_card_html = backend_card.backend_efficiency_card_html
