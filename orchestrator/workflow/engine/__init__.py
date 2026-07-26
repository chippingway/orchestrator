# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Workflow engine owners.

Home for the tick loop, dispatch, and shared-helper owners that the
``orchestrator.workflow`` facade resolves its inventory to. Callers import
the owner they need directly, so this initializer binds nothing and an
import pulls in only what the chosen owner itself needs.
"""
