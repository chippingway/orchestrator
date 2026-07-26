# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Forwarding surface for the GitHub comment trust policy.

Every name below is defined by :mod:`orchestrator.github.comments`; nothing is
rebuilt here, so a caller reaching through this module sees the owner's exact
object. Orchestrator code imports the owner, and this module stays the import
site tests and external operator scripts already reference.
"""
from __future__ import annotations

from orchestrator.github import comments as _comments

filter_trusted = _comments.filter_trusted
is_trusted_author = _comments.is_trusted_author
