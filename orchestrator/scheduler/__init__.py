# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Stable process-local scheduler surface for concurrent per-issue handlers.

Typed submissions, the historical positional/keyword ``submit`` binding, and
field normalization live in the ``models`` owner; the concrete
``IssueScheduler`` -- caps, tracked claims, the family mutex, worker dispatch,
and shutdown -- lives in the ``service`` owner. This facade re-exports the
narrow public surface (``__all__``): the scheduler and the caller-facing
``SubmissionRequest``. The layers ``IssueScheduler`` is composed from belong to
``service``, so this facade carries no private re-exports.

Importing the ``service`` owner here pulls its sibling ``models`` import, which
names a submodule rather than a facade attribute; a submodule import binds on
the parent package even while this initializer is still running, so importing
either owner first never needs a name this module has not bound yet.
"""
from __future__ import annotations

from orchestrator.scheduler import models as _models
from orchestrator.scheduler import service as _service

__all__ = (
    "IssueScheduler",
    "SubmissionRequest",
)

IssueScheduler = _service.IssueScheduler
SubmissionRequest = _models.SubmissionRequest
